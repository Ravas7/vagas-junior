from vagas import storage
from vagas.models import Job


def mk(i, title="Desenvolvedor Python Jr", company="Acme", source="gupy", location="Salvador, BA"):
    return Job(id=f"{source}:{i}", source=source, title=title, company=company,
               url="https://x/" + str(i), location=location, score=80)


def test_vaga_nova_e_depois_conhecida():
    jobs, new = storage.merge({}, [mk(1)], {"gupy"}, "2026-11-23")
    assert [j.id for j in new] == ["gupy:1"] and jobs["gupy:1"].first_seen == "2026-11-23"
    jobs["gupy:1"].notified = True
    jobs2, new2 = storage.merge(jobs, [mk(1)], {"gupy"}, "2026-11-24")
    assert new2 == []
    j = jobs2["gupy:1"]
    assert j.first_seen == "2026-11-23" and j.last_seen == "2026-11-24" and j.notified


def test_duplicada_entre_fontes_nao_vira_nova():
    jobs, _ = storage.merge({}, [mk(1, source="gupy")], {"gupy"}, "2026-11-23")
    jobs, new = storage.merge(jobs, [mk(9, source="adzuna")], {"gupy", "adzuna"}, "2026-11-24")
    assert new == [] and len(jobs) == 1


def test_encerrada_so_se_a_fonte_respondeu():
    jobs, _ = storage.merge({}, [mk(1), mk(2, source="lever", title="Dev Go Jr", company="Beta")],
                            {"gupy", "lever"}, "2026-11-23")
    jobs, _ = storage.merge(jobs, [], {"gupy"}, "2026-11-24")     # lever falhou hoje
    assert jobs["gupy:1"].active is False
    assert jobs["lever:2"].active is True


def test_remove_vagas_muito_antigas():
    jobs, _ = storage.merge({}, [mk(1)], {"gupy"}, "2026-01-01")
    jobs, _ = storage.merge(jobs, [], {"gupy"}, "2026-11-23", keep_days=45)
    assert jobs == {}


def test_salvar_e_carregar(tmp_path):
    p = tmp_path / "d" / "jobs.json"
    jobs, _ = storage.merge({}, [mk(1), mk(2, title="Dev Java Jr", company="Beta")], {"gupy"}, "2026-11-23")
    jobs["gupy:1"].description = "não persiste"
    storage.save(p, jobs, {"updated_at": "x"})
    back = storage.load(p)
    assert set(back) == {"gupy:1", "gupy:2"} and back["gupy:1"].description == ""
    assert storage.load(tmp_path / "nao_existe.json") == {}


def test_noticia_dedupe_por_titulo_e_nao_encerra():
    n1 = Job(id="noticias:a", source="noticias", title="Itaú abre vagas", company="Itaú", url="u1",
             location="via Exame", tipo="noticia", score=70)
    n2 = Job(id="noticias:b", source="noticias", title="Itaú abre vagas", company="Itaú", url="u2",
             location="via G1", tipo="noticia", score=70)
    jobs, new = storage.merge({}, [n1, n2], {"noticias"}, "2026-11-23")
    assert len(jobs) == 1 and len(new) == 1
    jobs, _ = storage.merge(jobs, [], {"noticias"}, "2026-11-24")          # sumiu do feed
    assert jobs["noticias:a"].active is True
    jobs, _ = storage.merge(jobs, [], {"noticias"}, "2026-12-30", keep_days_news=30)
    assert jobs == {}                                                      # velha: removida
