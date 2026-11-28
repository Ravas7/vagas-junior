/* Login, controle de acesso e sincronização com o Firestore (Firebase).
 * Opcional: sem window.FIREBASE_CONFIG o painel usa só o navegador.
 * O navegador continua sendo a cópia principal: se estiver sem internet, nada se perde,
 * e o que mudou é enviado na próxima vez que conectar.
 *
 * Acesso (README, passo 9): quem cria conta ganha um pedido em acesso/{uid} com status
 * "pendente". O admin aprova no painel ("Acessos"). Só quem está aprovado (ou é o admin)
 * lê e grava os próprios dados em users/{uid}/... Quem é admin está nas regras do
 * Firestore, não aqui: o código do site é público.
 */
(() => {
  "use strict";

  const VERSION = "10.12.2";
  const BASE = `https://www.gstatic.com/firebasejs/${VERSION}/`;
  const listeners = new Set();
  const Sync = {
    // mode: local | signed-out | connecting | synced | error
    // access: "" | checking | admin | aprovado | pendente | recusado | erro
    status: { mode: "local", user: null, message: "", access: "" },
    configured: false,
    onStatus(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    hasAccess: () => ["admin", "aprovado"].includes(Sync.status.access),
    init, signIn, signOut, signInEmail, signUpEmail, resetPassword, authMessage, loadProfile, saveProfile, loadTelegram,
    watchRequests, decide,
  };
  window.Sync = Sync;

  let fb = null, auth = null, db = null, col = null, store = null, user = null;
  let unsubData = null, unsubAccess = null, pendingName = "";

  function set(next) {
    Sync.status = { ...Sync.status, ...next };
    listeners.forEach((fn) => { try { fn(Sync.status); } catch (e) { console.error(e); } });
  }

  function friendly(err) {
    const code = (err && err.code) || "";
    if (code.includes("permission-denied")) return "sem permissão. Confira as regras do Firestore (README, passo 9).";
    if (code.includes("unauthorized-domain")) return "este endereço não está autorizado no Firebase (Authentication > Configurações > Domínios autorizados).";
    if (code.includes("network") || code.includes("unavailable")) return "sem conexão. As mudanças ficam salvas aqui e seguem quando voltar.";
    return (err && err.message) || "erro desconhecido";
  }

  /* mensagens de login e cadastro, em frases curtas */
  function authMessage(err) {
    const code = (err && err.code) || "";
    const map = {
      "auth/invalid-credential": "E-mail ou senha incorretos.",
      "auth/wrong-password": "E-mail ou senha incorretos.",
      "auth/user-not-found": "E-mail ou senha incorretos.",
      "auth/invalid-email": "Esse e-mail não parece válido.",
      "auth/missing-password": "Digite a senha.",
      "auth/email-already-in-use": "Já existe uma conta com esse e-mail. Use a aba Entrar.",
      "auth/weak-password": "Senha fraca. Use pelo menos 6 caracteres.",
      "auth/too-many-requests": "Muitas tentativas seguidas. Espere alguns minutos e tente de novo.",
      "auth/network-request-failed": "Sem conexão com a internet.",
      "auth/popup-blocked": "O navegador bloqueou a janela do Google. Libere pop-ups para este site.",
      "auth/operation-not-allowed": "Esse jeito de entrar ainda não foi ligado no Firebase (README, passo 9).",
      "auth/unauthorized-domain": "Este endereço não está autorizado no Firebase (README, passo 9).",
      "auth/account-exists-with-different-credential": "Esse e-mail já entra de outro jeito. Tente com Google ou com senha.",
    };
    return map[code] || friendly(err);
  }

  async function init(theStore) {
    store = theStore;
    const cfg = window.FIREBASE_CONFIG;
    Sync.configured = !!(cfg && cfg.apiKey && cfg.projectId && cfg.appId);
    if (!Sync.configured) { set({ mode: "local" }); return; }

    set({ mode: "connecting" });
    try {
      const [app, au, fs] = await Promise.all([
        import(BASE + "firebase-app.js"),
        import(BASE + "firebase-auth.js"),
        import(BASE + "firebase-firestore.js"),
      ]);
      fb = { au, fs };
      const instance = app.initializeApp(cfg);
      auth = au.getAuth(instance);
      auth.languageCode = "pt";                            // e-mails do Firebase em português
      db = fs.getFirestore(instance);
    } catch (err) {
      console.warn(err);
      set({ mode: "error", user: null, message: "não foi possível carregar o login (sem internet?)." });
      return;
    }

    store.subscribe((ev) => {
      if (ev.source === "remote") return;                 // veio da nuvem, não precisa voltar
      ev.ids.forEach((id) => push(store.getRaw(id)));
    });
    fb.au.onAuthStateChanged(auth, onUser, (err) => set({ mode: "error", message: friendly(err) }));
  }

  /* ---------- quem entrou: primeiro o acesso, depois os dados ---------- */
  function stopAll() {
    if (unsubData) { unsubData(); unsubData = null; }
    if (unsubAccess) { unsubAccess(); unsubAccess = null; }
    col = null;
  }

  function onUser(u) {
    stopAll();
    user = u;
    if (!u) { set({ mode: "signed-out", user: null, message: "", access: "" }); return; }
    set({ mode: "connecting", user: { uid: u.uid, email: u.email || "", name: u.displayName || pendingName || "" },
      message: "", access: "checking" });
    watchAccess(u);
  }

  /* O admin consegue listar todos os pedidos; os outros não (regra do Firestore). */
  async function isAdmin() {
    try {
      await fb.fs.getDocs(fb.fs.query(fb.fs.collection(db, "acesso"), fb.fs.limit(1)));
      return true;
    } catch (err) {
      return false;
    }
  }

  /* O admin também aparece como "aprovado" em acesso/: assim o robô manda aviso para ele.
     Ser admin continua dependendo só das regras (e-mail), não deste documento. */
  async function listAdmin(u) {
    try {
      const ref = fb.fs.doc(db, "acesso", u.uid);
      const snap = await fb.fs.getDoc(ref);
      if (snap.exists() && snap.data().status === "aprovado") return;
      await fb.fs.setDoc(ref, {
        email: u.email || "", nome: (u.displayName || "").slice(0, 60), status: "aprovado",
        ...(snap.exists() ? {} : { pedidoEm: fb.fs.serverTimestamp() }), decididoEm: fb.fs.serverTimestamp(),
      }, { merge: true });
    } catch (err) {
      console.warn("admin na lista de acesso:", err);          // regra antiga: sem problema, só não recebe aviso
    }
  }

  /* Regras antigas (sem a coleção acesso): quem já lia os próprios dados continua lendo. */
  async function legacyAccess(u) {
    try {
      await fb.fs.getDoc(fb.fs.doc(db, "users", u.uid, "perfil", "atual"));
      return true;
    } catch (err) {
      return false;
    }
  }

  async function watchAccess(u) {
    // o admin entra direto, mesmo que exista um pedido antigo em nome dele
    if (await isAdmin()) { listAdmin(u); return grant(u, "admin"); }
    if (user !== u) return;
    const ref = fb.fs.doc(db, "acesso", u.uid);
    let asked = false;
    unsubAccess = fb.fs.onSnapshot(ref, async (snap) => {
      if (user !== u) return;
      if (!snap.exists()) {
        if (asked) return;
        asked = true;                                      // pede acesso uma vez; o snapshot volta com "pendente"
        try {
          await fb.fs.setDoc(ref, {
            email: u.email || "", nome: (u.displayName || pendingName || "").slice(0, 60),
            status: "pendente", pedidoEm: fb.fs.serverTimestamp(),
          });
        } catch (err) {
          console.warn(err);
          set({ access: "erro", message: friendly(err) });
        }
        return;
      }
      const st = snap.data().status;
      if (st === "aprovado") return grant(u, "aprovado");
      if (unsubData) { unsubData(); unsubData = null; col = null; }   // foi bloqueado agora
      set({ access: st === "recusado" ? "recusado" : "pendente", mode: "connecting" });
    }, async (err) => {
      if (user !== u) return;
      if (await legacyAccess(u)) return grant(u, "aprovado");
      console.warn(err);
      set({ access: "erro", message: friendly(err) });
    });
  }

  function grant(u, access) {
    if (user !== u) return;
    set({ access });
    if (unsubData) return;
    col = fb.fs.collection(db, "users", u.uid, "candidaturas");
    unsubData = fb.fs.onSnapshot(col, (snap) => {
      const remote = snap.docs.map((d) => d.data());
      store.mergeRemote(remote).forEach(push);           // o que é mais novo aqui sobe para a nuvem
      set({ mode: "synced", message: "" });
    }, (err) => set({ mode: "error", message: friendly(err) }));
  }

  function push(app) {
    if (!app || !user || !col) return;
    const ref = fb.fs.doc(col, encodeURIComponent(app.id));
    fb.fs.setDoc(ref, JSON.parse(JSON.stringify(app)))
      .catch((err) => set({ mode: "error", message: friendly(err) }));
  }

  /* ---------- admin: pedidos de acesso ---------- */
  /* Chama fn com a lista de pedidos sempre que muda. Devolve a função para parar. */
  function watchRequests(fn) {
    if (!db || Sync.status.access !== "admin") return () => {};
    return fb.fs.onSnapshot(fb.fs.collection(db, "acesso"), (snap) => {
      fn(snap.docs.map((d) => {
        const x = d.data();
        const when = x.pedidoEm && x.pedidoEm.toDate ? x.pedidoEm.toDate() : null;
        return { uid: d.id, email: x.email || "", nome: x.nome || "", status: x.status || "pendente", pedidoEm: when };
      }));
    }, (err) => console.warn("pedidos de acesso:", err));
  }

  async function decide(uid, status) {
    await fb.fs.updateDoc(fb.fs.doc(db, "acesso", uid), { status, decididoEm: fb.fs.serverTimestamp() });
  }

  /* ---------- entrar e sair ---------- */
  async function signIn() {
    if (!auth) return;
    try {
      await fb.au.signInWithPopup(auth, new fb.au.GoogleAuthProvider());
    } catch (err) {
      if (err && /popup-closed|cancelled-popup/.test(err.code || "")) return;
      set({ mode: "signed-out", message: authMessage(err) });
    }
  }

  async function signOut() {
    if (auth) await fb.au.signOut(auth);                  // os dados continuam neste navegador
  }

  /* As três abaixo devolvem uma promessa; quem chama (login.js) mostra o erro com authMessage. */
  async function signInEmail(email, password) {
    if (!auth) throw { code: "auth/network-request-failed" };
    await fb.au.signInWithEmailAndPassword(auth, email, password);
  }

  async function signUpEmail(name, email, password) {
    if (!auth) throw { code: "auth/network-request-failed" };
    pendingName = name || "";                             // o pedido de acesso nasce antes do nome ser gravado
    const cred = await fb.au.createUserWithEmailAndPassword(auth, email, password);
    if (name) {
      await fb.au.updateProfile(cred.user, { displayName: name });
      set({ user: { uid: cred.user.uid, email: cred.user.email || email, name } });
    }
  }

  async function resetPassword(email) {
    if (!auth) throw { code: "auth/network-request-failed" };
    await fb.au.sendPasswordResetEmail(auth, email);
  }

  /* Perfil: um documento só, em users/{uid}/perfil/atual. null = ainda não tem. */
  const profileRef = () => (user && db ? fb.fs.doc(db, "users", user.uid, "perfil", "atual") : null);

  async function loadProfile() {
    const ref = profileRef();
    if (!ref) return null;
    const snap = await fb.fs.getDoc(ref);
    return snap.exists() ? snap.data() : null;
  }

  /* Telegram ligado? O robô grava telegram/{uid} quando a pessoa toca em Começar no bot. */
  async function loadTelegram() {
    if (!user || !db) return null;
    const snap = await fb.fs.getDoc(fb.fs.doc(db, "telegram", user.uid));
    return snap.exists() ? snap.data() : null;
  }

  async function saveProfile(profile) {
    const ref = profileRef();
    if (!ref) throw { code: "auth/network-request-failed" };
    await fb.fs.setDoc(ref, JSON.parse(JSON.stringify(profile)));
  }
})();
