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

  function paintAccount(user) {
    const box = $("#account");
    if (!user) { box.hidden = true; box.replaceChildren(); return; }
    const out = document.createElement("button");
    out.type = "button";
    out.className = "link-btn";
    out.textContent = "Sair";
    out.addEventListener("click", () => Sync.signOut());
    const perfil = document.createElement("button");
    perfil.type = "button";
    perfil.className = "link-btn";
    perfil.textContent = "Meu perfil";
    perfil.addEventListener("click", () => window.Perfil && window.Perfil.open());
    box.replaceChildren(`Conectado como ${user.name || user.email} · `, perfil, " · ", out);
    box.hidden = false;
  }

  function paint(status) {
    const configured = Sync.configured || !!(window.FIREBASE_CONFIG && window.FIREBASE_CONFIG.apiKey);
    const user = status.user;
    // sem Firebase, ou já logado: mostra o painel
    const open = (!configured && status.mode === "local") || !!user;
    root.classList.toggle("gated", !open);
    paintAccount(open && user ? user : null);
    if (open) return;

    const waiting = status.mode === "connecting";
    const failed = status.mode === "error";
    $("#gate-wait").hidden = !waiting;
    $("#gate-forms").hidden = waiting || failed;
    $("#gate-retry").hidden = !failed;
    if (failed) say("Não deu para carregar o login: " + status.message, "err");
    else if (status.mode === "signed-out" && status.message) say(status.message, "err");
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
