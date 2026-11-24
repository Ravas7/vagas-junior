"""Teste de ponta a ponta: fontes simuladas -> filtro -> JSON -> e-mail."""

import json

from vagas import emailer, runner
from vagas.models import Job
from vagas.sources import REGISTRY


def jobs_do_dia():
    mk = lambda i, t, **kw: Job(id=f"gupy:{i}", source="gupy", title=t, company=kw.pop("company", f"Empresa {i}"),
                                url=f"https://x/{i}", description=kw.pop("description", ""), **kw)
    return [
        mk(1, "Desenvolvedor Python Júnior", workplace="remoto", location="Remoto"),
        mk(2, "Desenvolvedor Java Sênior"),
        mk(3, "Analista Financeiro Jr"),
        mk(4, "Dev <script>alert(1)</script> Jr", company="A&B"),
    ]


CFG = {
    "storage": {"path": ""},
    "email": {"enabled": True, "max_per_email": 40, "min_score": 40},
    "filter": {"min_score": 40},
    "sources": {"gupy": {"enabled": True}},
}


def test_execucao_completa(monkeypatch, tmp_path):
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: jobs_do_dia())
    monkeypatch.setenv("EMAIL_USER", "eu@exemplo.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")
    monkeypatch.delenv("EMAIL_TO", raising=False)
    sent = []
    monkeypatch.setattr(emailer, "send", lambda msg, u, p, h, port: sent.append(msg))
    cfg = {**CFG, "storage": {"path": str(tmp_path / "jobs.json")}}

    assert runner.run(cfg) == 0
    assert len(sent) == 1
    msg = sent[0]
    assert msg["To"] == "eu@exemplo.com" and "2 vagas novas" in msg["Subject"]
    html = msg.get_body(("html",)).get_content()
    assert "Desenvolvedor Python Júnior" in html
    assert "<script>" not in html and "A&amp;B" in html          # HTML escapado

    saved = json.loads((tmp_path / "jobs.json").read_text(encoding="utf-8"))
    assert saved["meta"]["active"] == 2 and saved["meta"]["sources"]["gupy"]["ok"] is True
    assert all(j["notified"] for j in saved["jobs"])
    assert "description" not in saved["jobs"][0]

    # segunda execução: nada novo, nenhum e-mail
    assert runner.run(cfg) == 0
    assert len(sent) == 1


def test_falha_no_email_nao_perde_aviso(monkeypatch, tmp_path):
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: jobs_do_dia())
    monkeypatch.setenv("EMAIL_USER", "eu@exemplo.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")

    def quebra(*a, **k):
        raise OSError("sem rede")
    monkeypatch.setattr(emailer, "send", quebra)
    cfg = {**CFG, "storage": {"path": str(tmp_path / "jobs.json")}}
    assert runner.run(cfg) == 0
    saved = json.loads((tmp_path / "jobs.json").read_text(encoding="utf-8"))
    assert not any(j["notified"] for j in saved["jobs"])          # será reenviado na próxima

    sent = []
    monkeypatch.setattr(emailer, "send", lambda msg, u, p, h, port: sent.append(msg))
    assert runner.run(cfg) == 0 and len(sent) == 1


def test_todas_as_fontes_falham(monkeypatch, tmp_path):
    from vagas.http import SourceError

    def erro(cfg):
        raise SourceError("HTTP 404")
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", erro)
    cfg = {**CFG, "storage": {"path": str(tmp_path / "jobs.json")}}
    assert runner.run(cfg) == 1
    assert not (tmp_path / "jobs.json").exists()


def test_limite_de_vagas_por_email():
    jobs = [Job(id=f"g:{i}", source="gupy", title=f"Dev Jr {i}", company="X", url=f"https://x/{i}", score=50)
            for i in range(60)]
    msg = emailer.build_message(jobs, {"max_per_email": 40}, "https://painel", "a@b", "a@b", "23/11")
    body = msg.get_body(("html",)).get_content()
    assert body.count("https://x/") == 40 and "Mais 20 no painel" in body
    assert "60 vagas novas" in msg["Subject"]


def test_email_com_noticias_e_selos():
    vaga = Job(id="g:1", source="gupy", title="Analista de Dados Júnior", company="Itaú", url="https://v/1",
               score=70, area="correlata", grande=True, reasons=["área correlata no título", "júnior no título"])
    n = Job(id="n:1", source="noticias", title="Amazon abre processo seletivo", company="Amazon", url="https://n/1",
            location="via Exame", tipo="noticia", score=65, grande=True, posted_at="2026-11-23")
    msg = emailer.build_message([vaga, n], {}, "https://painel", "a@b", "a@b", "23/11")
    html = msg.get_body(("html",)).get_content()
    assert "1 vaga nova e 1 notícia de seleção" in msg["Subject"]
    assert "Processos seletivos nas notícias" in html and "grande empresa" in html and "área correlata" in html
    assert "via Exame" in html and "https://n/1" in html


def test_email_mostra_exterior_e_ingles():
    j = Job(id="g:9", source="greenhouse", title="Junior Backend Engineer", company="Acme", url="https://v/9",
            location="Remote - US", workplace="remoto", score=80, abroad=True, english="intermediario",
            reasons=["termo de dev no título", "júnior no título", "remoto"])
    msg = emailer.build_message([j], {}, "https://painel", "a@b", "a@b", "23/11")
    html = msg.get_body(("html",)).get_content()
    assert ">exterior<" in html and "inglês intermediário" in html
