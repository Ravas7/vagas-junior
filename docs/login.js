/* Tela de entrada: o painel só aparece depois do login (Google ou e-mail e senha).
 * Sem window.FIREBASE_CONFIG não há como entrar, então o painel abre direto (uso local).
 * Quem decide se está logado é o sync.js; aqui só desenhamos a tela.
 */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const root = document.documentElement;
  const Sync = window.Sync;
  const msg = $("#gate-msg");
  let busy = false;

  function say(text, kind = "") {
    msg.textContent = text || "";
    msg.className = "gate-msg" + (kind ? " is-" + kind : "");
  }

  function showTab(tab) {
    const entrar = tab === "entrar";
    $("#gate-tab-entrar").setAttribute("aria-selected", String(entrar));
    $("#gate-tab-criar").setAttribute("aria-selected", String(!entrar));
    $("#gate-entrar").hidden = !entrar;
    $("#gate-criar").hidden = entrar;
    say("");
    const first = (entrar ? $("#gate-entrar") : $("#gate-criar")).querySelector("input");
    if (first && !first.value) first.focus();
  }

  /* trava os botões enquanto espera o Firebase, para não mandar duas vezes */
  async function run(button, label, work) {
    if (busy) return;
    busy = true;
    const old = button.textContent;
    button.disabled = true;
    button.textContent = label;
    say("");
    try {
      await work();
    } catch (err) {
      console.warn(err);
      say(Sync.authMessage(err), "err");
    } finally {
      busy = false;
      button.disabled = false;
      button.textContent = old;
    }
  }

  const btn = (label, onclick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "link-btn";
    b.textContent = label;
    b.addEventListener("click", onclick);
    return b;
  };

  function paintAccount(user, admin) {
    const box = $("#account");
    if (!user) { box.hidden = true; box.replaceChildren(); return; }
    const parts = [`Conectado como ${user.name || user.email} · `,
      btn("Meu perfil", () => window.Perfil && window.Perfil.open()), " · "];
    if (admin && window.Admin) parts.push(window.Admin.link(), " · ");     // só o admin vê "Acessos"
    parts.push(btn("Sair", () => Sync.signOut()));
    box.replaceChildren(...parts);
    box.hidden = false;
  }

  /* conta criada, mas ainda sem acesso: pendente, recusado ou erro ao conferir */
  function paintAccess(status) {
    const box = $("#gate-access");
    const st = status.access;
    const show = !!status.user && ["pendente", "recusado", "erro"].includes(st);
    box.hidden = !show;
    if (!show) return;
    const who = status.user.email ? ` (${status.user.email})` : "";
    const texts = {
      pendente: ["Pedido enviado", `Sua conta${who} foi criada e o pedido de acesso chegou para a liberação. `
        + "Assim que for aprovado, esta tela abre sozinha. Pode fechar e voltar depois."],
      recusado: ["Acesso não liberado", `O acesso da conta${who} não foi liberado. Fale com quem te convidou para o Ragas.`],
      erro: ["Não deu para conferir seu acesso", status.message || "Tente de novo em instantes."],
    };
    const [title, body] = texts[st];
    box.className = "gate-access is-" + st;
    box.replaceChildren(
      Object.assign(document.createElement("h2"), { textContent: title }),
      Object.assign(document.createElement("p"), { textContent: body }),
      btn("Sair e entrar com outra conta", () => Sync.signOut()));
  }

  function paint(status) {
    const configured = Sync.configured || !!(window.FIREBASE_CONFIG && window.FIREBASE_CONFIG.apiKey);
    const user = status.user;
    // sem Firebase, ou logado e liberado: mostra o painel
    const open = (!configured && status.mode === "local") || (!!user && Sync.hasAccess());
    root.classList.toggle("gated", !open);
    paintAccount(open && user ? user : null, status.access === "admin");
    paintAccess(status);
    if (open) return;

    const blocked = !!user && ["pendente", "recusado", "erro"].includes(status.access);
    const waiting = !blocked && (status.mode === "connecting" || (!!user && status.access === "checking"));
    const failed = !blocked && !user && status.mode === "error";
    $("#gate-wait").hidden = !waiting;
    $("#gate-forms").hidden = waiting || failed || blocked || !!user;
    $("#gate-retry").hidden = !failed;
    if (failed) say("Não deu para carregar o login: " + status.message, "err");
    else if (status.mode === "signed-out" && status.message) say(status.message, "err");
    else if (blocked) say("");
  }

  function bind() {
    $("#gate-tab-entrar").addEventListener("click", () => showTab("entrar"));
    $("#gate-tab-criar").addEventListener("click", () => showTab("criar"));
    // setas do teclado trocam de aba, como nas abas do painel
    $(".gate-tabs").addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const next = $("#gate-tab-entrar").getAttribute("aria-selected") === "true" ? "criar" : "entrar";
      showTab(next);
      $("#gate-tab-" + next).focus();
    });

    $("#gate-google").addEventListener("click", (e) =>
      run(e.currentTarget, "Abrindo o Google…", () => Sync.signIn()));

    $("#gate-entrar").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.currentTarget;
      const email = f.email.value.trim(), senha = f.senha.value;
      if (!email || !senha) return say("Preencha e-mail e senha.", "err");
      run(f.querySelector('[type="submit"]'), "Entrando…", () => Sync.signInEmail(email, senha));
    });

    $("#gate-criar").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.currentTarget;
      const nome = f.nome.value.trim(), email = f.email.value.trim();
      if (!nome || !email || !f.senha.value) return say("Preencha nome, e-mail e senha.", "err");
      if (f.senha.value.length < 6) return say("A senha precisa ter pelo menos 6 caracteres.", "err");
      if (f.senha.value !== f.senha2.value) return say("As duas senhas não são iguais.", "err");
      run(f.querySelector('[type="submit"]'), "Criando conta…", () => Sync.signUpEmail(nome, email, f.senha.value));
    });

    $("#gate-forgot").addEventListener("click", (e) => {
      const email = $("#gate-entrar").email.value.trim();
      if (!email) { say("Digite seu e-mail acima e clique de novo em “Esqueci minha senha”.", "err"); $("#gate-entrar").email.focus(); return; }
      run(e.currentTarget, "Enviando…", async () => {
        await Sync.resetPassword(email);
        say(`Se existir uma conta com ${email}, chega um e-mail para criar uma senha nova. Olhe também o spam.`, "ok");
      });
    });

    $("#gate-retry").addEventListener("click", () => location.reload());
  }

  bind();
  Sync.onStatus(paint);
  // Firebase desligado: sync.js diz "local" logo de cara; com Firebase, espera a resposta do login
  paint(Sync.status.mode === "local" && !(window.FIREBASE_CONFIG && window.FIREBASE_CONFIG.apiKey)
    ? Sync.status : { mode: "connecting", user: null, message: "" });
})();
