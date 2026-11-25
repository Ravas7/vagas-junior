/* Sincroniza as candidaturas com o Firestore (Firebase), entrando com a sua conta Google.
 * Opcional: sem window.FIREBASE_CONFIG o painel usa só o navegador.
 * O navegador continua sendo a cópia principal: se estiver sem internet, nada se perde,
 * e o que mudou é enviado na próxima vez que conectar.
 */
(() => {
  "use strict";

  const VERSION = "10.12.2";
  const BASE = `https://www.gstatic.com/firebasejs/${VERSION}/`;
  const listeners = new Set();
  const Sync = {
    status: { mode: "local", user: null, message: "" },   // local | signed-out | connecting | synced | error
    configured: false,
    onStatus(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    init, signIn, signOut, signInEmail, signUpEmail, resetPassword, authMessage,
  };
  window.Sync = Sync;

  let fb = null, auth = null, db = null, col = null, unsub = null, store = null, user = null;

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

  function onUser(u) {
    if (unsub) { unsub(); unsub = null; }
    user = u;
    if (!u) { col = null; set({ mode: "signed-out", user: null, message: "" }); return; }

    set({ mode: "connecting", user: { email: u.email || "", name: u.displayName || "" }, message: "" });
    col = fb.fs.collection(db, "users", u.uid, "candidaturas");
    unsub = fb.fs.onSnapshot(col, (snap) => {
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
    const cred = await fb.au.createUserWithEmailAndPassword(auth, email, password);
    if (name) {
      await fb.au.updateProfile(cred.user, { displayName: name });
      set({ user: { email: cred.user.email || email, name } });
    }
  }

  async function resetPassword(email) {
    if (!auth) throw { code: "auth/network-request-failed" };
    await fb.au.sendPasswordResetEmail(auth, email);
  }
})();
