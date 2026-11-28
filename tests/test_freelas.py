"""Freelas de TI (ideia 8, etapa 1): coleta da Workana e do 99Freelas, filtro e armazenamento. Sem internet."""

from datetime import datetime, timezone

from vagas import emailer, filters, runner, storage
from vagas.models import Job
from vagas.sources import REGISTRY, freelas99, workana

NOW = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)

WK_ROW = {
    "slug": "criar-api-em-python-para-loja",
    "title": '<a href="/job/criar-api"><span title="Criar API em Python para loja">Criar API em Python pa...</span></a>',
    "description": "Preciso de uma API em <b>Python</b> com Django para minha loja.",
    "budget": "USD 250 - 500",
    "totalBids": "Propostas: 7",
    "postedDate": "há 15 horas",
    "skills": [{"anchorText": "Python"}, {"anchorText": "Django"}],
    "country": '<span class="country-name"><a href="/jobs?country=BR">Brasil</a></span>',
    "authorName": "Fulano D. S.",
    "hasVerifiedPaymentMethod": True,
}

P99 = """<ul class="result-list">
<li class="with-flag result-item " data-id="801624" data-nome="x">
  <hgroup><h1 class="title"><a href="/project/criacao-de-pagina-801624?fs=t">Cria&ccedil;&atilde;o de p&aacute;gina em React</a></h1>
  <p class="item-text information">
     Desenvolvimento Web | Iniciante | Publicado: <b class="datetime" cp-datetime="1795654102000"></b> |
     Tempo restante: <b class="datetime-restante" cp-datetime="1796258902000"></b> | Propostas: <b>4</b> | Interessados: <b>9</b>
  </hgroup>
  <div class="item-text description formatted-text" data-content="P&aacute;gina simples em React.<br/>Prazo curto.">x</div>
  <p class="item-text habilidades"><a class="habilidade">React</a><a class="habilidade">HTML</a></p>
</li>
<li class="with-flag result-item " data-id="801700" data-nome="y">
  <hgroup><h1 class="title"><a href="/project/bot-bac-bo-801700">Bot para Bac Bo no Telegram</a></h1>
  <p class="item-text information"> Automa&ccedil;&atilde;o | Especialista | Propostas: <b>90</b> |</p></hgroup>
</li>
</ul>"""


def test_workana_le_orcamento_data_e_nao_guarda_o_nome_do_cliente():
    j = workana.parse(WK_ROW, NOW)
    assert j.id == "workana:criar-api-em-python-para-loja" and j.url.endswith("/job/criar-api-em-python-para-loja")
    assert j.title == "Criar API em Python para loja" and j.tipo == "freela" and j.location == "Brasil"
    assert (j.orcamento_min, j.orcamento_max, j.moeda, j.por_hora) == (250, 500, "USD", False)
    assert j.propostas == 7 and j.posted_at == "2026-11-28" and j.pagamento_verificado
    assert "Fulano" not in str(j.to_dict())                    # jobs.json é público


def test_workana_formatos_de_orcamento_e_data():
    assert workana.budget("Menos de USD 15 / hora") == (0, 15, "USD", True)
    assert workana.budget("Mais de USD 3.000") == (3000, 0, "USD", False)
    assert workana.budget("USD 1.000 - 3.000") == (1000, 3000, "USD", False)
    assert workana.budget("A combinar") == (0, 0, "", False)
    assert workana.posted_date("Há quase uma hora", NOW) == "2026-11-28"
    assert workana.posted_date("Ontem", NOW) == "2026-11-27"
    assert workana.posted_date("há 3 dias", NOW) == "2026-11-25"
    assert workana.posted_date("há 2 semanas", NOW) == "2026-11-14"
    assert workana.posted_date("???", NOW) == ""


def test_workana_junta_repetidos_entre_paginas(monkeypatch):
    pages = {1: [WK_ROW, {**WK_ROW, "slug": "outro"}], 2: [WK_ROW], 3: []}
    calls = []

    def get(url, params=None, headers=None, **kw):
        calls.append(params["page"])
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        return {"results": {"results": pages[params["page"]]}}
    monkeypatch.setattr(workana, "get_json", get)
    jobs = workana.fetch({"pages": 5, "delay": 0})
    assert sorted(j.id for j in jobs) == ["workana:criar-api-em-python-para-loja", "workana:outro"]
    assert calls == [1, 2, 3]                                    # página vazia encerra


def test_99freelas_le_nivel_propostas_data_e_habilidades():
    a, b = freelas99.parse_page(P99)
    assert a.id == "freelas99:801624" and a.url == "https://www.99freelas.com.br/project/criacao-de-pagina-801624"
    assert a.title == "Criação de página em React" and a.location == "Desenvolvimento Web"
    assert a.nivel_freela == "iniciante" and a.propostas == 4 and a.posted_at == "2026-11-26"
    assert "React" in a.description and a.snippet.startswith("Página simples em React")
    assert b.nivel_freela == "especialista" and b.propostas == 90 and b.posted_at == ""


def test_99freelas_pagina_sem_projeto_e_erro_da_fonte(monkeypatch):
    monkeypatch.setattr(freelas99, "get_text", lambda url, **kw: "<html>site novo</html>")
    try:
        freelas99.fetch({"delay": 0})
    except Exception as exc:                                    # noqa: BLE001
        assert "o site mudou" in str(exc)
    else:
        raise AssertionError("deveria falhar")


def test_filtro_guarda_ti_descarta_golpe_e_ordena_iniciante_primeiro():
    boa, golpe = freelas99.parse_page(P99)
    assert filters.classify(boa, {}) is True and boa.padrao is False      # freela não vai no e-mail de vagas
    assert "para iniciante" in boa.reasons and "só 4 propostas" in boa.reasons and "React" in boa.techs
    assert filters.classify(golpe, {}) is False and "bac bo" in golpe.reasons[0]
    especialista = Job(id="w:1", source="workana", title="Sistema ERP completo", company="", url="u", tipo="freela",
                       nivel_freela="especialista", propostas=120)
    assert filters.classify(especialista, {}) and especialista.score < boa.score
    traducao = Job(id="w:3", source="workana", title="Ferramenta de tradução de textos com IA", company="", url="u",
                   tipo="freela")
    assert filters.classify(traducao, {}) is True               # tradução dentro de TI é parte do sistema
    extra = Job(id="w:2", source="workana", title="Planilha de Excel para RH", company="", url="u", tipo="freela")
    assert filters.classify(extra, {"freela_bloquear": ["planilha de excel"]}) is False


def test_freela_nao_encerra_quando_some_e_sai_em_7_dias():
    f = Job(id="workana:a", source="workana", title="A", company="", url="u", tipo="freela")
    jobs, new = storage.merge({}, [f], {"workana"}, "2026-11-20")
    assert len(new) == 1
    jobs, _ = storage.merge(jobs, [], {"workana"}, "2026-11-25")
    assert jobs["workana:a"].active                              # sumiu das primeiras páginas, mas segue aberto
    jobs, _ = storage.merge(jobs, [], {"workana"}, "2026-11-28")
    assert "workana:a" not in jobs                               # 8 dias sem aparecer: sai


def test_coleta_guarda_freela_mas_nao_manda_no_email(monkeypatch, tmp_path):
    monkeypatch.setattr(REGISTRY["workana"], "fetch", lambda cfg: [workana.parse(WK_ROW, NOW)])
    monkeypatch.setattr(REGISTRY["gupy"], "fetch", lambda cfg: [
        Job(id="gupy:1", source="gupy", title="Desenvolvedor Python Júnior", company="A", url="u", workplace="remoto")])
    monkeypatch.setattr(runner, "load_people", lambda: None)
    monkeypatch.setenv("EMAIL_USER", "eu@x.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "segredo")
    sent = []
    monkeypatch.setattr(emailer, "send", lambda msg, *a: sent.append(msg))
    path = tmp_path / "jobs.json"
    cfg = {"storage": {"path": str(path)}, "email": {"enabled": True}, "filter": {"location_filter": True},
           "sources": {"gupy": {"enabled": True}, "workana": {"enabled": True}}}
    assert runner.run(cfg) == 0
    saved = storage.load(path)
    assert saved["workana:criar-api-em-python-para-loja"].tipo == "freela"
    html = sent[0].get_body(("html",)).get_content()
    assert "Python Júnior" in html and "Criar API" not in html


# ---------------------------------------------------------------- etapa 3: perfil e avisos
from vagas import avisos, telegram  # noqa: E402
from vagas.firebase import Recipient  # noqa: E402

PADRAO = filters.profile_from_config({"location_filter": True, "state": "BA"})


def freelas_do_dia(n=7):
    out = []
    for i in range(n):
        j = Job(id=f"workana:p{i}", source="workana", title=f"Site em PHP número {i}", company="", url=f"https://w/{i}",
                tipo="freela", nivel_freela="iniciante" if i % 2 else "especialista", propostas=i * 10,
                orcamento="USD 100 - 250", orcamento_min=100, orcamento_max=250, description="PHP e SQL",
                first_seen="2026-11-29")
        filters.classify(j, {})
        out.append(j)
    return out


def test_perfil_de_freela_filtra_nivel_propostas_e_orcamento():
    f = Job(id="w:1", source="workana", title="x", company="", url="u", tipo="freela", nivel_freela="especialista",
            propostas=40, orcamento_min=0, orcamento_max=50, techs=["PHP"], score=50, reasons=["freela de TI"])
    ok = lambda **fr: filters.evaluate_freela(f, {"tecnologias": ["PHP"], "freelas": fr}).accepted  # noqa: E731
    assert ok() and not ok(ver=False) and not ok(nivel="intermediario") and not ok(propostas_max=30)
    assert not ok(orcamento_min=100)
    r = filters.evaluate_freela(f, {"tecnologias": ["PHP"]})
    assert r.score == 60 and r.reasons[-1] == "sua tecnologia: PHP"
    sem_info = Job(id="w:2", source="freelas99", title="x", company="", url="u", tipo="freela")
    assert filters.evaluate_freela(sem_info, {"freelas": {"orcamento_min": 500, "propostas_max": 5}}).accepted


def test_aviso_so_leva_freela_para_quem_ligou_e_no_maximo_5():
    pool = freelas_do_dia()
    ids = {j.id for j in pool}
    nao = Recipient("u1", "a@x.com", "Ana", {**PADRAO})
    sim = Recipient("u2", "b@x.com", "Bia", {**PADRAO, "freelas": {"avisar": True}})
    plans = avisos.plan([nao, sim], pool, ids, "2026-11-29", evening=False)
    assert [pl.person.uid for pl in plans] == ["u2"]           # só freelas novos: Ana não recebe nada
    assert len(plans[0].freelas) == 5 and plans[0].jobs == []
    so_ini = Recipient("u3", "c@x.com", "Caio", {**PADRAO, "freelas": {"avisar": True, "nivel": "iniciante"}})
    [pl] = avisos.plan([so_ini], pool, ids, "2026-11-29", evening=False)
    assert all(j.nivel_freela == "iniciante" for j in pl.freelas)


def test_email_e_telegram_tem_secao_de_freelas():
    frees = freelas_do_dia(2)
    msg = emailer.build_message([], {}, "https://painel", "r@x.com", "b@x.com", "29/11", greeting="Olá, Bia!",
                                freelas=frees)
    html = msg.get_body(("html",)).get_content()
    assert "Freelas novos" in html and "Site em PHP número 0" in html and "USD 100 - 250" in html
    assert "2 freelas novos" in msg["Subject"]
    texts = telegram.messages([], "Olá, Bia!", "https://painel", freelas=frees)
    assert "<b>Freelas novos</b>" in texts[0] and "Workana · USD 100 - 250" in texts[0]
