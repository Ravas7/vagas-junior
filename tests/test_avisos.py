"""Aviso de vagas novas por pessoa (sem internet: Firebase e e-mail simulados)."""

from datetime import datetime

from vagas import avisos, emailer, filters, runner
from vagas.firebase import Recipient
from vagas.models import Job
from vagas.sources import REGISTRY

TODAY = "2026-11-27"
PADRAO = filters.profile_from_config({"location_filter": True, "state": "BA"})


def vaga(i, title, nivel, **kw):
    base = dict(id=f"g:{i}", source="gupy", title=title, company=f"Empresa {i}", url=f"https://x/{i}",
                workplace="remoto", nivel=nivel, junior_title=nivel == "junior", first_seen=TODAY, active=True)
    base.update(kw)
    return Job(**base)


JOBS = [
    vaga(1, "Desenvolvedor Python Jr", "junior"),
    vaga(2, "Desenvolvedor Java Pleno", "pleno"),
    vaga(3, "Estágio em Desenvolvimento de Software", "estagio"),
    vaga(4, "Desenvolvedor Jr antigo", "junior", first_seen="2026-11-26"),
]
EU = Recipient("u1", "eu@x.com", "Pedro Monteiro", {**PADRAO})
AMIGA = Recipient("u2", "amiga@x.com", "Emily Camile", {**PADRAO, "niveis": ["estagio"]})


def test_padroes_do_aviso():
    assert avisos.prefs(None) == {"ativo": True, "canal": "email", "frequencia": "coleta"}
    assert avisos.prefs({"aviso": {"ativo": False}})["ativo"] is False


def test_cada_um_recebe_so_o_que_combina_com_o_proprio_perfil():
    plans = avisos.plan([EU, AMIGA], JOBS, {"g:1", "g:2", "g:3"}, TODAY, evening=False)
    got = {pl.person.uid: [j.id for j in pl.jobs] for pl in plans}
    assert got == {"u1": ["g:1"], "u2": ["g:3"]}         # júnior para mim, estágio para ela; pleno para ninguém


def test_nota_do_aviso_e_a_do_perfil_da_pessoa():
    [pl] = avisos.plan([AMIGA], JOBS, {"g:3"}, TODAY, evening=False)
    assert pl.jobs[0].score > 0 and "estágio" in pl.jobs[0].reasons


def test_desligado_ou_sem_perfil_nao_recebe():
    desligado = Recipient("u3", "a@x.com", "A", {**PADRAO, "aviso": {"ativo": False}})
    sem_perfil = Recipient("u4", "b@x.com", "B", None)
    assert avisos.plan([desligado, sem_perfil], JOBS, {"g:1"}, TODAY, evening=True) == []


def tg(code="ABC12345", link_code="ABC12345", chat=777):
    extra = {"telegram": {"chat_id": chat, "codigo": link_code}} if link_code else {}
    return Recipient("u5", "c@x.com", "Caio", {**PADRAO, "aviso": {"canal": "telegram", "telegram_codigo": code}}, extra)


def test_telegram_ligado_recebe_pelo_telegram():
    [pl] = avisos.plan([tg()], JOBS, {"g:1"}, TODAY, evening=False)
    assert (pl.channel, pl.chat_id) == ("telegram", 777)


def test_telegram_nao_ligado_ou_bot_fora_vai_por_email():
    for p, on in ((tg(link_code=None), True), (tg(link_code="VELHO123"), True), (tg(), False)):
        [pl] = avisos.plan([p], JOBS, {"g:1"}, TODAY, evening=False, telegram_on=on)
        assert pl.channel == "email" and pl.chat_id is None


def test_resumo_diario_so_a_noite_e_com_tudo_do_dia():
    diario = Recipient("u6", "d@x.com", "D", {**PADRAO, "aviso": {"frequencia": "diario"}})
    assert avisos.plan([diario], JOBS, {"g:1"}, TODAY, evening=False) == []
    [pl] = avisos.plan([diario], JOBS, set(), TODAY, evening=True)      # nada novo agora, mas o dia teve g:1
    assert [j.id for j in pl.jobs] == ["g:1"] and pl.kind == "diario"


def test_quem_ja_recebe_pelo_perfil_nao_recebe_o_email_do_config():
    assert avisos.covers([EU], "EU@x.com")
    assert not avisos.covers([EU], "outro@x.com")
    assert not avisos.covers(None, "eu@x.com")
    assert avisos.covers([Recipient("u1", "eu@x.com", "Eu", {**PADRAO, "aviso": {"canal": "telegram"}})], "eu@x.com")


def test_aviso_tem_saudacao_e_rodape():
    msg = emailer.build_message(JOBS[:1], {}, "https://painel", "robo@x.com", "amiga@x.com", "27/11",
                                greeting=avisos.greeting(AMIGA, "coleta"), footer=avisos.FOOTER)
    html = msg.get_body(("html",)).get_content()
    assert "Olá, Emily!" in html and "Meu perfil" in html and msg["To"] == "amiga@x.com"


def test_coleta_completa_manda_um_aviso_por_pessoa_e_nao_duplica_o_meu(monkeypatch, tmp_path):
    fetched = [Job(id="gupy:1", source="gupy", title="Desenvolvedor Python Júnior", company="A", url="https://x/1",
                   workplace="remoto"),
               Job(id="gupy:2", source="gupy", title="Estágio em Desenvolvimento de Software", company="B",
                   url="https://x/2", workplace="remoto")]
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: [j for j in fetched])
    monkeypatch.setattr(runner, "load_people", lambda: [EU, AMIGA])
    monkeypatch.setenv("EMAIL_USER", "eu@x.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")
    monkeypatch.delenv("EMAIL_TO", raising=False)
    sent = []
    monkeypatch.setattr(emailer, "send", lambda msg, u, p, h, port: sent.append(msg))
    cfg = {"storage": {"path": str(tmp_path / "jobs.json")}, "email": {"enabled": True},
           "filter": {"location_filter": True, "state": "BA", "max_age_days": 0}, "sources": {"gupy": {"enabled": True}}}

    assert runner.run(cfg) == 0
    to = sorted(m["To"] for m in sent)
    assert to == ["amiga@x.com", "eu@x.com"]                 # um por pessoa; o do config.toml não saiu de novo
    mine = next(m for m in sent if m["To"] == "eu@x.com").get_body(("html",)).get_content()
    hers = next(m for m in sent if m["To"] == "amiga@x.com").get_body(("html",)).get_content()
    assert "Python Júnior" in mine and "Estágio" not in mine
    assert "Estágio" in hers and "Python Júnior" not in hers

    sent.clear()
    assert runner.run(cfg) == 0                               # nada novo: ninguém recebe
    assert sent == []


def test_sem_firebase_volta_o_email_do_config(monkeypatch, tmp_path):
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: [
        Job(id="gupy:1", source="gupy", title="Desenvolvedor Python Júnior", company="A", url="u", workplace="remoto")])
    monkeypatch.setattr(runner, "load_people", lambda: None)
    monkeypatch.setenv("EMAIL_USER", "eu@x.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")
    sent = []
    monkeypatch.setattr(emailer, "send", lambda msg, u, p, h, port: sent.append(msg))
    cfg = {"storage": {"path": str(tmp_path / "jobs.json")}, "email": {"enabled": True},
           "filter": {"location_filter": True}, "sources": {"gupy": {"enabled": True}}}
    assert runner.run(cfg) == 0
    assert [m["To"] for m in sent] == ["eu@x.com"] and "Olá" not in sent[0].get_body(("html",)).get_content()


def test_coleta_da_noite():
    assert avisos.is_evening(datetime(2026, 11, 27, 18), {})
    assert not avisos.is_evening(datetime(2026, 11, 27, 8), {})


def test_registros_do_robo_nao_mostram_nome_nem_email(monkeypatch, tmp_path, capsys):
    """Os registros do GitHub Actions são públicos: nada de nome ou e-mail de quem usa o Ragas."""
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: [
        Job(id="gupy:1", source="gupy", title="Estágio em Desenvolvimento de Software", company="B", url="https://x/2",
            workplace="remoto")])
    monkeypatch.setattr(runner, "load_people", lambda: [EU, AMIGA])
    monkeypatch.setenv("EMAIL_USER", "eu@x.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")

    def falha(msg, *a):
        raise OSError(f"recusado: {msg['To']}")
    monkeypatch.setattr(emailer, "send", falha)
    cfg = {"storage": {"path": str(tmp_path / "jobs.json")}, "email": {"enabled": True},
           "filter": {"location_filter": True, "state": "BA", "max_age_days": 0}, "sources": {"gupy": {"enabled": True}}}
    runner.run(cfg)
    out = capsys.readouterr().out
    assert "pessoa u2" in out
    for private in ("Emily", "amiga@x.com", "Pedro", "eu@x.com"):
        assert private not in out, private
