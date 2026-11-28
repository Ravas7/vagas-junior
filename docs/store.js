/* Candidaturas: dados e regras do kanban.
 * Sem dependências. Roda no navegador (window.Candidaturas) e no Node (testes em tests/store.test.js).
 * Cada candidatura é uma cópia dos dados da vaga mais a etapa em que está, então continua
 * no quadro mesmo depois que a vaga sai da lista de vagas abertas.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Candidaturas = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STAGES = [
    { id: "inscricao", name: "Inscrição feita", short: "Inscrição" },
    { id: "dinamica", name: "Dinâmica e testes", short: "Dinâmica" },
    { id: "entrevista", name: "Entrevista", short: "Entrevista" },
    { id: "proposta", name: "Proposta", short: "Proposta" },
    { id: "encerrada", name: "Encerrada", short: "Encerrada" },
  ];
  const ACTIVE = STAGES.filter((s) => s.id !== "encerrada");
  const REASONS = [
    { id: "recusada", name: "Recusada pela empresa" },
    { id: "sem_retorno", name: "Sem retorno" },
    { id: "desisti", name: "Desisti" },
    { id: "cancelada", name: "Vaga cancelada" },
    { id: "contratado", name: "Fui contratado" },   // só aparece a partir da proposta
  ];
  const HISTORY_MAX = 30;

  const isStage = (id) => STAGES.some((s) => s.id === id);
  const stageName = (id) => (STAGES.find((s) => s.id === id) || {}).name || id;
  const reasonName = (id) => (REASONS.find((r) => r.id === id) || {}).name || "";
  const reasonsFor = (app) => REASONS.filter((r) => r.id !== "contratado" || app.stage === "proposta");
  const str = (v) => (v == null ? "" : String(v)).trim();
  /** Só links http(s): "javascript:..." vindo de arquivo importado ou da nuvem viraria código ao clicar. */
  const safeUrl = (v) => (/^https?:\/\//i.test(str(v)) ? str(v) : "");

  /** Garante o formato certo, venha de onde vier (navegador, nuvem ou arquivo importado). */
  function normalize(raw) {
    raw = raw || {};
    const stage = isStage(raw.stage) ? raw.stage : "inscricao";
    const stopped = stage === "encerrada" && isStage(raw.stoppedAt) && raw.stoppedAt !== "encerrada" ? raw.stoppedAt : "";
    const date = str(raw.nextDate);
    return {
      id: str(raw.id),
      title: str(raw.title) || "Candidatura sem título",
      company: str(raw.company),
      url: safeUrl(raw.url),
      location: str(raw.location),
      workplace: str(raw.workplace),
      grande: !!raw.grande,
      stage,
      closedReason: stage === "encerrada" ? str(raw.closedReason) : "",
      stoppedAt: stopped,
      nextText: str(raw.nextText),
      nextDate: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : "",
      note: raw.note == null ? "" : String(raw.note),
      history: (Array.isArray(raw.history) ? raw.history : []).slice(-HISTORY_MAX)
        .map((e) => ({ stage: str(e && e.stage), reason: str(e && e.reason), at: Number(e && e.at) || 0 })),
      createdAt: Number(raw.createdAt) || 0,
      updatedAt: Number(raw.updatedAt) || 0,
      deleted: !!raw.deleted,
    };
  }

  function create(fields, now) {
    const t = now == null ? Date.now() : now;
    const stage = isStage(fields.stage) && fields.stage !== "encerrada" ? fields.stage : "inscricao";
    return normalize({
      ...fields,
      id: str(fields.id) || "manual:" + t + "-" + Math.random().toString(36).slice(2, 7),
      stage, closedReason: "", stoppedAt: "",
      createdAt: t, updatedAt: t,
      history: [{ stage, at: t }],
    });
  }

  function move(app, stage, now) {
    if (!isStage(stage) || stage === "encerrada") throw new Error("etapa inválida: " + stage);
    if (app.stage === stage) return app;
    return {
      ...app, stage, closedReason: "", stoppedAt: "",
      nextText: "", nextDate: "",              // o prazo era da etapa anterior
      updatedAt: now, history: [...app.history, { stage, reason: "", at: now }].slice(-HISTORY_MAX),
    };
  }

  function close(app, reason, now) {
    if (!REASONS.some((r) => r.id === reason)) throw new Error("motivo inválido: " + reason);
    const stoppedAt = app.stage === "encerrada" ? app.stoppedAt : app.stage;   // guarda onde parou
    return {
      ...app, stage: "encerrada", closedReason: reason, stoppedAt,
      nextText: "", nextDate: "",
      updatedAt: now, history: [...app.history, { stage: "encerrada", reason, at: now }].slice(-HISTORY_MAX),
    };
  }

  function reopen(app, now) {
    if (app.stage !== "encerrada") return app;
    const stage = app.stoppedAt && app.stoppedAt !== "encerrada" ? app.stoppedAt : "inscricao";
    return {
      ...app, stage, closedReason: "", stoppedAt: "",
      updatedAt: now, history: [...app.history, { stage, reason: "", at: now }].slice(-HISTORY_MAX),
    };
  }

  function update(app, patch, now) {
    const next = { ...app };
    for (const key of ["title", "company", "url", "nextText", "nextDate", "note"]) {
      if (key in patch) next[key] = patch[key];
    }
    return { ...normalize(next), updatedAt: now };
  }

  const remove = (app, now) => ({ ...app, deleted: true, updatedAt: now });

  /** Junta o que está no aparelho com o que veio da nuvem (ou de um backup): vale o mais recente de cada candidatura. */
  function mergeApps(local, remoteList) {
    const merged = { ...local };
    const remoteById = {};
    for (const raw of remoteList || []) {
      const r = normalize(raw);
      if (r.id && (!remoteById[r.id] || r.updatedAt >= remoteById[r.id].updatedAt)) remoteById[r.id] = r;
    }
    const changedLocal = [];
    for (const r of Object.values(remoteById)) {
      const l = merged[r.id];
      if (!l || r.updatedAt > l.updatedAt) { merged[r.id] = r; changedLocal.push(r.id); }
    }
    const toPush = Object.values(merged).filter((a) => {
      const r = remoteById[a.id];
      return !r || a.updatedAt > r.updatedAt;
    });
    return { merged, changedLocal, toPush };
  }

  function createStore(opts) {
    opts = opts || {};
    const storage = opts.storage || null;
    const key = opts.key || "vagas-junior:candidaturas:v1";
    const clock = opts.now || (() => Date.now());
    const listeners = new Set();
    let map = {};

    try {
      const saved = JSON.parse((storage && storage.getItem(key)) || "[]");
      for (const raw of Array.isArray(saved) ? saved : []) {
        const app = normalize(raw);
        if (app.id) map[app.id] = app;
      }
    } catch { /* arquivo corrompido: começa vazio */ }

    const persist = () => { try { if (storage) storage.setItem(key, JSON.stringify(Object.values(map))); } catch { /* modo privado */ } };
    const emit = (source, ids) => listeners.forEach((fn) => { try { fn({ source, ids }); } catch (e) { console.error(e); } });
    const put = (app) => { map[app.id] = app; persist(); emit("local", [app.id]); return app; };
    const change = (id, fn) => {
      const cur = map[id];
      if (!cur || cur.deleted) return null;
      const next = fn(cur, clock());
      return next === cur ? cur : put(next);
    };

    return {
      all: () => Object.values(map).filter((a) => !a.deleted),
      get: (id) => (map[id] && !map[id].deleted ? map[id] : null),
      getRaw: (id) => map[id] || null,
      add(fields) {
        const existing = map[fields.id];
        if (existing && !existing.deleted) return existing;
        return put(create(fields, clock()));
      },
      move: (id, stage) => change(id, (a, t) => move(a, stage, t)),
      close: (id, reason) => change(id, (a, t) => close(a, reason, t)),
      reopen: (id) => change(id, (a, t) => reopen(a, t)),
      update: (id, patch) => change(id, (a, t) => update(a, patch, t)),
      remove: (id) => change(id, (a, t) => remove(a, t)),

      /** Recebe candidaturas de fora e devolve as que precisam ser enviadas de volta. */
      mergeRemote(list, source) {
        const r = mergeApps(map, list);
        map = r.merged;
        if (r.changedLocal.length) { persist(); emit(source || "remote", r.changedLocal); }
        return r.toPush;
      },
      exportJSON: () => JSON.stringify({
        versao: 1, exportado_em: new Date(clock()).toISOString(), candidaturas: Object.values(map),
      }, null, 2),
      importJSON(text) {
        const data = JSON.parse(text);
        const list = Array.isArray(data) ? data : data.candidaturas;
        if (!Array.isArray(list)) throw new Error("arquivo sem candidaturas");
        const before = Object.keys(map).length;
        this.mergeRemote(list, "import");
        return { lidas: list.length, novas: Object.keys(map).length - before };
      },
      /** Candidaturas marcadas na versão antiga do painel (status "applied") viram cartões em "Inscrição feita". */
      migrateLegacy(status, jobsById) {
        const rest = { ...status };
        for (const [id, value] of Object.entries(status)) {
          if (value !== "applied") continue;
          const job = jobsById[id];
          this.add(job
            ? { id, title: job.title, company: job.company, url: job.url, location: job.location,
                workplace: job.workplace, grande: job.grande, stage: "inscricao" }
            : { id, title: "Vaga marcada antes do quadro existir", stage: "inscricao" });
          delete rest[id];
        }
        return rest;
      },
      subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    };
  }

  return {
    STAGES, ACTIVE, REASONS, isStage, stageName, reasonName, reasonsFor,
    normalize, create, move, close, reopen, update, remove, mergeApps, createStore,
  };
});
