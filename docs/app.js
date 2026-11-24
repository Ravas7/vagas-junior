/* Painel de vagas: lê data/jobs.json e filtra no navegador. Sem build, sem bibliotecas. */
(() => {
  "use strict";

  const WP = { remoto: "Remoto", hibrido: "Híbrido", presencial: "Presencial" };
  const SRC = {
    gupy: "Gupy", adzuna: "Adzuna", greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby",
    smartrecruiters: "SmartRecruiters", workday: "Workday", noticias: "Notícias",
  };
  const EN = { "": "Inglês não informado", basico: "Inglês básico", intermediario: "Inglês intermediário", avancado: "Inglês avançado" };
  const STORE = "vagas-junior:status:v1";
  const C = window.Candidaturas;
  const store = C.createStore({ storage: (() => { try { return window.localStorage; } catch { return null; } })() });
  const DAY = 86400000;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  const state = {
    jobs: [], meta: {}, sample: false, now: new Date(),
    status: readStatus(),            // id -> "saved" | "hidden" (candidaturas ficam em store.js)
    tab: "all", day: null,
  };

  function readStatus() {
    try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch { return {}; }
  }
  function writeStatus() {
    try { localStorage.setItem(STORE, JSON.stringify(state.status)); } catch { /* modo privado */ }
  }

  /* ---------- utilidades ---------- */
  const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const toDate = (iso) => new Date(iso + "T12:00:00");
  const pad = (n) => String(n).padStart(2, "0");
  const dm = (d) => `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
  const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  function h(tag, attrs = {}, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(kid));
    }
    return el;
  }

  function daysAgo(iso) {
    return Math.max(0, Math.round((startOfDay(state.now) - startOfDay(toDate(iso))) / DAY));
  }
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

  function ageLabel(job) {
    const iso = job.posted_at || job.first_seen;
    if (!iso) return "";
    const n = daysAgo(iso);
    const base = n === 0 ? "hoje" : n === 1 ? "ontem" : `há ${n} dias`;
    return job.posted_at ? `Publicada ${base}` : `Vista ${base}`;
  }
  const isNew = (job) => job.first_seen && daysAgo(job.first_seen) <= 1;
  const pipCount = (s) => (s >= 80 ? 5 : s >= 70 ? 4 : s >= 60 ? 3 : s >= 50 ? 2 : 1);

  /* ---------- dados ---------- */
  async function load() {
    const get = async (path) => {
      const r = await fetch(path + "?t=" + Date.now());
      if (!r.ok) throw new Error(path + " " + r.status);
      return r.json();
    };
    let data = { jobs: [], meta: {} };
    try { data = await get("data/jobs.json"); } catch (e) { console.warn(e); }
    if (!data.jobs.length) {
      try { data = await get("data/jobs.sample.json"); state.sample = true; } catch (e) { console.warn(e); }
    }
    state.jobs = data.jobs;
    state.meta = data.meta || {};
    state.now = state.sample ? new Date("2026-11-23T15:00:00-03:00") : new Date();
  }

  /* ---------- filtros ---------- */
  function filters() {
    return {
      q: norm($("#q").value).split(/\s+/).filter(Boolean),
      wp: $$('input[name="wp"]:checked').map((i) => i.value),
      uf: $("#uf").value, source: $("#source").value, sort: $("#sort").value,
      tipo: $("#tipo").value, area: $("#area").value, local: $("#local").value,
      onlyBig: $("#only-big").checked,
      onlyNew: $("#only-new").checked,
      closed: $("#show-closed").checked, hidden: $("#show-hidden").checked,
    };
  }

  function matches(job, f, ignoreTab = false) {
    const st = state.status[job.id] || "";
    if (!f.closed && !job.active) return false;
    if (f.tipo && (job.tipo || "vaga") !== f.tipo) return false;
    if (f.area && (job.area || "dev") !== f.area) return false;
    if (f.onlyBig && !job.grande) return false;
    if (f.local) {
      if (job.tipo === "noticia") return false;
      const remote = job.workplace === "remoto";
      if (f.local === "ssa" && remote) return false;
      if (f.local === "br" && !(remote && !job.abroad)) return false;
      if (f.local === "exterior" && !job.abroad) return false;
    }
    if (!f.hidden && st === "hidden") return false;
    if (!ignoreTab) {
      if (state.tab === "saved" && st !== "saved") return false;
    }
    if (f.wp.length && !f.wp.includes(job.workplace || "")) return false;
    if (f.uf && job.uf !== f.uf) return false;
    if (f.source && job.source !== f.source) return false;
    if (f.onlyNew && daysAgo(job.first_seen) > 7) return false;
    if (state.day && job.first_seen !== state.day) return false;
    if (f.q.length) {
      const hay = norm([job.title, job.company, job.location, job.snippet].join(" "));
      if (!f.q.every((w) => hay.includes(w))) return false;
    }
    return true;
  }

  /* ---------- desenho ---------- */
  function renderPulse() {
    const box = $("#pulse");
    box.replaceChildren();
    const today = startOfDay(state.now);
    const days = [...Array(14)].map((_, i) => new Date(today.getTime() - (13 - i) * DAY));
    const counts = Object.fromEntries(days.map((d) => [isoDay(d), 0]));
    for (const j of state.jobs) if (j.first_seen in counts && j.active) counts[j.first_seen]++;
    const max = Math.max(1, ...Object.values(counts));
    days.forEach((d, i) => {
      const key = isoDay(d), n = counts[key];
      const label = `${dm(d)}: ${n} ${n === 1 ? "vaga nova" : "vagas novas"}`;
      box.append(h("button", {
        class: "bar" + (i === 13 ? " today" : ""), type: "button", "data-n": n, title: label,
        "aria-label": label, "aria-pressed": String(state.day === key),
        onclick: () => { state.day = state.day === key ? null : key; renderPulse(); render(); },
      }, h("i", { style: `height:${Math.round((n / max) * 52)}px` }),
         h("small", {}, i % 3 === 0 || i === 13 ? pad(d.getDate()) : "")));
    });
  }

  function fillSelects() {
    const ufs = [...new Set(state.jobs.map((j) => j.uf).filter(Boolean))].sort();
    const srcs = [...new Set(state.jobs.map((j) => j.source))].sort();
    $("#uf").append(...ufs.map((u) => h("option", { value: u }, u)));
    $("#source").append(...srcs.map((s) => h("option", { value: s }, SRC[s] || s)));
  }

  function jobRow(job) {
    const st = state.status[job.id] || "";
    const app = store.get(job.id);
    const set = (value) => () => {
      state.status[job.id] = state.status[job.id] === value ? "" : value;
      if (!state.status[job.id]) delete state.status[job.id];
      writeStatus(); render();
    };
    const isNews = job.tipo === "noticia";
    const place = [isNews ? "" : WP[job.workplace], job.location].filter(Boolean)
      .filter((p, i, all) => all.findIndex((q) => norm(q) === norm(p)) === i);
    const company = isNews && job.company === "Empresa não identificada" ? "" : job.company;
    const n = pipCount(job.score);
    const why = (job.reasons || []).slice(1).join(", ");

    return h("article", {
      class: ["job", isNews && "is-news", isNew(job) && "is-new", st === "saved" && "is-saved", app && "is-applied", !job.active && "is-closed"]
        .filter(Boolean).join(" "),
    },
      h("div", {},
        h("h3", {}, h("a", { href: job.url, target: "_blank", rel: "noopener noreferrer" }, job.title)),
        h("p", { class: "where" }, company && h("b", {}, company),
          place.join(", ") || (isNews ? "" : "Local não informado")),
        h("div", { class: "tags" },
          isNew(job) && job.active && h("span", { class: "tag new" }, "Nova"),
          isNews && h("span", { class: "tag news" }, "Notícia"),
          job.grande && h("span", { class: "tag big" }, "Grande empresa"),
          job.area === "correlata" && h("span", { class: "tag area" }, "Área correlata"),
          job.area === "suporte" && h("span", { class: "tag support" }, "Suporte técnico"),
          job.abroad && h("span", { class: "tag abroad" }, "Remoto no exterior"),
          job.abroad && h("span", { class: "tag plain" }, EN[job.english || ""]),
          !job.abroad && job.english && h("span", { class: "tag plain" }, EN[job.english]),
          job.salary > 0 && h("span", { class: "tag money" }, "R$ " + job.salary.toLocaleString("pt-BR")),
          !job.active && !isNews && h("span", { class: "tag plain" }, "Encerrada"),
          app && h("span", { class: "tag" }, "Candidatura: " + C.stageName(app.stage)),
          !isNews && job.workplace && h("span", { class: "tag" }, WP[job.workplace]),
          !isNews && h("span", { class: "tag plain" }, SRC[job.source] || job.source),
          h("span", { class: "pips", role: "img", "aria-label": `Relevância ${n} de 5`, title: `Relevância ${n} de 5` },
            [1, 2, 3, 4, 5].map((i) => h("i", { class: i <= n ? "on" : "" })))),
      ),
      h("div", { class: "side" },
        h("span", { class: "age" }, ageLabel(job)),
        h("div", { class: "actions" },
          h("button", { class: "btn", type: "button", "aria-pressed": String(st === "saved"), onclick: set("saved") }, st === "saved" ? "Salva" : "Salvar"),
          !isNews && h("button", { class: "btn", type: "button", "aria-pressed": String(!!app), onclick: () => (app ? showTab("applied") : applyTo(job)) },
            app ? "Ver no quadro" : "Marcar candidatura"),
          h("button", { class: "btn quiet", type: "button", onclick: set("hidden") }, st === "hidden" ? "Mostrar de novo" : "Ocultar"))),
      (job.snippet || why) && h("details", { class: "more" },
        h("summary", {}, "Ver resumo"),
        job.snippet && h("p", {}, job.snippet),
        why && h("p", { class: "why" }, "Entrou porque: " + why)),
    );
  }

  function render() {
    const f = filters();
    const list = state.jobs.filter((j) => matches(j, f));
    list.sort(f.sort === "recent"
      ? (a, b) => (b.posted_at || b.first_seen).localeCompare(a.posted_at || a.first_seen) || b.score - a.score
      : (a, b) => b.score - a.score || b.first_seen.localeCompare(a.first_seen));

    const base = state.jobs.filter((j) => matches(j, f, true));
    $("#count-all").textContent = base.length;
    $("#count-saved").textContent = base.filter((j) => state.status[j.id] === "saved").length;
    countApplied();

    const box = $("#list");
    box.replaceChildren();
    const newCount = list.filter((j) => isNew(j) && j.active).length;
    $("#summary").textContent = list.length
      ? `${list.length} ${list.length === 1 ? "resultado" : "resultados"}${newCount ? `, ${newCount} de hoje ou ontem` : ""}`
      : "";

    if (!list.length) {
      const nothingYet = !state.jobs.length;
      box.append(h("div", { class: "empty" },
        h("h3", {}, nothingYet ? "Ainda não há vagas aqui" : "Nenhuma vaga com esses filtros"),
        h("p", {}, nothingYet
          ? "A primeira coleta ainda não rodou. Execute o fluxo “Buscar vagas” no GitHub Actions ou rode o comando abaixo no seu computador."
          : state.tab === "all" ? "Remova algum filtro ou escolha outro dia na faixa de cima." : "Use Salvar nas vagas para listá-las aqui."),
        nothingYet && h("code", {}, "python -m vagas run")));
    } else {
      box.append(...list.map(jobRow));
    }
  }

  function renderHeader() {
    const m = state.meta;
    const vagas = state.jobs.filter((j) => j.active && j.tipo !== "noticia").length;
    const noticias = state.jobs.filter((j) => j.tipo === "noticia").length;
    let when = "";
    if (m.updated_at) {
      const d = new Date(m.updated_at);
      when = `Atualizado em ${dm(d)} às ${pad(d.getHours())}:${pad(d.getMinutes())}. `;
    }
    $("#updated").textContent =
      `${when}${vagas} vagas abertas${noticias ? ` e ${noticias} notícias de processos seletivos` : ""}.`;

    const banner = $("#banner");
    if (state.sample) {
      banner.hidden = false;
      banner.textContent = "Você está vendo dados de exemplo. Quando a primeira coleta rodar, as vagas reais aparecem no lugar.";
    }

    const failed = Object.entries(m.sources || {}).filter(([, s]) => s.ok === false);
    const foot = $("#foot");
    foot.replaceChildren(
      "Vagas coletadas automaticamente de fontes públicas. Confira a vaga no site de origem antes de se candidatar. ",
      "Vagas salvas e ocultadas ficam só neste navegador. As candidaturas ficam no quadro e podem sincronizar entre aparelhos.",
      ...failed.map(([name, s]) => h("p", { class: "warn" },
        `A fonte ${SRC[name] || name} falhou na última coleta: ${s.error}`)));
  }

  /* ---------- eventos ---------- */
  function bind() {
    ["#q", "#uf", "#source", "#sort", "#tipo", "#area", "#local", "#only-big", "#only-new", "#show-closed", "#show-hidden"].forEach((s) =>
      $(s).addEventListener(s === "#q" ? "input" : "change", render));
    $$('input[name="wp"]').forEach((i) => i.addEventListener("change", render));
    $$(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
    $("#reset").addEventListener("click", () => {
      $("#q").value = ""; $("#uf").value = ""; $("#source").value = ""; $("#sort").value = "score";
      $("#tipo").value = ""; $("#area").value = ""; $("#local").value = "";
      $$('input[type="checkbox"]').forEach((c) => (c.checked = false));
      state.day = null; renderPulse(); render();
    });
    const toggle = $("#filters-toggle");
    toggle.addEventListener("click", () =>
      toggle.setAttribute("aria-expanded", String(toggle.getAttribute("aria-expanded") !== "true")));
  }

  /* ---------- candidaturas (quadro) ---------- */
  const countApplied = () => { $("#count-applied").textContent = store.all().filter((a) => a.stage !== "encerrada").length; };

  function applyTo(job) {
    store.add({ id: job.id, title: job.title, company: job.company, url: job.url, location: job.location,
      workplace: job.workplace, grande: job.grande, stage: "inscricao" });
  }

  function showTab(tab) {
    state.tab = tab;
    $$(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x.dataset.tab === tab)));
    const board = tab === "applied";
    $("#board").hidden = !board;
    $("#list").hidden = board;
    $("#summary").hidden = board;
    $(".layout").classList.toggle("board-mode", board);
    if (!board) render();
    window.scrollTo({ top: 0 });
  }

  load().then(() => {
    state.status = store.migrateLegacy(state.status, Object.fromEntries(state.jobs.map((j) => [j.id, j])));
    writeStatus();
    fillSelects(); bind(); renderHeader(); renderPulse(); render();
    window.Kanban.mount({ root: $("#board"), store, sync: window.Sync });
    store.subscribe(() => { countApplied(); if (state.tab !== "applied") render(); });
    window.Sync.init(store);
    countApplied();
  });
})();
