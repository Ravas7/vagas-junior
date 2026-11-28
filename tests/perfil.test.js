// Regras puras do perfil (docs/perfil.js). Rode: node --test tests/perfil.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const P = require("../docs/perfil.js");

const opcoes = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "perfil-padrao.json"), "utf8"));
const padrao = P.normalize(opcoes.perfil);

test("perfil padrão (do config.toml) vira o formato do formulário", () => {
  assert.deepEqual(padrao.niveis, ["junior"]);
  // "correlata" do config vira as subáreas; sem hardware
  assert.deepEqual(padrao.areas, ["dev", "dados", "qa", "devops", "seguranca", "infra", "suporte"]);
  assert.equal(padrao.regiao_nome, "Salvador");
  assert.ok(padrao.cidades.includes("Camaçari"));
  assert.equal(padrao.exterior, true);
  assert.equal(padrao.ingles_max, "intermediario");
  assert.equal(padrao.suporte_salario_min, 3200);
  assert.equal(padrao.anos_max, 2);
  assert.deepEqual(P.validate(padrao), []);
});

test("opções do formulário batem com as listas do perfil.js", () => {
  assert.deepEqual(opcoes.niveis.map((n) => n.id), P.NIVEIS);
  assert.deepEqual(opcoes.areas.map((a) => a.id), P.SUBAREAS);
  assert.deepEqual(opcoes.correlatas, P.CORRELATAS);
  assert.ok(opcoes.tecnologias.includes("Python"));
});

test("normalize limpa o que veio errado", () => {
  const p = P.normalize({
    niveis: ["senior", "xyz", "estagio"], areas: ["hardware", "qa", "nada"], estado: "pe",
    cidades: [" Recife ", "Recife", ""], ingles_max: "fluente", anos_max: "-3",
    tecnologias: ["React"], so_minhas_techs: true,
  });
  assert.deepEqual(p.niveis, ["estagio", "senior"]);            // na ordem certa, sem lixo
  assert.deepEqual(p.areas, ["qa", "hardware"]);
  assert.equal(p.estado, "PE");
  assert.deepEqual(p.cidades, ["Recife"]);
  assert.equal(p.regiao_nome, "Recife");
  assert.equal(p.ingles_max, "intermediario");
  assert.equal(p.anos_max, 2);
  assert.equal(p.so_minhas_techs, true);
  assert.equal(P.normalize({ so_minhas_techs: true }).so_minhas_techs, false);   // sem tecnologias, não filtra
});

test("validate aponta o que falta", () => {
  const vazio = P.normalize({ presencial: false, remoto: false, exterior: false });
  const erros = P.validate(vazio);
  assert.equal(erros.length, 3);
  const semLugar = P.normalize({ niveis: ["junior"], areas: ["dev"], presencial: true });
  assert.match(P.validate(semLugar)[0], /escolha o seu estado/);
  const soCidade = P.normalize({ niveis: ["junior"], areas: ["dev"], cidades: ["Recife"] });
  assert.match(P.validate(soCidade)[0], /escolha o seu estado/);   // o estado filtra as notícias
  const soEstado = P.normalize({ niveis: ["junior"], areas: ["dev"], estado: "SP" });
  assert.deepEqual(P.validate(soEstado), []);
});

test("perfil salvo antes, com as cidades de Salvador e sem estado, ganha BA", () => {
  const antigo = P.normalize({ niveis: ["junior"], areas: ["dev"], cidades: ["Salvador", "Camaçari"], estado: "" }, padrao);
  assert.equal(antigo.estado, "BA");
  const outro = P.normalize({ niveis: ["junior"], areas: ["dev"], cidades: ["Recife"], estado: "" }, padrao);
  assert.equal(outro.estado, "");
});

test("summary resume em uma linha", () => {
  assert.equal(P.summary(padrao, opcoes), "júnior · Salvador, remoto, exterior");
  const amigo = P.normalize({ niveis: ["estagio", "junior"], areas: ["dev"], estado: "PE", remoto: true });
  assert.equal(P.summary(amigo, opcoes), "estágio, júnior · PE, remoto");
});

test("paridade: o JS decide igual ao Python em todas as vagas e perfis", () => {
  const fx = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "paridade.json"), "utf8"));
  let checked = 0;
  for (const [nome, perfil] of Object.entries(fx.perfis)) {
    fx.vagas.forEach((vaga, i) => {
      const [accepted, score, reasons] = fx.esperado[nome][i];
      const got = P.evaluate(vaga, perfil, opcoes);
      assert.deepEqual([got.accepted, got.score, got.reasons], [accepted, score, reasons],
        `perfil "${nome}", vaga "${vaga.title}" (${vaga.location || "sem local"}, ${vaga.workplace || "-"})`);
      checked++;
    });
  }
  assert.ok(checked > 3000, `poucas comparações: ${checked}`);
});

test("vaga antiga (sem os campos novos) e notícia passam como vieram", () => {
  const antiga = { id: "a", tipo: "vaga", title: "Dev Jr", score: 80, reasons: ["x"] };
  assert.deepEqual(P.evaluate(antiga, padrao, opcoes).score, 80);
  const noticia = { id: "n", tipo: "noticia", title: "Itaú abre trainee", score: 70, reasons: [] };
  assert.equal(P.evaluate(noticia, P.normalize({ niveis: ["senior"] }), opcoes).accepted, true);
});

test("paridade também com o perfil no formato salvo pelo formulário (normalize)", () => {
  const fx = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "paridade.json"), "utf8"));
  for (const nome of ["padrao", "recife_estado", "techs_filtro", "pleno_senior"]) {
    const perfil = P.normalize(fx.perfis[nome]);
    fx.vagas.forEach((vaga, i) => {
      const [accepted, score] = fx.esperado[nome][i];
      const got = P.evaluate(vaga, perfil, opcoes);
      assert.deepEqual([got.accepted, got.score], [accepted, score], `perfil "${nome}" normalizado, vaga "${vaga.title}"`);
    });
  }
});

test("aviso de vagas: padrão ligado, e-mail, a cada coleta; valores estranhos voltam ao padrão", () => {
  assert.deepEqual(P.normalize({}).aviso, { ativo: true, canal: "email", frequencia: "coleta", telegram_codigo: "" });
  assert.deepEqual(P.normalize({ aviso: { ativo: false, frequencia: "diario" } }).aviso,
    { ativo: false, canal: "email", frequencia: "diario", telegram_codigo: "" });
  assert.deepEqual(P.normalize({ aviso: { canal: "pombo", frequencia: "semanal", telegram_codigo: "a b<" } }).aviso,
    { ativo: true, canal: "email", frequencia: "coleta", telegram_codigo: "" });
  assert.equal(P.normalize({ aviso: { canal: "telegram", telegram_codigo: "Ab3dEf7hJk2m" } }).aviso.telegram_codigo, "Ab3dEf7hJk2m");
});

test("paridade dos freelas: o JS decide igual ao Python (evaluateFreela = evaluate_freela)", () => {
  const fx = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "paridade.json"), "utf8")).freelas;
  let checked = 0;
  for (const [nome, perfil] of Object.entries(fx.perfis)) {
    fx.itens.forEach((item, i) => {
      const got = P.evaluateFreela(item, perfil);
      assert.deepEqual([got.accepted, got.score, got.reasons], fx.esperado[nome][i], `perfil "${nome}", freela ${item.id}`);
      checked++;
    });
  }
  assert.ok(checked > 1000, `poucas comparações: ${checked}`);
});

test("freelas no perfil: padrão mostra tudo e não avisa; valores estranhos voltam ao padrão", () => {
  assert.deepEqual(P.normalize({}).freelas,
    { ver: true, nivel: "", orcamento_min: 0, propostas_max: 0, so_minhas_techs: false, avisar: false });
  assert.deepEqual(P.normalize({ freelas: { ver: false, nivel: "mestre", orcamento_min: "250", avisar: true } }).freelas,
    { ver: false, nivel: "", orcamento_min: 250, propostas_max: 0, so_minhas_techs: false, avisar: true });
});
