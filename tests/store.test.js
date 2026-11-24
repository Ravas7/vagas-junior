// Testes das regras do kanban. Rode com: node --test tests/
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../docs/store.js");

const fake = () => {
  const data = {};
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = v; }, data };
};
const job = { id: "gupy:1", title: "Dev Python Jr", company: "Acme", url: "https://x/1", location: "Salvador, BA", workplace: "remoto", grande: true };

test("nova candidatura começa em Inscrição feita e guarda os dados da vaga", () => {
  const s = C.createStore({ storage: fake(), now: () => 1000 });
  const a = s.add({ ...job });
  assert.equal(a.stage, "inscricao");
  assert.equal(a.title, "Dev Python Jr");
  assert.equal(a.createdAt, 1000);
  assert.equal(s.all().length, 1);
});

test("adicionar a mesma vaga duas vezes não duplica", () => {
  const s = C.createStore({ storage: fake() });
  s.add({ ...job }); s.add({ ...job });
  assert.equal(s.all().length, 1);
});

test("mover limpa o prazo da etapa anterior e registra o histórico", () => {
  let t = 1000;
  const s = C.createStore({ storage: fake(), now: () => t });
  s.add({ ...job });
  t = 2000; s.update("gupy:1", { nextText: "Teste técnico", nextDate: "2026-11-27" });
  assert.equal(s.get("gupy:1").nextText, "Teste técnico");
  t = 3000; const a = s.move("gupy:1", "dinamica");
  assert.equal(a.stage, "dinamica");
  assert.equal(a.nextText, "");
  assert.equal(a.nextDate, "");
  assert.deepEqual(a.history.map((e) => e.stage), ["inscricao", "dinamica"]);
});

test("encerrar em qualquer etapa vai direto para Encerrada e guarda onde parou", () => {
  for (const stage of ["inscricao", "dinamica", "entrevista", "proposta"]) {
    const s = C.createStore({ storage: fake() });
    s.add({ ...job });
    if (stage !== "inscricao") s.move("gupy:1", stage);
    const a = s.close("gupy:1", "recusada");
    assert.equal(a.stage, "encerrada");
    assert.equal(a.stoppedAt, stage);
    assert.equal(a.closedReason, "recusada");
  }
});

test("encerrar de novo troca o motivo mas mantém onde parou", () => {
  const s = C.createStore({ storage: fake() });
  s.add({ ...job }); s.move("gupy:1", "entrevista");
  s.close("gupy:1", "sem_retorno");
  const a = s.close("gupy:1", "desisti");
  assert.equal(a.stoppedAt, "entrevista");
  assert.equal(a.closedReason, "desisti");
});

test("reabrir volta para a etapa em que parou", () => {
  const s = C.createStore({ storage: fake() });
  s.add({ ...job }); s.move("gupy:1", "entrevista"); s.close("gupy:1", "recusada");
  const a = s.reopen("gupy:1");
  assert.equal(a.stage, "entrevista");
  assert.equal(a.closedReason, "");
  assert.equal(a.stoppedAt, "");
});

test("arrastar uma encerrada para outra etapa também reabre", () => {
  const s = C.createStore({ storage: fake() });
  s.add({ ...job }); s.close("gupy:1", "recusada");
  const a = s.move("gupy:1", "dinamica");
  assert.equal(a.stage, "dinamica");
  assert.equal(a.closedReason, "");
});

test("motivo e etapa inválidos são recusados", () => {
  const s = C.createStore({ storage: fake() });
  s.add({ ...job });
  assert.throws(() => s.close("gupy:1", "qualquer"));
  assert.throws(() => s.move("gupy:1", "encerrada"));
  assert.throws(() => s.move("gupy:1", "nada"));
});

test("'Fui contratado' só é oferecido a partir da proposta", () => {
  const s = C.createStore({ storage: fake() });
  const a = s.add({ ...job });
  assert.ok(!C.reasonsFor(a).some((r) => r.id === "contratado"));
  const b = s.move("gupy:1", "proposta");
  assert.ok(C.reasonsFor(b).some((r) => r.id === "contratado"));
});

test("remover some da lista mas fica como marcador para sincronizar", () => {
  const s = C.createStore({ storage: fake() });
  s.add({ ...job }); s.remove("gupy:1");
  assert.equal(s.all().length, 0);
  assert.equal(s.getRaw("gupy:1").deleted, true);
  assert.equal(s.add({ ...job }).deleted, false);   // dá para marcar de novo depois
});

test("salva no armazenamento e recarrega", () => {
  const st = fake();
  const s1 = C.createStore({ storage: st });
  s1.add({ ...job }); s1.move("gupy:1", "entrevista");
  const s2 = C.createStore({ storage: st });
  assert.equal(s2.get("gupy:1").stage, "entrevista");
});

test("armazenamento corrompido não derruba o painel", () => {
  const st = fake(); st.setItem("vagas-junior:candidaturas:v1", "{isso não é json");
  assert.equal(C.createStore({ storage: st }).all().length, 0);
});

test("merge: vale a versão mais recente de cada candidatura", () => {
  let t = 1000;
  const s = C.createStore({ storage: fake(), now: () => t });
  s.add({ ...job }); s.add({ ...job, id: "gupy:2", title: "Outra" });
  const remote = [
    { ...s.get("gupy:1"), stage: "entrevista", updatedAt: 5000 },     // nuvem mais nova
    { ...s.get("gupy:2"), stage: "proposta", updatedAt: 10 },         // nuvem mais velha
    { ...job, id: "gupy:3", title: "Só na nuvem", updatedAt: 7 },     // só existe na nuvem
  ];
  const push = s.mergeRemote(remote);
  assert.equal(s.get("gupy:1").stage, "entrevista");
  assert.equal(s.get("gupy:2").stage, "inscricao");
  assert.ok(s.get("gupy:3"));
  assert.deepEqual(push.map((a) => a.id), ["gupy:2"]);   // a local mais nova volta para a nuvem
});

test("merge: o marcador de remoção também se espalha", () => {
  const s = C.createStore({ storage: fake(), now: () => 1000 });
  s.add({ ...job });
  s.mergeRemote([{ ...s.get("gupy:1"), deleted: true, updatedAt: 9000 }]);
  assert.equal(s.all().length, 0);
});

test("merge de dados da nuvem avisa quem está ouvindo, com a origem", () => {
  const s = C.createStore({ storage: fake() });
  const events = [];
  s.subscribe((e) => events.push(e));
  s.mergeRemote([{ ...job, updatedAt: 5 }]);
  s.add({ ...job, id: "gupy:9" });
  assert.deepEqual(events.map((e) => e.source), ["remote", "local"]);
});

test("backup: exportar e importar em outro aparelho", () => {
  const a = C.createStore({ storage: fake() });
  a.add({ ...job }); a.move("gupy:1", "dinamica"); a.close("gupy:1", "desisti");
  const text = a.exportJSON();
  const b = C.createStore({ storage: fake() });
  const r = b.importJSON(text);
  assert.equal(r.novas, 1);
  assert.equal(b.get("gupy:1").stoppedAt, "dinamica");
  assert.throws(() => b.importJSON('{"x":1}'));
});

test("migra 'applied' do painel antigo e mantém salvas e ocultadas", () => {
  const s = C.createStore({ storage: fake() });
  const rest = s.migrateLegacy(
    { "gupy:1": "applied", "gupy:2": "saved", "gupy:3": "hidden", "old:9": "applied" },
    { "gupy:1": { ...job } },
  );
  assert.deepEqual(rest, { "gupy:2": "saved", "gupy:3": "hidden" });
  assert.equal(s.get("gupy:1").title, "Dev Python Jr");
  assert.ok(s.get("old:9"));
});

test("normalize corrige dados estranhos", () => {
  const a = C.normalize({ id: "x", stage: "invalida", nextDate: "amanhã", note: 5 });
  assert.equal(a.stage, "inscricao");
  assert.equal(a.nextDate, "");
  assert.equal(a.note, "5");
  assert.equal(C.normalize({ id: "y", stage: "encerrada", stoppedAt: "encerrada" }).stoppedAt, "");
});
