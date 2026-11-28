/* Perfil de cada pessoa: que vagas ela quer ver.
 * Duas partes:
 *  1. Regras puras (normalizar, validar, resumir). Rodam no navegador (window.Perfil)
 *     e no Node (testes em tests/perfil.test.js). Sem dependências.
 *  2. A janela "Meu perfil" (só no navegador). Abre sozinha no primeiro login.
 * As chaves são as mesmas do Python (vagas/filters.py, PROFILE_DEFAULTS), porque o
 * mesmo perfil um dia vai servir para o e-mail de cada pessoa.
 * O perfil padrão e as opções vêm de perfil-padrao.json (python -m vagas perfil).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Perfil = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
    "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];
  const NIVEIS = ["estagio", "junior", "pleno", "senior"];
  const SUBAREAS = ["dev", "dados", "qa", "devops", "seguranca", "infra", "suporte", "hardware"];
  const CORRELATAS = ["dados", "qa", "devops", "seguranca", "infra"];
  const INGLES = ["basico", "intermediario", "qualquer"];
  const CANAIS = ["email", "telegram"];
  const FREQUENCIAS = ["coleta", "diario"];

  /* Freelas (campo "freelas"): mesmas chaves e regras de freela_prefs em vagas/filters.py */
  function freelas(f) {
    f = f && typeof f === "object" ? f : {};
    const num = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) && n > 0 ? n : 0; };
    return {
      ver: f.ver !== false,
      nivel: ["iniciante", "intermediario"].includes(f.nivel) ? f.nivel : "",
      orcamento_min: num(f.orcamento_min),
      propostas_max: num(f.propostas_max),
      so_minhas_techs: f.so_minhas_techs === true,
      avisar: f.avisar === true,
    };
  }

  /* Aviso de vagas novas (lido pelo robô em vagas/avisos.py, prefs). Padrão: ligado, e-mail, a cada coleta. */
  function aviso(a) {
    a = a && typeof a === "object" ? a : {};
    return {
      ativo: a.ativo !== false,
      canal: CANAIS.includes(a.canal) ? a.canal : "email",
      frequencia: FREQUENCIAS.includes(a.frequencia) ? a.frequencia : "coleta",
      telegram_codigo: /^[A-Za-z0-9]{6,32}$/.test(a.telegram_codigo || "") ? a.telegram_codigo : "",
    };
  }

  const list = (v) => (Array.isArray(v) ? v : []).map((x) => String(x).trim()).filter(Boolean);
  const unique = (a) => [...new Set(a)];
  const bool = (v, dflt) => (typeof v === "boolean" ? v : dflt);
  const int = (v, dflt) => { const n = Math.round(Number(v)); return Number.isFinite(n) && n >= 0 ? n : dflt; };

  /* Deixa o perfil num formato só: listas limpas, "correlata" vira as subáreas, números inteiros. */
  function normalize(p, base) {
    const d = base || {};
    p = { ...d, ...(p || {}) };
    let areas = list(p.areas);
    if (areas.includes("correlata")) areas = areas.filter((a) => a !== "correlata").concat(CORRELATAS);
    const cidades = unique(list(p.cidades));
    return {
      ...p,
      niveis: NIVEIS.filter((n) => list(p.niveis).includes(n)),
      areas: SUBAREAS.filter((a) => areas.includes(a)),
      estado: UFS.includes(String(p.estado || "").toUpperCase()) ? String(p.estado).toUpperCase()
        : d.estado && cidades.some((c) => (d.cidades || []).includes(c)) ? d.estado : "",
      cidades,
      regiao_nome: cidades.length ? (p.regiao_nome && cidades.some((c) => c === p.regiao_nome) ? p.regiao_nome : cidades[0]) : "",
      filtrar_local: true,
      presencial: bool(p.presencial, true),
      remoto: bool(p.remoto, true),
      exterior: bool(p.exterior, false),
      local_desconhecido: bool(p.local_desconhecido, false),
      ingles_max: INGLES.includes(p.ingles_max) ? p.ingles_max : "intermediario",
      anos_max: int(p.anos_max, 2),
      salario_min: int(p.salario_min, 0),
      sem_salario: bool(p.sem_salario, true),
      tecnologias: unique(list(p.tecnologias)),
      so_minhas_techs: bool(p.so_minhas_techs, false) && list(p.tecnologias).length > 0,
      estados_preferidos: list(p.estados_preferidos),
      bonus_remoto: int(p.bonus_remoto, 10),
      bonus_grande: int(p.bonus_grande, 10),
      bonus_tecnologia: int(p.bonus_tecnologia, 10),
      nota_minima: int(p.nota_minima, 40),
      aviso: aviso(p.aviso),
      freelas: freelas(p.freelas),
    };
  }

  /* Problemas que impedem salvar (lista vazia = tudo certo). */
  function validate(p) {
    const out = [];
    if (!p.niveis.length) out.push("Escolha pelo menos um nível.");
    if (!p.areas.length) out.push("Escolha pelo menos uma área.");
    if (!p.presencial && !p.remoto && !p.exterior) out.push("Escolha pelo menos um jeito de trabalhar: presencial, remoto ou exterior.");
    if (p.presencial && !p.estado) out.push("Para vagas presenciais, escolha o seu estado.");
    return out;
  }

  /* Frase curta para mostrar no topo do painel. */
  function summary(p, opts) {
    const nome = (id, arr) => ((arr || []).find((x) => x.id === id) || {}).nome || id;
    const niveis = p.niveis.map((n) => nome(n, opts && opts.niveis).toLowerCase());
    const onde = [];
    if (p.presencial) onde.push(p.cidades.length ? p.regiao_nome || p.cidades[0] : p.estado);
    if (p.remoto) onde.push("remoto");
    if (p.exterior) onde.push("exterior");
    return `${niveis.join(", ")} · ${onde.filter(Boolean).join(", ")}`;
  }

  /* ---------- filtro: a mesma conta de evaluate_profile (vagas/filters.py) ----------
   * Mudou lá? Mude aqui também. O teste de paridade (tests/perfil.test.js) compara os dois. */
  const norm = (s) => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
  const reCache = new Map();
  function termRegex(term) {
    if (!reCache.has(term)) {
      const esc = norm(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      reCache.set(term, new RegExp("(?<![a-z0-9])" + esc + "(?![a-z0-9])"));
    }
    return reCache.get(term);
  }
  const findTerm = (text, terms) => terms.find((t) => termRegex(t).test(text)) || null;
  const get = (o, k, d) => (o && o[k] !== undefined && o[k] !== null ? o[k] : d);

  function isAbroad(job, r) {
    const loc = norm(job.location);
    return !!(findTerm(loc, r.remote_block) && !findTerm(loc, r.remote_ok));
  }

  function locationCheck(job, p, r) {
    if (!get(p, "filtrar_local", true)) return [true, ""];
    const regiao = get(p, "regiao_nome", "");
    const notSsa = (t) => norm(t).split("el salvador").join("").split("san salvador").join("");
    const loc = notSsa(job.location);
    const where = job.location || "local não informado";
    if (job.workplace === "remoto" && get(p, "remoto", true)) {
      if (isAbroad(job, r)) {
        if (!get(p, "exterior", true)) return [false, `remoto restrito a outro país (${job.location})`];
        return [true, "remoto no exterior"];
      }
      return [true, "remoto"];
    }
    if (!get(p, "presencial", true)) return [false, `não é remota (${where})`];
    const cities = get(p, "cidades", []).map(norm);
    if (cities.length && (findTerm(loc, cities) || findTerm(notSsa(job.title), cities))) {
      return [true, regiao ? `região de ${regiao}` : "sua região"];
    }
    const estado = String(get(p, "estado", "") || "").toUpperCase();
    if (!cities.length && estado && job.uf === estado) {
      return [true, regiao ? `região de ${regiao}` : `seu estado (${estado})`];
    }
    if (!loc && get(p, "local_desconhecido", false)) return [true, "local não informado"];
    const fora = regiao ? `fora de ${regiao} e região`
      : estado && !cities.length ? `fora de ${estado}` : "fora das suas cidades";
    return [false, `${fora} (${where})`];
  }

  function levelCheck(area, nivel, niveis) {
    if (niveis.includes(nivel)) return true;
    if (nivel === "") return ["junior", "pleno", "senior"].some((n) => niveis.includes(n));
    return area === "suporte" && nivel === "pleno" && niveis.includes("junior");
  }

  /* Diz se a vaga combina com o perfil e dá a nota. `opts` = perfil-padrao.json.
   * Devolve { accepted, score, reasons, comuns }. */
  function evaluate(job, p, opts) {
    const r = opts.regras;
    if (job.tipo === "noticia") {
      const ok = { accepted: true, score: job.score || 0, reasons: job.reasons || [], comuns: [] };
      const ufs = job.ufs || [];                        // notícia antiga (sem ufs): passa
      if (!get(p, "filtrar_local", true) || job.workplace === "remoto" || !ufs.length) return ok;
      if (!get(p, "presencial", true)) return { accepted: false, score: 0, reasons: [`notícia de vaga local (${ufs.join(", ")})`], comuns: [] };
      const estado = String(get(p, "estado", "") || "").toUpperCase();
      if (!estado || ufs.includes(estado)) return ok;
      return { accepted: false, score: 0, reasons: [`notícia de outro estado (${ufs.join(", ")})`], comuns: [] };
    }
    // vaga gravada antes dos campos novos: vale o resultado de quando foi coletada
    if (job.nivel === undefined) return { accepted: true, score: job.score || 0, reasons: job.reasons || [], comuns: [], legacy: true };

    const area = job.area || "dev", nivel = job.nivel || "", english = job.english || "";
    const niveis = get(p, "niveis", ["junior"]);
    const no = (why) => ({ accepted: false, score: 0, reasons: [why], comuns: [] });

    const areas = get(p, "areas", ["dev", "correlata", "suporte"]);
    if (!areas.includes(area) && !areas.includes(job.subarea)) return no(`${r.area_nome[area]} fora do perfil`);
    const minhas = new Set(get(p, "tecnologias", []));
    const comuns = (job.techs || []).filter((t) => minhas.has(t));
    if (minhas.size && get(p, "so_minhas_techs", false) && !comuns.length) return no("não cita suas tecnologias");
    if (!levelCheck(area, nivel, niveis)) {
      return no(nivel ? `nível ${r.nivel_nome[nivel] || "não informado"} fora do perfil` : "nível não informado (perfil só de estágio)");
    }

    const [locOk, locReason] = locationCheck(job, p, r);
    if (!locOk) return no(locReason);
    const abroad = locReason === "remoto no exterior";

    const cap = get(p, "ingles_max", "intermediario");
    if (cap in r.english_rank && r.english_rank[english] > r.english_rank[cap]) {
      return no(`exige inglês ${english} (limite: ${cap})`);
    }

    const salary = job.salary || 0;
    const minimum = Math.trunc(Number(get(p, "salario_min", 0)) || 0);   // vale para qualquer área
    if (minimum) {
      if (salary <= 0 && !get(p, "sem_salario", true)) return no(`salário não informado (mínimo R$ ${minimum})`);
      if (salary > 0 && salary < minimum) return no(`paga R$ ${salary} (mínimo R$ ${minimum})`);
    }

    const techArea = area === "dev" || area === "correlata";
    const years = job.years || 0, maxYears = Math.trunc(Number(get(p, "anos_max", 0)) || 0);
    if (techArea && maxYears && years > maxYears && !job.junior_title) return no(`pede ${years} anos de experiência`);

    let score = { dev: 20, correlata: 10, suporte: 40, hardware: 40 }[area];
    const reasons = [{ dev: "termo de dev no título", correlata: "área correlata no título",
      suporte: "suporte técnico", hardware: "hardware e assistência técnica" }[area]];
    if (area === "suporte") {
      reasons.push(salary ? `salário R$ ${salary}` : "salário não informado");
    } else if (area === "hardware") {
      if (salary) reasons.push(`salário R$ ${salary}`);
    } else if (nivel && niveis.includes(nivel)) {
      score += 50;
      reasons.push(job.junior_title ? "júnior no título" : nivel === "estagio" ? "estágio" : `${r.nivel_nome[nivel]} no título`);
    } else if (!nivel && job.junior_desc && niveis.includes("junior")) {
      score += 20;
      reasons.push("júnior na descrição");
    }
    if (techArea && job.pouca_exp) { score += 5; reasons.push("aceita pouca experiência"); }
    if (techArea && maxYears && years > 0 && years <= maxYears) { score += 5; reasons.push(`pede até ${years} anos`); }
    if (techArea && maxYears && years > maxYears) { score -= 30; reasons.push(`pede ${years} anos (penalizado)`); }
    if (job.grande) { score += get(p, "bonus_grande", 10); reasons.push("grande empresa"); }
    if (comuns.length) { score += get(p, "bonus_tecnologia", 10); reasons.push("sua tecnologia: " + comuns.join(", ")); }
    if (job.workplace === "remoto") {
      score += get(p, "bonus_remoto", 10);
      reasons.push("remoto");
    } else if (locReason.startsWith("região de") || locReason.startsWith("seu estado") || locReason === "sua região") {
      score += 10;
      reasons.push(locReason);
    }
    if (abroad) reasons.push("no exterior");
    if (english) reasons.push(`inglês ${english}`);
    const preferred = new Set(get(p, "estados_preferidos", []).map((s) => s.toUpperCase()));
    if (job.uf && preferred.has(job.uf)) { score += 10; reasons.push(`estado preferido (${job.uf})`); }

    const accepted = score >= get(p, "nota_minima", 40);
    if (!accepted) reasons.push("nota abaixo do mínimo");
    return { accepted, score, reasons, comuns };
  }

  /* O freela combina com o perfil? A mesma conta de evaluate_freela (vagas/filters.py).
   * Orçamento ou propostas que o site não informa não tiram o projeto. */
  function evaluateFreela(job, p) {
    const fp = freelas(p && p.freelas);
    const no = (why) => ({ accepted: false, score: 0, reasons: [why], comuns: [] });
    if (!fp.ver) return no("você não quer ver freelas");
    if (fp.nivel === "iniciante" && job.nivel_freela !== "iniciante") return no("não é para iniciante");
    if (fp.nivel === "intermediario" && job.nivel_freela === "especialista") return no("pede especialista");
    const top = Math.max(job.orcamento_min || 0, job.orcamento_max || 0);
    if (fp.orcamento_min && top && !job.por_hora && top < fp.orcamento_min) return no(`orçamento abaixo de USD ${fp.orcamento_min}`);
    const bids = job.propostas == null ? -1 : job.propostas;
    if (fp.propostas_max && bids > fp.propostas_max) return no(`mais de ${fp.propostas_max} propostas`);
    const minhas = new Set((p && p.tecnologias) || []);
    const comuns = (job.techs || []).filter((t) => minhas.has(t));
    if (fp.so_minhas_techs && minhas.size && !comuns.length) return no("não cita suas tecnologias");
    const reasons = [...(job.reasons || [])];
    let score = job.score || 0;
    if (comuns.length) { score += 10; reasons.push("sua tecnologia: " + comuns.join(", ")); }
    return { accepted: true, score, reasons, comuns };
  }

  return { UFS, NIVEIS, SUBAREAS, CORRELATAS, normalize, validate, summary, evaluate, evaluateFreela, freelas, norm };
});

/* ---------------------------------------------------------------- janela (só navegador) */
(() => {
  "use strict";
  if (typeof document === "undefined" || !window.Perfil || !window.Sync) return;

  const P = window.Perfil;
  const Sync = window.Sync;
  const KEY = "ragas:perfil:v1:";
  const listeners = new Set();
  let opts = null, uid = null, dialog = null, firstTime = false;

  P.current = null;
  P.options = null;
  P.onChange = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
  P.open = (first = false) => open(first);
  P.loadOptions = () => options();

  const readCache = (id) => { try { return JSON.parse(localStorage.getItem(KEY + id)); } catch { return null; } };
  const writeCache = (id, p) => { try { localStorage.setItem(KEY + id, JSON.stringify(p)); } catch { /* modo privado */ } };

  function setCurrent(p) {
    P.current = p;
    listeners.forEach((fn) => { try { fn(p); } catch (e) { console.error(e); } });
  }

  async function options() {
    if (opts) return opts;
    const r = await fetch("perfil-padrao.json?t=" + Date.now());
    if (!r.ok) throw new Error("perfil-padrao.json " + r.status);
    opts = await r.json();
    P.options = opts;
    return opts;
  }

  /* quando alguém entra: usa o perfil guardado aqui, confere o da nuvem; sem nenhum, abre o formulário */
  Sync.onStatus(async (s) => {
    const id = s.user && Sync.hasAccess() ? s.user.uid : null;      // sem acesso liberado: nada de perfil
    if (id === uid) return;
    uid = id || null;
    if (!uid) { setCurrent(null); return; }
    const cached = readCache(uid);
    if (cached) setCurrent(cached);
    let remote = null;
    try { remote = await Sync.loadProfile(); } catch (e) { console.warn("perfil na nuvem:", e); }
    if (uid !== id) return;                                // trocou de conta no meio
    if (remote && (!cached || (remote.updatedAt || "") >= (cached.updatedAt || ""))) {
      writeCache(uid, remote);
      setCurrent(remote);
    } else if (!cached) {
      open(true);
    }
  });

  /* ---------- montagem do formulário ---------- */
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
  const chip = (name, value, label, checked) =>
    h("label", { class: "pf-chip" }, h("input", { type: "checkbox", name, value, checked }), h("span", {}, label));
  const radio = (name, value, label, checked, disabled = false) =>
    h("label", { class: "pf-chip" + (disabled ? " is-off" : "") },
      h("input", { type: "radio", name, value, checked, disabled }), h("span", {}, label));
  const check = (name, label, checked, hint) =>
    h("label", { class: "check pf-check" }, h("input", { type: "checkbox", name, checked }),
      h("span", {}, label, hint && h("small", {}, hint)));

  async function open(first) {
    let o;
    try { o = await options(); } catch (e) {
      console.warn(e);
      alert("Não deu para abrir o perfil agora. Recarregue a página e tente de novo.");
      return;
    }
    firstTime = !!first;
    const base = P.normalize(o.perfil);
    const p = P.normalize(P.current || o.perfil, base);
    if (!dialog) {
      dialog = h("dialog", { class: "kb-dialog pf-dialog", "aria-labelledby": "pf-title" });
      dialog.addEventListener("cancel", (e) => { if (firstTime) e.preventDefault(); });   // 1ª vez: precisa salvar
      document.body.append(dialog);
    }
    dialog.replaceChildren(form(p, o));
    if (!dialog.open) dialog.showModal();
    refresh(dialog.querySelector("form"));
  }

  function form(p, o) {
    const has = (arr, v) => arr.includes(v);
    const f = h("form", { class: "kb-form pf-form", novalidate: true, onsubmit: save, oninput: (e) => refresh(e.currentTarget) },
      h("header", { class: "pf-head" },
        h("h2", { id: "pf-title" }, firstTime ? "Monte seu perfil" : "Meu perfil"),
        h("p", { class: "kb-dialog-sub" }, firstTime
          ? "Leva um minuto. O painel mostra só as vagas que combinam com você. Dá para mudar depois em “Meu perfil”."
          : "O painel mostra só as vagas que combinam com estas escolhas.")),

      h("fieldset", { class: "pf-sec" }, h("legend", {}, "Que vagas você quer?"),
        h("p", { class: "pf-label" }, "Nível"),
        h("div", { class: "pf-chips" }, o.niveis.map((n) => chip("niveis", n.id, n.nome[0].toUpperCase() + n.nome.slice(1), has(p.niveis, n.id)))),
        h("p", { class: "pf-label" }, "Áreas"),
        h("div", { class: "pf-chips" }, o.areas.map((a) => chip("areas", a.id, a.nome, has(p.areas, a.id)))),
        h("label", { class: "pf-inline" }, h("span", {}, "Experiência que você tem para mostrar"),
          h("select", { name: "anos_max" },
            [[1, "Até 1 ano pedido"], [2, "Até 2 anos pedidos"], [3, "Até 3 anos pedidos"], [5, "Até 5 anos pedidos"], [0, "Não importa"]]
              .map(([v, t]) => h("option", { value: v, selected: p.anos_max === v }, t)))),
        h("p", { class: "pf-hint" }, "Vagas que pedem mais anos de experiência ficam de fora, a não ser que digam júnior no título."),
        h("label", { class: "pf-inline" }, h("span", {}, "Salário mínimo (R$ por mês)"),
          h("input", { name: "salario_min", type: "number", min: 0, step: 100, inputmode: "numeric", value: p.salario_min || "",
            placeholder: "Sem mínimo" })),
        check("sem_salario", "Mostrar também vagas sem salário informado", p.sem_salario,
          "A maioria das vagas não informa o salário. Desligado, só aparecem as que dizem quanto pagam.")),

      h("fieldset", { class: "pf-sec" }, h("legend", {}, "Onde?"),
        check("presencial", "Presencial ou híbrido", p.presencial),
        h("div", { class: "pf-where", "data-show": "presencial" },
          h("label", {}, h("span", {}, "Estado"),
            h("select", { name: "estado" }, h("option", { value: "" }, "Escolha"),
              P.UFS.map((uf) => h("option", { value: uf, selected: p.estado === uf }, uf)))),
          h("label", { class: "pf-grow" }, h("span", {}, "Cidades (separe por vírgula)"),
            h("input", { name: "cidades", value: p.cidades.join(", "), placeholder: "Vazio = o estado todo", autocomplete: "off" })),
          h("p", { class: "pf-hint pf-full" }, "O estado também filtra as notícias de vagas: notícias de outros estados ficam de fora, menos as de vaga remota."),
          h("button", { class: "link-btn pf-suggest", type: "button", "data-show-uf": "BA",
            onclick: (e) => { const i = e.currentTarget.form.cidades; i.value = o.cidades_padrao.join(", "); refresh(e.currentTarget.form); } },
            "Usar Salvador e região metropolitana")),
        check("remoto", "Remoto no Brasil", p.remoto),
        check("exterior", "Remoto de empresa de fora do Brasil", p.exterior),
        h("label", { class: "pf-inline", "data-show": "exterior" }, h("span", {}, "Seu inglês"),
          h("select", { name: "ingles_max" },
            [["basico", "Básico"], ["intermediario", "Intermediário"], ["qualquer", "Avançado ou fluente"]]
              .map(([v, t]) => h("option", { value: v, selected: p.ingles_max === v }, t)))),
        check("local_desconhecido", "Mostrar vagas sem local informado", p.local_desconhecido,
          "Muitas vagas não dizem onde são. Ligado, elas aparecem também.")),

      h("fieldset", { class: "pf-sec" }, h("legend", {}, "Tecnologias que você usa"),
        h("p", { class: "pf-hint" }, "Vagas que citam uma delas sobem na lista e ganham destaque."),
        h("div", { class: "pf-chips" }, o.tecnologias.map((t) => chip("tecnologias", t, t, has(p.tecnologias, t)))),
        check("so_minhas_techs", "Mostrar só vagas que citam uma das minhas tecnologias", p.so_minhas_techs,
          "Cuidado: muitas vagas júnior não citam a tecnologia.")),

      h("fieldset", { class: "pf-sec" }, h("legend", {}, "Freelas"),
        check("fr_ver", "Mostrar freelas (projetos avulsos) no painel", p.freelas.ver,
          "Projetos da Workana e do 99Freelas, numa aba própria."),
        h("div", { "data-show": "freelas" },
          h("label", { class: "pf-inline" }, h("span", {}, "Nível pedido"),
            h("select", { name: "fr_nivel" },
              [["", "Todos"], ["iniciante", "Só para iniciante"], ["intermediario", "Até intermediário"]]
                .map(([v, t]) => h("option", { value: v, selected: p.freelas.nivel === v }, t)))),
          h("label", { class: "pf-inline" }, h("span", {}, "Orçamento mínimo"),
            h("select", { name: "fr_orcamento" },
              [[0, "Qualquer um"], [50, "USD 50"], [100, "USD 100"], [250, "USD 250"], [500, "USD 500"]]
                .map(([v, t]) => h("option", { value: v, selected: p.freelas.orcamento_min === v }, t)))),
          h("label", { class: "pf-inline" }, h("span", {}, "Concorrência"),
            h("select", { name: "fr_propostas" },
              [[0, "Qualquer número de propostas"], [10, "Até 10 propostas"], [30, "Até 30 propostas"], [50, "Até 50 propostas"]]
                .map(([v, t]) => h("option", { value: v, selected: p.freelas.propostas_max === v }, t)))),
          h("p", { class: "pf-hint" }, "Projetos que não informam orçamento ou propostas continuam aparecendo."),
          check("fr_techs", "Só os que citam minhas tecnologias", p.freelas.so_minhas_techs),
          check("fr_avisar", "Me avisar de freelas novos", p.freelas.avisar,
            "Até 5 por aviso, junto com as vagas, pelo mesmo canal escolhido abaixo."))),

      h("fieldset", { class: "pf-sec" }, h("legend", {}, "Avisos de vagas novas"),
        check("aviso_ativo", "Me avisar quando chegar vaga que combina comigo", p.aviso.ativo,
          "O robô procura vagas duas vezes por dia. Se nada combinar, você não recebe nada."),
        h("div", { "data-show": "aviso" },
          h("p", { class: "pf-label" }, "Por onde"),
          h("div", { class: "pf-chips" },
            radio("aviso_canal", "email", "E-mail", p.aviso.canal === "email"),
            o.telegram_bot ? radio("aviso_canal", "telegram", "Telegram", p.aviso.canal === "telegram")
              : radio("aviso_canal", "telegram", "Telegram (em breve)", false, true)),
          o.telegram_bot && telegramBox(p, o),
          h("p", { class: "pf-label" }, "Com que frequência"),
          h("div", { class: "pf-chips" },
            radio("aviso_frequencia", "coleta", "A cada coleta", p.aviso.frequencia === "coleta"),
            radio("aviso_frequencia", "diario", "Resumo diário", p.aviso.frequencia === "diario")),
          h("p", { class: "pf-hint" }, "A cada coleta: duas vezes por dia, só o que for novo. Resumo diário: um aviso só, no fim do dia, com as vagas do dia."))),

      h("p", { class: "gate-msg is-err pf-errors", role: "alert" }),
      h("div", { class: "kb-dialog-actions pf-actions" },
        !firstTime && h("button", { class: "kb-btn", type: "button", onclick: () => dialog.close() }, "Cancelar"),
        h("button", { class: "kb-btn primary", type: "submit" }, "Salvar perfil")));
    return f;
  }

  /* código que liga a conversa do Telegram a esta conta (o robô procura "/start <código>") */
  function newCode() {
    const abc = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
    const r = crypto.getRandomValues(new Uint8Array(12));
    return [...r].map((n) => abc[n % abc.length]).join("");
  }

  function telegramBox(p, o) {
    const code = p.aviso.telegram_codigo || newCode();
    const status = h("p", { class: "pf-tg-status" }, "Conferindo…");
    const box = h("div", { class: "pf-tg", "data-show": "telegram" },
      h("input", { type: "hidden", name: "aviso_codigo", value: code }),
      status,
      h("a", { class: "kb-btn primary pf-tg-btn", href: `https://t.me/${o.telegram_bot}?start=${code}`, target: "_blank", rel: "noopener",
        onclick: (e) => { const f = e.currentTarget.closest("form"); setTimeout(() => f.requestSubmit(), 0); } },
        "Abrir o Telegram"),
      h("p", { class: "pf-hint pf-tg-hint" }, "No Telegram, toque em Começar. O robô liga a conversa na próxima coleta e manda um “Pronto!”. Até lá, os avisos chegam por e-mail."));
    Sync.loadTelegram().then((t) => {
      const ok = t && t.codigo === code;
      status.textContent = ok ? `✓ Ligado ao Telegram${t.nome_telegram ? " (" + t.nome_telegram + ")" : ""}` : "Ainda não ligado.";
      status.classList.toggle("is-ok", !!ok);
      if (ok) {
        box.querySelector(".pf-tg-btn").textContent = "Abrir a conversa";
        box.querySelector(".pf-tg-hint").textContent = "Tudo certo: os avisos chegam por lá.";
      }
    }).catch(() => { status.textContent = "Ainda não ligado."; });
    return box;
  }

  function read(f) {
    const vals = (name) => [...f.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value);
    const on = (name) => f.elements[name].checked;
    return {
      ...(P.current || {}),
      niveis: vals("niveis"), areas: vals("areas"),
      presencial: on("presencial"), remoto: on("remoto"), exterior: on("exterior"),
      local_desconhecido: on("local_desconhecido"),
      estado: f.elements.estado.value,
      cidades: f.elements.cidades.value.split(",").map((c) => c.trim()).filter(Boolean),
      ingles_max: f.elements.ingles_max.value,
      anos_max: Number(f.elements.anos_max.value),
      salario_min: Number(f.elements.salario_min.value || 0),
      sem_salario: on("sem_salario"),
      tecnologias: vals("tecnologias"),
      so_minhas_techs: on("so_minhas_techs"),
      aviso: {
        ativo: on("aviso_ativo"),
        canal: (f.querySelector('input[name="aviso_canal"]:checked') || {}).value || "email",
        frequencia: (f.querySelector('input[name="aviso_frequencia"]:checked') || {}).value || "coleta",
        telegram_codigo: f.elements.aviso_codigo ? f.elements.aviso_codigo.value : (P.current && P.current.aviso || {}).telegram_codigo || "",
      },
      freelas: {
        ver: on("fr_ver"),
        nivel: f.elements.fr_nivel.value,
        orcamento_min: Number(f.elements.fr_orcamento.value) || 0,
        propostas_max: Number(f.elements.fr_propostas.value) || 0,
        so_minhas_techs: on("fr_techs"),
        avisar: on("fr_avisar"),
      },
    };
  }

  /* mostra só as partes que fazem sentido com o que está marcado */
  function refresh(f) {
    if (!f) return;
    const showIf = (sel, cond) => f.querySelectorAll(sel).forEach((el) => { el.hidden = !cond; });
    showIf('[data-show="presencial"]', f.elements.presencial.checked);
    showIf('[data-show="exterior"]', f.elements.exterior.checked);
    showIf('[data-show="aviso"]', f.elements.aviso_ativo.checked);
    showIf('[data-show="freelas"]', f.elements.fr_ver.checked);
    showIf('[data-show="telegram"]', !!f.querySelector('input[name="aviso_canal"][value="telegram"]:checked:not(:disabled)'));
    showIf('[data-show-uf="BA"]', f.elements.estado.value === "BA");
    f.querySelector(".pf-errors").textContent = "";
  }

  async function save(e) {
    e.preventDefault();
    const f = e.currentTarget;
    const p = P.normalize(read(f), P.normalize(opts.perfil));
    const problems = P.validate(p);
    if (problems.length) {
      const box = f.querySelector(".pf-errors");
      box.textContent = problems.join(" ");
      box.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    p.updatedAt = new Date().toISOString();
    const btn = f.querySelector('[type="submit"]');
    btn.disabled = true; btn.textContent = "Salvando…";
    if (uid) writeCache(uid, p);
    setCurrent(p);
    try {
      await Sync.saveProfile(p);
    } catch (err) {
      console.warn(err);
      // fica salvo neste navegador; a nuvem tenta de novo na próxima vez que salvar
      alert("Seu perfil ficou salvo neste aparelho, mas não foi para a nuvem: " + Sync.authMessage(err));
    }
    firstTime = false;
    dialog.close();
  }
})();
