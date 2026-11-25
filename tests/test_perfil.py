"""Filtro em duas partes: base (vale para todos) + perfil (muda de pessoa para pessoa)."""

import tomllib

import pytest

from vagas.filters import evaluate, evaluate_base, evaluate_profile, profile_from_config
from vagas.models import Job


def job(title, description="", workplace="remoto", location="", uf="", kind="", salary=0):
    return Job(id="t:1", source="t", title=title, company="Acme", url="https://x", location=location,
               uf=uf, workplace=workplace, description=description, kind=kind, salary=salary)


CFG = tomllib.load(open("config.toml", "rb"))["filter"]
PADRAO = profile_from_config(CFG)


def base(j):
    r = evaluate_base(j, CFG)
    assert r.accepted, r.reasons
    return r


def com_perfil(j, **mudancas):
    return evaluate_profile(j, base(j), {**PADRAO, **mudancas})


def test_perfil_padrao_reproduz_o_config():
    assert PADRAO["niveis"] == ["junior"]
    assert PADRAO["areas"] == ["dev", "correlata", "suporte"]          # sem hardware
    assert PADRAO["filtrar_local"] is True
    assert "Salvador" in PADRAO["cidades"] and "Camaçari" in PADRAO["cidades"]
    assert PADRAO["remoto"] and PADRAO["exterior"]
    assert PADRAO["ingles_max"] == "intermediario"
    assert PADRAO["anos_max"] == CFG["max_years"]
    assert PADRAO["suporte_salario_min"] == 3200 and PADRAO["suporte_sem_salario"] is False
    assert PADRAO["nota_minima"] == CFG["min_score"]


@pytest.mark.parametrize("title,kind,nivel", [
    ("Desenvolvedor Python Júnior", "", "junior"),
    ("Dev React Jr/Pleno", "", "junior"),
    ("Desenvolvedor Java I", "", "junior"),
    ("Estágio em Desenvolvimento de Software", "", "estagio"),
    ("Desenvolvedor Jr", "estagio", "estagio"),                        # contrato de estágio
    ("Desenvolvedor Java Pleno", "", "pleno"),
    ("Desenvolvedor Back-end Semi Sênior", "", "pleno"),
    ("Desenvolvedor Java II", "", "pleno"),
    ("Desenvolvedor Python Sênior", "", "senior"),
    ("Tech Lead Backend", "", "senior"),
    ("Desenvolvedor Java III", "", "senior"),
    ("Desenvolvedor Full Stack", "", ""),                             # título não diz
])
def test_base_classifica_o_nivel_sem_descartar(title, kind, nivel):
    assert base(job(title, kind=kind)).nivel == nivel


def test_base_nao_olha_local_nem_ingles():
    assert evaluate_base(job("Desenvolvedor Jr", workplace="presencial", location="Recife, PE"), CFG).accepted
    assert evaluate_base(job("Desenvolvedor Jr", "Inglês fluente"), CFG).accepted


def test_base_continua_cortando_o_que_nao_e_ti():
    assert not evaluate_base(job("Vendedor Júnior"), CFG).accepted
    assert not evaluate_base(job("Analista de Dados"), CFG).accepted     # correlata sem nível
    assert not evaluate_base(job("Técnico de Assistência Técnica de Ar Condicionado"), CFG).accepted


def test_evaluate_e_base_mais_perfil_padrao():
    j = job("Desenvolvedor Python Jr", workplace="presencial", location="Salvador, BA", uf="BA")
    r = evaluate(j, CFG)
    assert r.accepted and "região de Salvador" in r.reasons
    assert r == com_perfil(j)


def test_niveis_do_perfil():
    jr, pleno, senior = job("Desenvolvedor Jr"), job("Desenvolvedor Pleno"), job("Desenvolvedor Sênior")
    estagio, sem_nivel = job("Estágio em Desenvolvimento de Software"), job("Desenvolvedor Full Stack", "Vaga júnior")

    assert [com_perfil(j).accepted for j in (jr, pleno, senior, estagio, sem_nivel)] == [True, False, False, False, True]

    so_estagio = dict(niveis=["estagio"])
    assert [com_perfil(j, **so_estagio).accepted for j in (jr, pleno, senior, estagio, sem_nivel)] == [False, False, False, True, False]

    pleno_senior = dict(niveis=["pleno", "senior"], anos_max=0)
    r = com_perfil(pleno, **pleno_senior)
    assert r.accepted and "pleno no título" in r.reasons
    assert com_perfil(senior, **pleno_senior).accepted
    assert not com_perfil(jr, **pleno_senior).accepted


def test_anos_de_experiencia_do_perfil():
    j = job("Desenvolvedor Pleno", "Experiência de 4 anos com Java")
    assert not com_perfil(j, niveis=["pleno"]).accepted                 # anos_max = 2 no padrão
    assert com_perfil(j, niveis=["pleno"], anos_max=5).accepted
    assert com_perfil(j, niveis=["pleno"], anos_max=0).accepted         # 0 = sem limite


def test_hardware_e_area_do_perfil():
    j = job("Técnico de Manutenção de Computadores", workplace="presencial", location="Salvador, BA")
    assert base(j).area == "hardware"
    assert not com_perfil(j).accepted                                  # padrão não tem hardware
    r = com_perfil(j, areas=["hardware"])
    assert r.accepted and "hardware e assistência técnica" in r.reasons
    assert base(job("Técnico de Informática")).area == "hardware"
    assert base(job("Assistência Técnica de Notebooks Jr")).area == "hardware"


def test_cidade_vem_do_perfil():
    j = job("Desenvolvedor Jr", workplace="presencial", location="Recife, PE", uf="PE")
    assert not com_perfil(j).accepted
    r = com_perfil(j, cidades=["Recife", "Olinda"], regiao_nome="Recife")
    assert r.accepted and "região de Recife" in r.reasons


def test_exterior_e_ingles_do_perfil():
    j = job("Software Engineer Junior", "Fluent English required", location="Remote - United States")
    assert not com_perfil(j).accepted                                  # inglês acima do limite
    assert com_perfil(j, ingles_max="qualquer").accepted
    assert not com_perfil(j, ingles_max="qualquer", exterior=False).accepted


def test_areas_e_suporte_do_perfil():
    dados = job("Analista de Dados Júnior")
    assert com_perfil(dados).accepted
    assert not com_perfil(dados, areas=["dev"]).accepted

    suporte = job("Analista de Suporte N1", salary=2800)
    assert not com_perfil(suporte).accepted                            # abaixo de R$ 3.200
    assert com_perfil(suporte, suporte_salario_min=2500).accepted
    assert com_perfil(job("Analista de Suporte N1"), suporte_sem_salario=True).accepted
    assert com_perfil(job("Analista de Suporte Pleno", salary=3500)).accepted   # regra de antes


def test_nota_minima_do_perfil():
    j = job("Desenvolvedor Full Stack", "Vaga para júnior")             # 20 + 20 + 10 remoto
    assert com_perfil(j).score == 50
    assert not com_perfil(j, nota_minima=60).accepted


def test_classify_grava_os_fatos_para_o_painel():
    from vagas.filters import classify
    j = job("Desenvolvedor Python Pleno", "Experiência com Django, React e AWS. 3 anos de experiência.",
            workplace="hibrido", location="Recife, PE", uf="PE")
    assert classify(j, CFG)                                            # passou na base: vai pro arquivo
    assert j.padrao is False                                           # mas não no seu perfil
    assert (j.nivel, j.area, j.subarea, j.years, j.city) == ("pleno", "dev", "dev", 3, "Recife")
    assert j.techs == ["Python", "React", "Cloud (AWS/Azure/GCP)"]

    dados = job("Engenheiro de Dados Jr", "SQL e Power BI")
    assert classify(dados, CFG) and dados.padrao
    assert (dados.area, dados.subarea, dados.nivel) == ("correlata", "dados", "junior")
    assert "SQL" in dados.techs and "Power BI" in dados.techs

    assert not classify(job("Vendedor Júnior"), CFG)                  # não é TI: fica de fora


def test_perfil_padrao_json_esta_em_dia():
    """docs/perfil-padrao.json precisa bater com o config.toml (rode: python -m vagas perfil)."""
    from pathlib import Path
    from vagas import runner
    cfg = runner.load_config("config.toml")
    atual = Path("docs/perfil-padrao.json").read_text(encoding="utf-8")
    assert atual.replace("\r\n", "\n") == runner.profile_json(cfg), "rode: python -m vagas perfil"


def test_perfil_de_amigo_estado_so_remoto_e_tecnologias():
    recife = job("Desenvolvedor Jr", "Vaga com React", workplace="presencial", location="Recife, PE", uf="PE")
    recife.techs = ["React"]
    amigo = dict(cidades=[], regiao_nome="", estado="PE")
    r = com_perfil(recife, **amigo)
    assert r.accepted and "seu estado (PE)" in r.reasons
    assert not com_perfil(recife, **amigo, presencial=False).accepted            # só remoto
    r = com_perfil(recife, **amigo, tecnologias=["React", "Python"])
    assert "sua tecnologia: React" in r.reasons and r.score == com_perfil(recife, **amigo).score + 10
    assert not com_perfil(recife, **amigo, tecnologias=["Python"], so_minhas_techs=True).accepted


def test_areas_finas_do_perfil():
    dados, qa = job("Analista de Dados Jr"), job("QA Júnior")
    assert com_perfil(dados, areas=["dados"]).accepted
    assert not com_perfil(qa, areas=["dados"]).accepted
    assert com_perfil(qa, areas=["correlata"]).accepted                          # o grupo todo


def test_arquivo_de_paridade_esta_em_dia():
    """tests/fixtures/paridade.json alimenta o teste do JS (rode: python tests/make_paridade.py)."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("make_paridade", Path("tests/make_paridade.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    atual = Path("tests/fixtures/paridade.json").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert atual == mod.build(), "rode: python tests/make_paridade.py"


@pytest.mark.parametrize("title,ufs,remoto", [
    ("TCE-ES abre processo seletivo para profissionais de TI", ["ES"], False),
    ("IMD/UFRN abre 40 vagas no Bacharelado em TI", ["RN"], False),
    ("IMPA Tech oferece 50 vagas em Teresina", ["PI"], False),
    ("Empresa de Camaçari abre vagas de TI", ["BA"], False),
    ("Prefeitura de Belém do Pará contrata", ["PA"], False),
    ("Itaú abre vagas para tech em São Paulo e Rio de Janeiro", ["RJ", "SP"], False),
    ("iFood abre seleção nacional para estudantes de todo o Brasil", [], True),
    ("Grupo OLX abre programa de trainee em inteligência artificial", [], False),
    ("Banco de El Salvador abre vagas", [], False),
])
def test_onde_e_a_noticia(title, ufs, remoto):
    from vagas.filters import news_places
    assert news_places(title) == (ufs, remoto)


def test_noticia_de_outro_estado_nao_vai_no_email():
    from vagas.filters import classify
    es = Job(id="n:1", source="noticias", title="TCE-ES abre processo seletivo de tecnologia", company="",
             url="u", tipo="noticia")
    assert classify(es, CFG)                          # guardada (serve para quem é do ES)...
    assert es.ufs == ["ES"] and es.padrao is False    # ...mas fora do seu perfil e do e-mail
    ba = Job(id="n:2", source="noticias", title="Empresa de Camaçari abre vagas de tecnologia para júnior",
             company="", url="u", tipo="noticia")
    assert classify(ba, CFG) and ba.padrao is True
