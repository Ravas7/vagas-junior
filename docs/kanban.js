/* Quadro de candidaturas (kanban). No computador: colunas e arrastar. No celular: uma etapa por vez. */
(() => {
  "use strict";

  const C = window.Candidaturas;
  const DAY = 86400000;
  const WP = { remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial" };
  const DOT = { inscricao: "var(--muted)", dinamica: "var(--violet)", entrevista: "var(--teal)", proposta: "var(--amber)", encerrada: "#6b7c93" };
  const pad = (n) => String(n).padStart(2, "0");
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

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

  const dmFromMs = (ms) => { const d = new Date(ms); return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`; };
  const dmFromKey = (key) => `${key.slice(8, 10)}/${key.slice(5, 7)}`;
  const daysUntil = (key) => {
    const [y, m, d] = key.split("-").map(Number);
    return Math.round((new Date(y, m - 1, d) - startOfDay(new Date())) / DAY);
  };
  const ago = (ms) => {
    const n = Math.max(0, Math.round((startOfDay(new Date()) - startOfDay(new Date(ms))) / DAY));
    return n === 0 ? "hoje" : n === 1 ? "ontem" : `há ${n} dias`;
  };

  function mount({ root, store, sync }) {
    const ui = { stage: "inscricao", menu: null, dragId: null };
    const dialog = h("dialog", { class: "kb-dialog" });
    document.body.append(dialog);
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });   // clique fora fecha

    /* ---------- ações ---------- */
    const nextStage = (app) => {
      const i = C.ACTIVE.findIndex((s) => s.id === app.stage);
      return i >= 0 && i < C.ACTIVE.length - 1 ? C.ACTIVE[i + 1] : null;
    };
    const closeMenu = () => { if (ui.menu) { ui.menu = null; render(); } };
    const done = () => { if (dialog.open) dialog.close(); ui.menu = null; };
    const act = (fn) => () => { done(); fn(); };

    /* ---------- janelas (celular: folha de baixo; computador: janela no meio) ---------- */
    function open(...content) {
      dialog.replaceChildren(...content.flat(Infinity).filter(Boolean));
      if (!dialog.open) dialog.showModal();
    }
    const subtitle = (app) => h("p", { class: "kb-dialog-sub" }, [app.title, app.company].filter(Boolean).join(", "));
    const cancelBtn = () => h("button", { class: "kb-btn", type: "button", onclick: () => dialog.close() }, "Cancelar");

    function reasonButtons(app) {
      return h("div", { class: "kb-reasons" }, C.reasonsFor(app).map((r) =>
        h("button", { class: "kb-reason" + (r.id === "contratado" ? " is-good" : ""), type: "button",
          onclick: act(() => store.close(app.id, r.id)) }, r.name)));
    }

    function openMove(app) {
      open(
        h("h2", {}, "Mover para"), subtitle(app),
        h("div", { class: "kb-opts" },
          h("button", { class: "kb-opt", type: "button", onclick: () => openEdit(app) }, h("span", {}, "Editar próximo passo e anotação")),
          C.ACTIVE.map((s) => {
            const here = s.id === app.stage;
            return h("button", { class: "kb-opt" + (here ? " is-here" : ""), type: "button", "aria-pressed": String(here), disabled: here,
              onclick: act(() => store.move(app.id, s.id)) },
              h("i", { class: "kb-dot", style: `background:${DOT[s.id]}` }), h("span", {}, s.name), here && h("small", {}, "Etapa atual"));
          })),
        app.stage === "encerrada"
          ? h("button", { class: "kb-opt", type: "button", onclick: act(() => store.reopen(app.id)) }, h("span", {}, "Reabrir candidatura"))
          : [h("h3", { class: "kb-danger" }, "Encerrar candidatura como"), reasonButtons(app),
             h("p", { class: "kb-note" }, "Ela vai para Encerrada e guarda em que etapa parou.")],
        h("div", { class: "kb-dialog-actions" }, cancelBtn()));
    }

    function openClose(app) {
      open(h("h2", {}, "Encerrar candidatura como"), subtitle(app), reasonButtons(app),
        h("p", { class: "kb-note" }, "Ela vai para Encerrada e guarda em que etapa parou."),
        h("div", { class: "kb-dialog-actions" }, cancelBtn()));
    }

    function openEdit(app) {
      const f = {
        next: h("input", { type: "text", name: "nextText", value: app.nextText, placeholder: "Ex.: teste técnico, entrevista com o RH", maxlength: "120" }),
        date: h("input", { type: "date", name: "nextDate", value: app.nextDate }),
        note: h("textarea", { name: "note", rows: "4", maxlength: "2000" }, app.note),
      };
      open(
        h("h2", {}, "Editar candidatura"), subtitle(app),
        h("form", { class: "kb-form", onsubmit: (e) => {
          e.preventDefault();
          store.update(app.id, { nextText: f.next.value, nextDate: f.date.value, note: f.note.value });
          done();
        } },
          h("label", {}, h("span", {}, "Próximo passo"), f.next),
          h("label", {}, h("span", {}, "Data do próximo passo"), f.date),
          h("label", {}, h("span", {}, "Anotação"), f.note),
          h("div", { class: "kb-dialog-actions" }, cancelBtn(), h("button", { class: "kb-btn primary", type: "submit" }, "Salvar"))));
    }

    function openAdd() {
      const f = {
        title: h("input", { type: "text", name: "title", required: true, maxlength: "140" }),
        company: h("input", { type: "text", name: "company", required: true, maxlength: "100" }),
        url: h("input", { type: "url", name: "url", placeholder: "https://…" }),
        stage: h("select", { name: "stage" }, C.ACTIVE.map((s) => h("option", { value: s.id }, s.name))),
      };
      open(
        h("h2", {}, "Adicionar candidatura"),
        h("p", { class: "kb-dialog-sub" }, "Para vagas em que você se candidatou fora deste painel."),
        h("form", { class: "kb-form", onsubmit: (e) => {
          e.preventDefault();
          store.add({ title: f.title.value, company: f.company.value, url: f.url.value, stage: f.stage.value });
          done();
        } },
          h("label", {}, h("span", {}, "Vaga"), f.title),
          h("label", {}, h("span", {}, "Empresa"), f.company),
          h("label", {}, h("span", {}, "Link da vaga (opcional)"), f.url),
          h("label", {}, h("span", {}, "Etapa em que está"), f.stage),
          h("div", { class: "kb-dialog-actions" }, cancelBtn(), h("button", { class: "kb-btn primary", type: "submit" }, "Adicionar"))));
    }

    function openRemove(app) {
      open(h("h2", {}, "Remover do quadro?"), subtitle(app),
        h("p", { class: "kb-note" }, "Apaga a candidatura e o histórico dela, também nos outros aparelhos. Para só tirar do caminho, use Encerrar."),
        h("div", { class: "kb-dialog-actions" }, cancelBtn(),
          h("button", { class: "kb-btn danger", type: "button", onclick: act(() => store.remove(app.id)) }, "Remover")));
    }

    /* ---------- cartão ---------- */
    function card(app) {
      const mentions = (word) => new RegExp(word, "i").test(app.location);
      const place = [
        app.workplace === "remoto" && !mentions("remot") ? WP.remoto : "",
        app.location,
        app.workplace && app.workplace !== "remoto" && !mentions(WP[app.workplace] || "^$") ? WP[app.workplace] : "",
      ].filter(Boolean).join(", ");
      const closed = app.stage === "encerrada";
      const soon = !closed && app.nextDate && daysUntil(app.nextDate) <= 3;
      const nextLabel = [app.nextText, app.nextDate && (app.nextText ? dmFromKey(app.nextDate) : "Prazo " + dmFromKey(app.nextDate))]
        .filter(Boolean).join(", ");
      const nxt = nextStage(app);
      const won = app.closedReason === "contratado";
      const age = app.stage === "inscricao" ? `Enviada ${ago(app.createdAt)}`
        : closed ? `Encerrada em ${dmFromMs(app.updatedAt)}` : `Atualizada ${ago(app.updatedAt)}`;

      return h("article", {
        class: "kb-card" + (ui.dragId === app.id ? " is-dragging" : ""), draggable: "true", "data-id": app.id,
        ondragstart: (e) => {
          ui.dragId = app.id;
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", app.id);
          root.classList.add("kb--dragging");
          e.currentTarget.classList.add("is-dragging");
          root.querySelector(`.kb-col[data-stage="${app.stage}"]`)?.classList.add("is-source");
        },
        ondragend: () => { ui.dragId = null; render(); },
      },
        h("div", { class: "kb-top" },
          h("div", { class: "kb-ttl" },
            h("h4", {}, app.url ? h("a", { href: app.url, target: "_blank", rel: "noopener noreferrer" }, app.title) : app.title),
            app.company && h("p", { class: "kb-co" }, app.company)),
          h("button", { class: "kb-more", type: "button", "aria-label": `Opções de ${app.title}`, "aria-haspopup": "menu",
            "aria-expanded": String(ui.menu === app.id),
            onclick: (e) => { e.stopPropagation(); ui.menu = ui.menu === app.id ? null : app.id; render(); if (ui.menu) root.querySelector(".kb-menu button")?.focus(); } },
            icon("dots", 16))),
        ui.menu === app.id && menu(app),
        h("div", { class: "kb-tags" },
          place && h("span", { class: "tag " + (app.workplace === "remoto" ? "" : "plain") }, place),
          app.grande && h("span", { class: "tag big" }, "Grande empresa")),
        !closed && nextLabel && h("p", { class: "kb-next" + (soon ? " is-soon" : "") }, icon("cal"), nextLabel),
        closed && h("p", { class: "kb-closed" + (won ? " is-good" : app.closedReason === "recusada" ? " is-bad" : "") }, icon(won ? "ok" : "x"),
          [C.reasonName(app.closedReason) || "Encerrada", app.stoppedAt && !won ? "parou em " + C.stageName(app.stoppedAt) : ""].filter(Boolean).join(", ")),
        app.note && h("p", { class: "kb-memo", title: app.note }, app.note),
        h("p", { class: "kb-age" }, age),
        h("div", { class: "kb-actions" },
          closed
            ? h("button", { class: "kb-btn small", type: "button", onclick: () => store.reopen(app.id) }, "Reabrir")
            : nxt && h("button", { class: "kb-advance", type: "button", onclick: () => store.move(app.id, nxt.id) }, "Avançar: " + nxt.short),
          h("button", { class: "kb-moveclose", type: "button", onclick: () => openMove(app) }, "Mover ou encerrar")));
    }

    function icon(kind, size = 14) {
      const paths = {
        cal: '<rect x="2" y="3" width="12" height="11" rx="2"/><path d="M2 7h12M5 1.5v3M11 1.5v3"/>',
        x: '<circle cx="8" cy="8" r="6.2"/><path d="M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4"/>',
        ok: '<circle cx="8" cy="8" r="6.2"/><path d="M5.2 8.2l2 2 3.6-4"/>',
        dots: '<g fill="currentColor" stroke="none"><circle cx="3" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="13" cy="8" r="1.5"/></g>',
      };
      const span = h("span", { class: "kb-ico", "aria-hidden": "true" });
      span.innerHTML = `<svg width="${size}" height="${size}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${paths[kind]}</svg>`;
      return span;
    }

    function menu(app) {
      const closed = app.stage === "encerrada";
      return h("div", { class: "kb-menu", role: "menu", "aria-label": "Opções da candidatura" },
        h("button", { role: "menuitem", type: "button", onclick: () => { ui.menu = null; openEdit(app); render(); } }, "Editar próximo passo e anotação"),
        closed
          ? h("button", { role: "menuitem", type: "button", onclick: act(() => store.reopen(app.id)) }, "Reabrir candidatura")
          : [h("p", { class: "kb-menu-label" }, "Encerrar candidatura como"),
             C.reasonsFor(app).map((r) => h("button", { role: "menuitem", type: "button", onclick: act(() => store.close(app.id, r.id)) }, r.name))],
        h("button", { role: "menuitem", type: "button", class: "danger", onclick: () => { ui.menu = null; openRemove(app); render(); } }, "Remover do quadro"));
    }

    /* ---------- coluna ---------- */
    function column(stage, apps) {
      const mine = apps.filter((a) => a.stage === stage.id);
      mine.sort(stage.id === "encerrada"
        ? (a, b) => b.updatedAt - a.updatedAt
        : (a, b) => (a.nextDate || "9999").localeCompare(b.nextDate || "9999") || b.updatedAt - a.updatedAt);
      const closing = stage.id === "encerrada";
      return h("section", {
        class: "kb-col" + (ui.stage === stage.id ? " is-active" : ""), "data-stage": stage.id, "aria-label": stage.name,
        ondragover: (e) => { if (!ui.dragId) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; e.currentTarget.classList.add("is-over"); },
        ondragleave: (e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.classList.remove("is-over"); },
        ondrop: (e) => {
          e.preventDefault();
          const id = e.dataTransfer.getData("text/plain") || ui.dragId;
          ui.dragId = null;
          const app = store.get(id);
          if (app && app.stage !== stage.id) {
            if (closing) { render(); openClose(app); return; }      // precisa do motivo
            store.move(id, stage.id);
          } else render();
        },
      },
        h("header", { class: "kb-col-head" },
          h("i", { class: "kb-dot", style: `background:${DOT[stage.id]}` }), h("h3", {}, stage.name), h("span", { class: "kb-count" }, mine.length)),
        h("div", { class: "kb-cards" },
          mine.map(card),
          !mine.length && h("p", { class: "kb-empty" }, closing ? "Nenhuma encerrada." : "Nenhuma candidatura aqui.")),
        h("div", { class: "kb-slot", "aria-hidden": "true" }, closing ? "Solte aqui para encerrar" : `Solte aqui para mover para ${stage.name}`));
    }

    /* ---------- sincronização e backup ---------- */
    const syncBox = h("div", { class: "kb-sync", "aria-live": "polite" });
    function paintSync() {
      const s = sync.status;
      const kids = [];
      if (s.mode === "local") kids.push(h("span", {}, sync.configured ? "Salvo neste navegador" : "Salvo neste navegador. Sincronização desligada."));
      if (s.mode === "connecting") kids.push(h("span", {}, "Conectando…"));
      if (s.mode === "signed-out") kids.push(h("span", {}, "Salvo neste navegador."),
        h("button", { class: "kb-btn", type: "button", onclick: () => sync.signIn() }, "Entrar com Google para sincronizar"));
      if (s.mode === "synced") kids.push(h("span", {}, "Sincronizado" + (s.user && s.user.email ? ` com ${s.user.email}` : "")),
        h("button", { class: "kb-link", type: "button", onclick: () => sync.signOut() }, "Sair"));
      if (s.mode === "error") kids.push(h("span", { class: "kb-err" }, "Sincronização: " + s.message));
      if (s.message && s.mode === "signed-out") kids.push(h("span", { class: "kb-err" }, s.message));
      syncBox.replaceChildren(...kids);
    }

    function download() {
      const blob = new Blob([store.exportJSON()], { type: "application/json" });
      const a = h("a", { href: URL.createObjectURL(blob), download: `candidaturas-${new Date().toISOString().slice(0, 10)}.json` });
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }
    const picker = h("input", { type: "file", accept: "application/json,.json", hidden: true, onchange: async (e) => {
      const file = e.target.files[0]; e.target.value = "";
      if (!file) return;
      try {
        const r = store.importJSON(await file.text());
        flash(`Backup lido: ${r.lidas} candidaturas, ${r.novas} novas.`);
      } catch (err) { flash("Esse arquivo não parece um backup de candidaturas."); }
    } });
    const flashBox = h("span", { class: "kb-flash", role: "status" });
    const flash = (msg) => { flashBox.textContent = msg; setTimeout(() => { if (flashBox.textContent === msg) flashBox.textContent = ""; }, 6000); };

    /* ---------- tela ---------- */
    function render() {
      const apps = store.all();
      const active = apps.filter((a) => a.stage !== "encerrada").length;
      const closed = apps.length - active;
      root.classList.remove("kb--dragging");
      root.replaceChildren(
        h("div", { class: "kb-head" },
          h("div", {}, h("h2", {}, "Minhas candidaturas"),
            h("p", { class: "kb-sub" }, apps.length ? `${active} em andamento, ${closed} ${closed === 1 ? "encerrada" : "encerradas"}` : "Nenhuma candidatura ainda. Marque uma vaga como candidatura ou adicione uma aqui.")),
          h("div", { class: "kb-tools" }, syncBox,
            h("button", { class: "kb-btn primary", type: "button", onclick: openAdd }, "Adicionar candidatura"))),
        h("div", { class: "kb-tabs", role: "group", "aria-label": "Etapas" }, C.STAGES.map((s) =>
          h("button", { class: "kb-chip", type: "button", "aria-pressed": String(ui.stage === s.id),
            onclick: () => { ui.stage = s.id; render(); } }, `${s.short} ${apps.filter((a) => a.stage === s.id).length}`))),
        h("div", { class: "kb-board" }, C.STAGES.map((s) => column(s, apps))),
        h("footer", { class: "kb-foot" },
          h("button", { class: "kb-link", type: "button", onclick: download }, "Baixar backup"),
          h("button", { class: "kb-link", type: "button", onclick: () => picker.click() }, "Importar backup"),
          picker, flashBox));
      paintSync();
    }

    document.addEventListener("click", (e) => { if (ui.menu && !e.target.closest(".kb-menu")) closeMenu(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && ui.menu) closeMenu(); });
    store.subscribe(() => render());
    sync.onStatus(paintSync);
    render();
    return { render };
  }

  window.Kanban = { mount };
})();
