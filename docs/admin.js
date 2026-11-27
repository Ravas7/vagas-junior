/* Tela "Acessos": só para o admin (quem as regras do Firestore deixam listar acesso/).
 * Mostra os pedidos de quem criou conta e libera ou recusa com um clique.
 * O link "Acessos" no topo mostra quantos pedidos estão esperando.
 */
(() => {
  "use strict";
  if (!window.Sync) return;
  const Sync = window.Sync;

  let list = [], stop = null, dialog = null, busy = new Set();

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

  /* número de pedidos esperando: vai dentro do item "Acessos" do menu da conta */
  const count = h("span", { class: "count alert", hidden: true });

  const pending = () => list.filter((r) => r.status === "pendente");

  function paintCount() {
    const n = pending().length;
    count.textContent = n;
    count.hidden = !n;
    count.setAttribute("aria-label", n ? `${n} ${n === 1 ? "pedido esperando" : "pedidos esperando"}` : "");
    // pontinho de aviso no botão da conta e no "Perfil" da barra do celular
    const btn = document.getElementById("acct-btn");
    if (btn) btn.classList.toggle("has-alert", n > 0);
    const nav = document.querySelector('.bn-count[data-for="acessos"]');
    if (nav) { nav.textContent = n; nav.hidden = !n; }
  }

  Sync.onStatus((s) => {
    if (s.access === "admin" && !stop) {
      stop = Sync.watchRequests((rows) => { list = rows; paintCount(); if (dialog && dialog.open) render(); });
    } else if (s.access !== "admin" && stop) {
      stop(); stop = null; list = []; paintCount();
      if (dialog && dialog.open) dialog.close();
    }
  });

  const fmt = (d) => (d ? d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }) : "");

  async function decide(r, status) {
    busy.add(r.uid); render();
    try { await Sync.decide(r.uid, status); }
    catch (err) { console.warn(err); alert("Não deu para salvar: " + Sync.authMessage(err)); }
    busy.delete(r.uid); render();
  }

  function row(r) {
    const wait = busy.has(r.uid);
    const actions = {
      pendente: [["Liberar", "aprovado", "primary"], ["Recusar", "recusado", ""]],
      aprovado: [["Bloquear", "recusado", ""]],
      recusado: [["Liberar", "aprovado", ""]],
    }[r.status] || [];
    return h("li", { class: "ad-row" },
      h("div", { class: "ad-who" },
        h("b", {}, r.nome || r.email || "(sem nome)"),
        r.nome && h("span", {}, r.email),
        r.pedidoEm && h("small", {}, "Pediu em " + fmt(r.pedidoEm))),
      h("div", { class: "ad-actions" }, actions.map(([label, status, tone]) =>
        h("button", { class: `kb-btn small ${tone}`, type: "button", disabled: wait, onclick: () => decide(r, status) },
          wait ? "Salvando…" : label))));
  }

  function section(title, rows, empty) {
    return h("section", { class: "ad-sec" },
      h("h3", {}, `${title} `, h("span", { class: "count" }, rows.length)),
      rows.length ? h("ul", { class: "ad-list" }, rows.map(row)) : h("p", { class: "kb-note" }, empty));
  }

  function render() {
    const by = (st) => list.filter((r) => r.status === st)
      .sort((a, b) => (b.pedidoEm || 0) - (a.pedidoEm || 0));
    dialog.replaceChildren(
      h("h2", { id: "ad-title" }, "Acessos"),
      h("p", { class: "kb-dialog-sub" }, "Quem cria conta aparece aqui. Só quem você liberar consegue usar o painel."),
      section("Esperando", by("pendente"), "Nenhum pedido esperando."),
      section("Liberados", by("aprovado"), "Ninguém liberado ainda."),
      by("recusado").length ? section("Recusados", by("recusado"), "") : "",
      h("div", { class: "kb-dialog-actions" },
        h("button", { class: "kb-btn", type: "button", onclick: () => dialog.close() }, "Fechar")));
  }

  function open() {
    if (!dialog) {
      dialog = h("dialog", { class: "kb-dialog ad-dialog", "aria-labelledby": "ad-title" });
      dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
      document.body.append(dialog);
    }
    render();
    if (!dialog.open) dialog.showModal();
  }

  window.Admin = { badge: () => count, open, _set: (rows) => { list = rows; paintCount(); } };
})();
