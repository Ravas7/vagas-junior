"""Leitura do Firebase pelo robô (sem internet: as respostas são simuladas)."""

import json

import pytest

from vagas import firebase, runner
from vagas.http import SourceError

CFG_JS = 'window.FIREBASE_CONFIG = {\n  apiKey: "chave-web",\n  projectId: "projeto-x",\n  appId: "1:2:web:3",\n};\n'


def s(v):
    return {"stringValue": v}


ACESSO = {"documents": [
    {"name": "projects/p/databases/(default)/documents/acesso/u1",
     "fields": {"email": s("eu@x.com"), "nome": s("Eu"), "status": s("aprovado")}},
    {"name": "projects/p/databases/(default)/documents/acesso/u2",
     "fields": {"email": s("amiga@x.com"), "nome": s("Amiga"), "status": s("aprovado")}},
    {"name": "projects/p/databases/(default)/documents/acesso/u3",
     "fields": {"email": s("pendente@x.com"), "status": s("pendente")}},
]}
PERFIL_U2 = {"fields": {
    "niveis": {"arrayValue": {"values": [s("estagio"), s("pleno")]}},
    "estado": s("PE"), "remoto": {"booleanValue": True}, "anos_max": {"integerValue": "0"},
    "aviso": {"mapValue": {"fields": {"ativo": {"booleanValue": True}}}},
}}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    cfg = tmp_path / "firebase-config.js"
    cfg.write_text(CFG_JS, encoding="utf-8")
    calls = []

    def post_json(url, body, headers=None, **kw):
        calls.append(("POST", url, body))
        if body["password"] != "certa":
            raise SourceError("HTTP 400 em https://identitytoolkit")
        return {"idToken": "token-do-robo"}

    def get_json(url, params=None, headers=None, **kw):
        calls.append(("GET", url, headers))
        assert headers["Authorization"] == "Bearer token-do-robo"
        if url.endswith("/documents/acesso"):
            return ACESSO
        if url.endswith("/users/u2/perfil/atual"):
            return PERFIL_U2
        raise SourceError("HTTP 404 em " + url)

    monkeypatch.setattr(firebase, "post_json", post_json)
    monkeypatch.setattr(firebase, "get_json", get_json)
    return cfg, calls


def test_le_projeto_e_chave_do_painel(fake):
    cfg, _ = fake
    assert firebase.web_config(cfg) == {"apiKey": "chave-web", "projectId": "projeto-x"}


def test_decodifica_valores_do_firestore():
    assert firebase.decode_fields(PERFIL_U2["fields"]) == {
        "niveis": ["estagio", "pleno"], "estado": "PE", "remoto": True, "anos_max": 0, "aviso": {"ativo": True}}


def test_lista_so_liberados_com_perfil(fake):
    cfg, calls = fake
    client = firebase.Client.login("robo@x.com", "certa", cfg)
    people = firebase.recipients(client)
    assert [(r.uid, r.email, r.perfil is not None) for r in people] == [("u1", "eu@x.com", False), ("u2", "amiga@x.com", True)]
    assert people[1].perfil["estado"] == "PE"
    assert "projeto-x" in calls[1][1] and "chave-web" in calls[0][1]


def test_sem_conta_do_robo_desliga_sem_erro(fake, monkeypatch):
    cfg, _ = fake
    monkeypatch.delenv("FIREBASE_ROBO_EMAIL", raising=False)
    monkeypatch.delenv("FIREBASE_ROBO_SENHA", raising=False)
    with pytest.raises(firebase.FirebaseSkipped):
        firebase.Client.login(config_path=cfg)


def test_senha_errada_vira_erro_claro_sem_mostrar_a_senha(fake):
    cfg, _ = fake
    with pytest.raises(SourceError) as err:
        firebase.Client.login("robo@x.com", "errada", cfg)
    assert "robô não conseguiu entrar" in str(err.value) and "errada" not in str(err.value)


def test_comando_avisos_lista_quem_recebe(fake, monkeypatch, tmp_path, capsys):
    cfg, _ = fake
    monkeypatch.setenv("FIREBASE_ROBO_EMAIL", "robo@x.com")
    monkeypatch.setenv("FIREBASE_ROBO_SENHA", "certa")
    real_login = firebase.Client.login
    monkeypatch.setattr(firebase.Client, "login", classmethod(lambda cls, *a, **k: real_login.__func__(cls, config_path=cfg)))
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"meta": {}, "jobs": [
        {"id": "g:1", "source": "g", "title": "Desenvolvedor Jr", "company": "A", "url": "u", "active": True,
         "padrao": True, "nivel": "junior", "junior_title": True, "workplace": "remoto"},
        {"id": "g:2", "source": "g", "title": "Desenvolvedor Pleno", "company": "B", "url": "u", "active": True,
         "padrao": False, "nivel": "pleno", "workplace": "remoto"},
    ]}), encoding="utf-8")
    assert runner.cmd_avisos({"storage": {"path": str(jobs)}, "filter": {}}) == 0
    out = capsys.readouterr().out
    assert "2 pessoas liberadas" in out
    assert "Eu <eu@x.com> | sem perfil (vale o do config.toml) | combinam 1 vaga " in out     # só a júnior (padrão)
    assert "Amiga <amiga@x.com> | perfil: estagio, pleno | PE | combinam 1 vaga " in out    # só a pleno
