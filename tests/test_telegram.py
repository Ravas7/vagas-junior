"""Aviso pelo Telegram (sem internet: API do Telegram e Firebase simulados)."""

import pytest

from vagas import emailer, filters, runner, telegram
from vagas.firebase import Recipient
from vagas.http import SourceError
from vagas.models import Job
from vagas.sources import REGISTRY

PADRAO = filters.profile_from_config({"location_filter": True, "state": "BA"})


def up(i, text, chat=100, kind="private"):
    return {"update_id": i, "message": {"text": text, "chat": {"id": chat, "type": kind, "first_name": "Ana"}}}


class FakeBot:
    def __init__(self, ups=()):
        self.ups, self.sent, self.offset = list(ups), [], None

    def __call__(self, tok, method, body=None):
        if method == "getUpdates":
            if "offset" in (body or {}):
                self.offset = body["offset"]
                return []
            return self.ups
        if method == "sendMessage":
            self.sent.append((body["chat_id"], body["text"]))
            return {}
        raise AssertionError(method)


class FakeClient:
    def __init__(self):
        self.docs = {}

    def set_doc(self, path, data):
        self.docs[path] = data


def test_le_so_start_com_codigo_em_conversa_privada():
    ups = [up(1, "/start ABC12345"), up(2, "oi"), up(3, "/start ABC12345", kind="group"), up(4, "/start x")]
    assert telegram.start_codes(ups) == [("ABC12345", 100, "Ana")]


def test_liga_a_conversa_pelo_codigo_do_perfil(monkeypatch):
    bot = FakeBot([up(10, "/start ABC12345", chat=555), up(11, "olá", chat=999)])
    monkeypatch.setattr(telegram, "_call", bot)
    ana = Recipient("u1", "ana@x.com", "Ana Souza", {**PADRAO, "aviso": {"canal": "telegram", "telegram_codigo": "ABC12345"}})
    client = FakeClient()
    links = telegram.link(client, [ana], {}, "tok", log=lambda m: None)
    assert links["u1"]["chat_id"] == 555 and client.docs["telegram/u1"]["codigo"] == "ABC12345"
    assert bot.offset == 12                                    # mensagens marcadas como lidas
    assert any(c == 555 and "Pronto, Ana" in t for c, t in bot.sent)
    assert any(c == 999 and "Meu perfil" in t for c, t in bot.sent)   # quem mandou outra coisa recebe explicação


def test_erro_do_telegram_nao_mostra_o_token(monkeypatch):
    def boom(*a, **k):
        raise SourceError("HTTP 401 em https://api.telegram.org/botSEGREDO123/getUpdates")
    monkeypatch.setattr(telegram, "post_json", boom)
    with pytest.raises(SourceError) as e:
        telegram.updates("SEGREDO123")
    assert "SEGREDO123" not in str(e.value) and "401" in str(e.value)


def test_mensagem_grande_e_dividida():
    jobs = [Job(id=f"g:{i}", source="gupy", title=f"Desenvolvedor Python Júnior número {i} " + "x" * 80,
                company="Empresa <A&B>", url=f"https://x/{i}", workplace="remoto") for i in range(40)]
    texts = telegram.messages(jobs, "Olá, Ana!", "https://painel")
    assert len(texts) > 1 and all(len(t) <= 4096 for t in texts)
    assert texts[0].startswith("<b>Olá, Ana!</b>") and "Empresa &lt;A&amp;B&gt;" in texts[0]
    assert "Meu perfil" in texts[-1]


def test_coleta_manda_pelo_telegram_quem_ligou(monkeypatch, tmp_path):
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: [
        Job(id="gupy:1", source="gupy", title="Desenvolvedor Python Júnior", company="A", url="https://x/1",
            workplace="remoto")])
    ana = Recipient("u1", "ana@x.com", "Ana", {**PADRAO, "aviso": {"canal": "telegram", "telegram_codigo": "ABC12345"}},
                    {"telegram": {"chat_id": 555, "codigo": "ABC12345"}})
    monkeypatch.setattr(runner, "load_people", lambda: [ana])
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("EMAIL_USER", "eu@x.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")
    bot = FakeBot()
    monkeypatch.setattr(telegram, "_call", bot)
    mails = []
    monkeypatch.setattr(emailer, "send", lambda msg, *a: mails.append(msg))
    cfg = {"storage": {"path": str(tmp_path / "jobs.json")}, "email": {"enabled": True},
           "filter": {"location_filter": True, "state": "BA", "max_age_days": 0}, "sources": {"gupy": {"enabled": True}}}
    assert runner.run(cfg) == 0
    assert [c for c, _ in bot.sent] == [555] and "Python Júnior" in bot.sent[0][1]
    assert [m["To"] for m in mails] == ["eu@x.com"]           # o dono (sem perfil no Firebase) segue no e-mail antigo


def test_telegram_com_erro_cai_para_o_email(monkeypatch, tmp_path):
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: [
        Job(id="gupy:1", source="gupy", title="Desenvolvedor Python Júnior", company="A", url="https://x/1",
            workplace="remoto")])
    ana = Recipient("u1", "ana@x.com", "Ana", {**PADRAO, "aviso": {"canal": "telegram", "telegram_codigo": "ABC12345"}},
                    {"telegram": {"chat_id": 555, "codigo": "ABC12345"}})
    monkeypatch.setattr(runner, "load_people", lambda: [ana])
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("EMAIL_USER", "ana@x.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")

    def down(*a, **k):
        raise SourceError("Telegram sendMessage: HTTP 403")
    monkeypatch.setattr(telegram, "_call", down)
    mails = []
    monkeypatch.setattr(emailer, "send", lambda msg, *a: mails.append(msg))
    cfg = {"storage": {"path": str(tmp_path / "jobs.json")}, "email": {"enabled": True},
           "filter": {"location_filter": True, "state": "BA", "max_age_days": 0}, "sources": {"gupy": {"enabled": True}}}
    assert runner.run(cfg) == 0
    assert [m["To"] for m in mails] == ["ana@x.com"] and "Olá, Ana" in mails[0].get_body(("html",)).get_content()
