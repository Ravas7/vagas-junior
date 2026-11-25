"""Testes das fontes com respostas simuladas (sem internet)."""

import pytest

from vagas.http import SourceError
from vagas.sources import adzuna, greenhouse, gupy, lever
from vagas.sources.base import SourceSkipped, date_of


def fake_get(payloads):
    calls = []

    def _get(url, params=None, headers=None, **kw):
        calls.append((url, params))
        value = payloads(url, params) if callable(payloads) else payloads
        if isinstance(value, Exception):
            raise value
        return value
    _get.calls = calls
    return _get


def test_gupy_parse_com_nomes_de_campo_variados(monkeypatch):
    payload = {"data": [
        {"id": 11, "name": "Desenvolvedor Python Jr", "careerPageName": "Empresa A",
         "city": "Salvador", "state": "Bahia", "workplaceType": "hybrid",
         "jobUrl": "https://a.gupy.io/jobs/11", "publishedDate": "2026-11-20T10:00:00.000Z",
         "description": "<p>Venha <b>programar</b></p>", "type": "vacancy_type_effective"},
        {"id": 12, "title": "Dev React", "companyName": "Empresa B", "isRemoteWork": True,
         "url": "https://b/12", "state": "SP"},
        {"id": 13, "name": "Sem url"},                       # ignorada
    ], "pagination": {"total": 3}}
    f = fake_get(payload)
    monkeypatch.setattr(gupy, "get_json", f)
    jobs = gupy.fetch({"terms": ["dev"], "pages": 1, "limit": 50, "delay": 0})
    assert {j.id for j in jobs} == {"gupy:11", "gupy:12"}
    a = next(j for j in jobs if j.id == "gupy:11")
    assert (a.uf, a.workplace, a.posted_at, a.company) == ("BA", "hibrido", "2026-11-20", "Empresa A")
    assert a.location == "Salvador, BA" and a.snippet == "Venha programar"
    b = next(j for j in jobs if j.id == "gupy:12")
    assert b.workplace == "remoto" and b.uf == "SP"
    assert f.calls[0][1]["jobName"] == "dev"


def test_gupy_pagina_ate_acabar(monkeypatch):
    def payloads(url, params):
        n = 2 if params["offset"] == 0 else 1
        return {"data": [{"id": params["offset"] + i, "name": f"Dev {i}", "url": "https://x", "careerPageName": "A"}
                         for i in range(n)]}
    monkeypatch.setattr(gupy, "get_json", fake_get(payloads))
    jobs = gupy.fetch({"terms": ["dev"], "pages": 5, "limit": 2, "delay": 0})
    assert len(jobs) == 3


def test_fonte_com_erro_em_tudo_levanta(monkeypatch):
    monkeypatch.setattr(gupy, "get_json", fake_get(SourceError("HTTP 404 em x")))
    with pytest.raises(SourceError):
        gupy.fetch({"terms": ["a", "b"], "delay": 0})


def test_adzuna(monkeypatch):
    payload = {"results": [{
        "id": "999", "title": "Desenvolvedor Júnior", "redirect_url": "https://adzuna/999",
        "company": {"display_name": "Beta"}, "created": "2026-11-21T08:00:00Z",
        "location": {"display_name": "Salvador, Bahia", "area": ["Brasil", "Bahia", "Salvador"]},
        "description": "Trabalho remoto com Python", "contract_time": "full_time"}]}
    monkeypatch.setattr(adzuna, "get_json", fake_get(payload))
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    [j] = adzuna.fetch({"terms": ["dev"], "pages": 1, "delay": 0})
    assert (j.company, j.uf, j.workplace, j.posted_at) == ("Beta", "BA", "remoto", "2026-11-21")


def test_adzuna_salario(monkeypatch):
    mk = lambda i, **kw: {"id": i, "title": "Analista de Suporte N1", "redirect_url": f"https://a/{i}",
                          "company": {"display_name": "X"}, "location": {"display_name": "Salvador", "area": ["Brasil", "Bahia"]},
                          **kw}
    payload = {"results": [
        mk("1", salary_min=39000, salary_max=45000, salary_is_predicted="0"),   # anual -> mensal
        mk("2", salary_min=3300, salary_max=3300, salary_is_predicted="0"),     # já mensal
        mk("3", salary_min=60000, salary_max=60000, salary_is_predicted="1"),   # estimativa: ignora
        mk("4"),
    ]}
    monkeypatch.setattr(adzuna, "get_json", fake_get(payload))
    monkeypatch.setenv("ADZUNA_APP_ID", "id"); monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    jobs = {j.id: j for j in adzuna.fetch({"terms": ["x"], "pages": 1, "delay": 0})}
    assert [jobs[f"adzuna:{i}"].salary for i in "1234"] == [3750, 3300, 0, 0]


def test_adzuna_sem_chave_e_ignorada(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    with pytest.raises(SourceSkipped):
        adzuna.fetch({})


def test_greenhouse_filtra_local_e_limpa_html(monkeypatch):
    payload = {"jobs": [
        {"id": 1, "title": "Junior Software Engineer", "absolute_url": "https://g/1",
         "location": {"name": "Remote - Brazil"}, "updated_at": "2026-11-19T12:00:00-03:00",
         "content": "&lt;p&gt;Build &lt;b&gt;things&lt;/b&gt;&lt;/p&gt;"},
        {"id": 2, "title": "Junior Developer", "absolute_url": "https://g/2",
         "location": {"name": "Berlin, Germany"}},
    ]}
    monkeypatch.setattr(greenhouse, "get_json", fake_get(payload))
    [j] = greenhouse.fetch({"companies": ["acme-corp"], "delay": 0})
    assert j.id == "greenhouse:acme-corp:1" and j.company == "Acme Corp"
    assert j.workplace == "remoto" and j.snippet == "Build things"


def test_lever(monkeypatch):
    payload = [{"id": "abc", "text": "Desenvolvedor Backend Jr", "hostedUrl": "https://l/abc",
                "createdAt": 1763900000000, "workplaceType": "remote",
                "categories": {"location": "São Paulo, SP", "commitment": "Full-time"},
                "descriptionPlain": "Vaga para júnior"}]
    monkeypatch.setattr(lever, "get_json", fake_get(payload))
    [j] = lever.fetch({"companies": ["beta"], "location_keywords": ["são paulo"], "delay": 0})
    assert (j.workplace, j.uf, j.posted_at) == ("remoto", "SP", "2025-11-23")


def test_date_of():
    assert date_of("2026-11-20T10:00:00Z") == "2026-11-20"
    assert date_of(1763900000) == date_of(1763900000000) == "2025-11-23"
    assert date_of(None) == "" and date_of("ontem") == ""


# ------------------------------------------------------------- fontes novas
from vagas.sources import ashby, noticias, smartrecruiters, workday

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>x</title>
<item><title>Itaú abre processo seletivo em tecnologia - Exame</title>
<link>https://news.google.com/rss/articles/AAA</link><pubDate>Mon, 23 Nov 2026 12:00:00 GMT</pubDate>
<source url="https://exame.com">Exame</source></item>
<item><title>Prefeitura abre processo seletivo - G1</title>
<link>https://news.google.com/rss/articles/BBB</link><pubDate>Mon, 23 Nov 2026 12:00:00 GMT</pubDate>
<source url="https://g1.globo.com">G1</source></item>
<item><title>Matéria muito antiga - Folha</title>
<link>https://news.google.com/rss/articles/CCC</link><pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
<source url="https://folha.com">Folha</source></item>
<item><title>Sem link</title></item>
</channel></rss>"""


def test_noticias_parse_e_busca(monkeypatch):
    jobs = noticias.parse_feed(RSS)
    assert len(jobs) == 3
    a = jobs[0]
    assert a.title == "Itaú abre processo seletivo em tecnologia" and a.location == "via Exame"
    assert a.posted_at == "2026-11-23" and a.tipo == "noticia" and a.id.startswith("noticias:")

    urls = []
    monkeypatch.setattr(noticias, "get_text", lambda url, **kw: urls.append(url) or RSS)
    got = noticias.fetch({"queries": ["q um"], "company_queries": True, "group_size": 50,
                          "delay": 0, "max_age_days": 100000})
    assert len(urls) == 1 + 2                       # 1 fixa + 2 grupos de empresas (50 por grupo)
    assert "ceid=BR:pt-419" in urls[0]                # ":" sem codificar, como o Google espera
    assert "when%3A21d" in urls[0] and "hl=pt-BR" in urls[0]
    assert len({j.id for j in got}) == 3


def test_noticias_xml_invalido(monkeypatch):
    monkeypatch.setattr(noticias, "get_text", lambda url, **kw: "<rss><nao fecha")
    with pytest.raises(SourceError):
        noticias.fetch({"queries": ["x"], "company_queries": False, "delay": 0})


def test_smartrecruiters(monkeypatch):
    payload = {"offset": 0, "limit": 100, "totalFound": 2, "content": [
        {"id": "7430", "name": "Junior Software Developer", "releasedDate": "2026-11-20T10:00:00.000Z",
         "company": {"identifier": "BoschGroup", "name": "Bosch"},
         "location": {"city": "Campinas", "region": "São Paulo", "country": "br", "remote": False, "hybrid": True},
         "experienceLevel": {"id": "entry_level", "label": "Entry Level"},
         "typeOfEmployment": {"label": "Full-time"}},
        {"id": "7431", "name": "Estagiário de TI", "location": {"city": "Salvador", "region": "BA", "remote": True},
         "typeOfEmployment": {"label": "Intern"}, "company": {"name": "Bosch"}},
    ]}
    f = fake_get(payload)
    monkeypatch.setattr(smartrecruiters, "get_json", f)
    jobs = smartrecruiters.fetch({"companies": ["BoschGroup"], "delay": 0, "country": "br"})
    a, b = jobs
    assert a.url == "https://jobs.smartrecruiters.com/BoschGroup/7430" and a.company == "Bosch"
    assert (a.uf, a.workplace, a.posted_at, a.description) == ("SP", "hibrido", "2026-11-20", "Entry Level")
    assert b.workplace == "remoto" and b.uf == "BA" and b.kind == "Intern"
    assert f.calls[0][1]["country"] == "br"


def test_ashby(monkeypatch):
    payload = {"jobs": [
        {"id": "u1", "title": "Junior Backend Engineer", "location": "Brazil (Remote)", "isRemote": True,
         "jobUrl": "https://jobs.ashbyhq.com/acme/u1", "publishedAt": "2026-11-18T09:00:00.000+00:00",
         "descriptionPlain": "Join us", "employmentType": "FullTime"},
        {"id": "u2", "title": "Junior Engineer", "location": "Tokyo", "jobUrl": "https://x/u2"},
    ]}
    monkeypatch.setattr(ashby, "get_json", fake_get(payload))
    [j] = ashby.fetch({"companies": ["acme"], "delay": 0})
    assert j.id == "ashby:acme:u1" and j.workplace == "remoto" and j.posted_at == "2026-11-18"


def test_workday_site_e_data():
    assert workday.split_site("https://accenture.wd103.myworkdayjobs.com/en-US/AccentureCareers") == \
        ("accenture.wd103.myworkdayjobs.com", "accenture", "AccentureCareers")
    assert workday.split_site("https://adobe.wd5.myworkdayjobs.com/external_experienced")[2] == "external_experienced"
    from datetime import datetime, timezone
    now = datetime(2026, 11, 23, tzinfo=timezone.utc)
    assert workday.posted_date("Posted Today", now) == "2026-11-23"
    assert workday.posted_date("Posted Yesterday", now) == "2026-11-22"
    assert workday.posted_date("Posted 5 Days Ago", now) == "2026-11-18"
    assert workday.posted_date("Posted 30+ Days Ago", now) == "2026-10-24"
    assert workday.posted_date("???", now) == ""


def test_workday_busca_e_filtro_de_local(monkeypatch):
    calls = []

    def post(url, body, **kw):
        calls.append((url, body))
        return {"total": 3, "jobPostings": [
            {"title": "Junior Developer", "externalPath": "/job/Sao-Paulo/Junior-Developer_R-1",
             "locationsText": "Brazil - Sao Paulo", "postedOn": "Posted 2 Days Ago", "bulletFields": ["R-1"]},
            {"title": "Junior Developer", "externalPath": "/job/Austin/Junior-Developer_R-2",
             "locationsText": "Austin, Texas", "postedOn": "Posted Today", "bulletFields": ["R-2"]},
            {"title": "Trainee TI", "externalPath": "/job/Multi/Trainee_R-3",
             "locationsText": "2 Locations", "postedOn": "Posted Today", "bulletFields": ["R-3"]},
        ]}
    monkeypatch.setattr(workday, "post_json", post)
    jobs = workday.fetch({"sites": ["https://acme.wd5.myworkdayjobs.com/en-US/Careers"],
                          "terms": ["junior"], "pages": 1, "delay": 0})
    assert [j.id for j in jobs] == ["workday:acme:R-1"]
    j = jobs[0]
    assert j.url == "https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Sao-Paulo/Junior-Developer_R-1"
    assert j.company == "Acme"
    url, body = calls[0]
    assert url == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/jobs"
    assert body == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "junior"}
    keep = workday.fetch({"sites": ["https://acme.wd5.myworkdayjobs.com/Careers"], "terms": ["x"],
                          "pages": 1, "delay": 0, "keep_multi_location": True})
    assert {j.id for j in keep} == {"workday:acme:R-1", "workday:acme:R-3"}


def test_adzuna_busca_salvador_e_remoto(monkeypatch):
    f = fake_get({"results": []})
    monkeypatch.setattr(adzuna, "get_json", f)
    monkeypatch.setenv("ADZUNA_APP_ID", "id"); monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    adzuna.fetch({"terms": ["dev jr"], "pages": 1, "delay": 0, "wheres": ["Salvador", ""], "distance_km": 40})
    (_, p1), (_, p2) = f.calls
    assert p1["where"] == "Salvador" and p1["distance"] == 40 and p1["what"] == "dev jr"
    assert "where" not in p2 and p2["what"] == "dev jr remoto"


def test_gupy_variantes(monkeypatch):
    f = fake_get({"data": []})
    monkeypatch.setattr(gupy, "get_json", f)
    gupy.fetch({"terms": ["dev"], "pages": 1, "delay": 0, "variants": [{"state": "Bahia"}, {"workplaceType": "remote"}]})
    assert [c[1].get("state") for c in f.calls] == ["Bahia", None]
    assert f.calls[1][1]["workplaceType"] == "remote" and all(c[1]["jobName"] == "dev" for c in f.calls)


def test_gupy_estados_viram_variantes(monkeypatch):
    calls = []
    monkeypatch.setattr(gupy, "get_json", lambda url, params: calls.append(dict(params)) or [])
    gupy.fetch({"terms": ["dev"], "pages": 1, "delay": 0, "states": ["BA", "pe"]})
    assert [c.get("state") or c.get("workplaceType") for c in calls] == ["Bahia", "Pernambuco", "remote"]
    assert gupy.build_variants([], remote=False) == [{}]


def test_gupy_estado_invalido_vira_erro_da_fonte():
    with pytest.raises(SourceError):
        gupy.build_variants(["XX"])
