/* "Apagar minha conta": janela de confirmação.
 * Abre pelo botão da página dados.html (que manda para o painel com #apagar-conta).
 * Quem entra com senha digita a senha; quem entra com Google confirma numa janela do Google.
 * A parte que apaga de verdade está em sync.js (deleteAccount).
 */
(() => {
  "use strict";
  if (!window.Sync) return;
  const Sync = window.Sync;
  const HASH = "#apagar-conta";
  let dialog = null;

  function h(tag, attrs = {}, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid == null || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(kid));
    }
    return el;
  }

  function message(err) {
    const code = (err && err.code) || "";
    if (/popup-closed|cancelled-popup/.test(code)) return "A janela do Google foi fechada. Nada foi apagado.";
    if (code === "auth/user-mismatch") return "Essa não é a conta que está aberta no painel. Nada foi apagado.";
    if (code === "auth/requires-recent-login") return "Por segurança, saia, entre de novo e tente logo em seguida.";
    return Sync.authMessage(err);
  }

  function open() {
    const user = Sync.status.user;
    if (!user) return;
    const senha = Sync.loginKind() === "password";
    if (!dialog) {
      dialog = h("dialog", { class: "kb-dialog del-dialog", "aria-labelledby": "del-title" });
      document.body.append(dialog);
    }
    const err = h("p", { class: "gate-msg is-err", role: "alert" });
    const form = h("form", { class: "kb-form", onsubmit: submit },
      h("h2", { id: "del-title" }, "Apagar minha conta"),
      h("p", { class: "kb-dialog-sub" }, `Conta: ${user.email}`),
      h("p", {}, "Isto apaga para sempre:"),
      h("ul", { class: "del-list" },
        h("li", {}, "seu perfil e as preferências de aviso;"),
        h("li", {}, "seu quadro de candidaturas;"),
        h("li", {}, "a ligação com o Telegram e o pedido de acesso;"),
        h("li", {}, "sua conta de login e a cópia guardada neste navegador.")),
      h("p", { class: "pf-hint" }, "Não tem como desfazer. Se quiser voltar depois, é só criar uma conta nova e pedir acesso de novo."),
      senha
        ? h("label", { class: "gate-field" }, h("span", {}, "Digite sua senha para confirmar"),
          h("input", { name: "senha", type: "password", autocomplete: "current-password", required: true }))
        : h("p", { class: "pf-hint" }, "Para confirmar, o Google vai abrir uma janela pedindo para escolher a sua conta."),
      h("label", { class: "check pf-check" }, h("input", { type: "checkbox", name: "certeza", required: true }),
        h("span", {}, "Entendi que não tem volta")),
      err,
      h("div", { class: "kb-dialog-actions" },
        h("button", { class: "kb-btn", type: "button", onclick: close }, "Cancelar"),
        h("button", { class: "kb-btn danger", type: "submit" }, "Apagar tudo")));
    dialog.replaceChildren(form);
    if (!dialog.open) dialog.showModal();

    async function submit(e) {
      e.preventDefault();
      if (!form.elements.certeza.checked) { err.textContent = "Marque “Entendi que não tem volta”."; return; }
      const btn = form.querySelector(".danger");
      btn.disabled = true; btn.textContent = "Apagando…"; err.textContent = "";
      try {
        await Sync.deleteAccount(senha ? form.elements.senha.value : "");
        dialog.replaceChildren(h("div", { class: "kb-form" },
          h("h2", {}, "Conta apagada"),
          h("p", {}, "Tudo foi apagado. Obrigado por ter usado o Ragas."),
          h("div", { class: "kb-dialog-actions" },
            h("button", { class: "kb-btn primary", type: "button", onclick: () => location.replace("./") }, "Fechar"))));
      } catch (ex) {
        console.warn(ex);
        err.textContent = message(ex);
        btn.disabled = false; btn.textContent = "Apagar tudo";
      }
    }
  }

  function close() {
    if (dialog) dialog.close();
    if (location.hash === HASH) history.replaceState(null, "", location.pathname + location.search);
  }

  /* veio de dados.html: abre assim que a pessoa estiver dentro */
  Sync.onStatus((s) => {
    const settled = s.access && s.access !== "checking";
    if (location.hash === HASH && s.user && settled && !(dialog && dialog.open)) open();
  });
  window.Conta = { open };
})();
