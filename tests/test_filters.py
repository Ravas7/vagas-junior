import pytest

from vagas.filters import evaluate, required_years
from vagas.models import Job
from vagas.text import norm, to_uf, infer_workplace


def job(title, description="", workplace="", uf="", kind="", company="Acme"):
    return Job(id="t:1", source="t", title=title, company=company, url="https://x",
               workplace=workplace, uf=uf, description=description, kind=kind)


CFG = {"min_score": 40, "max_years": 2}


@pytest.mark.parametrize("title", [
    "Desenvolvedor Python Júnior",
    "Desenvolvedor(a) Front-end Jr",
    "Pessoa Desenvolvedora Backend Junior",
    "Analista de Sistemas Jr.",
    "Software Engineer - Entry Level",
    "Desenvolvedor Java I",
    "Dev React Jr/Pleno",
    "Programador PHP Trainee",
    "Engenheiro de Software Júnior (.NET)",
])
def test_aceita_junior(title):
    r = evaluate(job(title), CFG)
    assert r.accepted, r.reasons


@pytest.mark.parametrize("title,motivo", [
    ("Desenvolvedor Python Sênior", "sênior"),
    ("Tech Lead Backend", "sênior"),
    ("Desenvolvedor Java Pleno", "pleno"),
    ("Desenvolvedor Java II", "sênior"),
    ("Especialista em Python", "sênior"),
    ("Vendedor Júnior", "dev"),
    ("Analista Financeiro Jr", "dev"),
    ("Desenvolvedor Full Stack", "nota"),            # sem nível: não passa
    ("Desenvolvedor Back-end Semi Sênior", "sênior"),
])
def test_rejeita(title, motivo):
    assert not evaluate(job(title), CFG).accepted


def test_java_nao_casa_com_javascript_nem_dev_com_devops():
    r = evaluate(job("DevOps Júnior"), CFG)           # "dev" não casa dentro de "devops"...
    assert r.area == "correlata"                      # ...mas DevOps é área correlata
    assert not evaluate(job("DevOps Júnior"), {**CFG, "related_enabled": False}).accepted
    assert evaluate(job("Desenvolvedor JavaScript Júnior"), CFG).accepted


def test_pleno_com_junior_no_titulo_passa():
    assert evaluate(job("Desenvolvedor Jr/Pleno Node"), CFG).accepted


def test_estagio_depende_da_config():
    j = job("Estágio em Desenvolvimento de Software")
    assert not evaluate(j, CFG).accepted
    assert evaluate(j, {**CFG, "include_estagio": True}).accepted
    tipo = job("Desenvolvedor Python", kind="vacancy_type_internship")
    assert not evaluate(tipo, CFG).accepted


def test_anos_de_experiencia():
    d = "Requisitos: experiência de 4 anos com Python e Django."
    assert required_years(norm(d)) == 4
    assert not evaluate(job("Desenvolvedor Python", d), CFG).accepted
    # título diz júnior: segue, mas com nota menor
    r = evaluate(job("Desenvolvedor Python Júnior", d), CFG)
    assert r.accepted and any("anos" in x for x in r.reasons)
    assert required_years(norm("3+ anos de experiência")) == 3
    assert required_years(norm("Sem experiência prévia")) == 0


def test_junior_so_na_descricao():
    r = evaluate(job("Desenvolvedor Python", "Vaga para nível júnior, sem experiência."), CFG)
    assert r.accepted and r.score < 70


def test_bonus_remoto_e_estado():
    base = evaluate(job("Desenvolvedor Python Jr"), CFG).score
    remoto = evaluate(job("Desenvolvedor Python Jr", workplace="remoto"), CFG).score
    ba = evaluate(job("Desenvolvedor Python Jr", uf="BA"), {**CFG, "preferred_states": ["ba"]}).score
    assert remoto == base + 10 and ba == base + 10


def test_exclusoes_da_config():
    assert not evaluate(job("Desenvolvedor SAP Jr"), {**CFG, "exclude_title_terms": ["sap"]}).accepted
    assert not evaluate(job("Desenvolvedor Jr", company="Acme"), {**CFG, "exclude_companies": ["ACME"]}).accepted
    assert evaluate(job("Engenheiro de Dados Jr"), {**CFG, "dev_terms_extra": ["engenheiro de dados"]}).accepted


def test_texto():
    assert norm("Júnior  em   São Paulo") == "junior em sao paulo"
    assert to_uf("Bahia") == "BA" and to_uf("sp") == "SP" and to_uf("Narnia") == ""
    assert infer_workplace("Vaga 100% remoto") == "remoto"
    assert infer_workplace("Modelo híbrido, 3x por semana") == "hibrido"


# ------------------------------------------------------------- áreas correlatas e grandes empresas
from datetime import datetime, timedelta, timezone

from vagas import filters


@pytest.mark.parametrize("title", [
    "Analista de Dados Júnior", "QA Júnior", "DevOps Jr", "Engenheiro de Dados Jr",
    "Analista de Segurança da Informação Júnior", "Data Analyst Junior",
])
def test_area_correlata_com_junior_passa(title):
    j = job(title)
    r = filters.evaluate(j, CFG)
    assert r.accepted and r.area == "correlata", r.reasons


def test_area_correlata_sem_junior_ou_desligada_nao_passa():
    assert not filters.evaluate(job("Analista de Dados"), CFG).accepted
    assert not filters.evaluate(job("Analista de Dados Júnior"), {**CFG, "related_enabled": False}).accepted
    assert not filters.evaluate(job("Analista de Dados Sênior"), CFG).accepted


def test_suporte_so_com_salario_minimo():
    base = {**CFG, "support_min_salary": 3200}
    sem = job("Analista de Suporte Técnico N1")
    r = filters.evaluate(sem, base)
    assert not r.accepted and r.area == "suporte" and "sem salário" in r.reasons[0]

    pouco = job("Analista de Suporte Técnico N1"); pouco.salary = 2400
    assert not filters.evaluate(pouco, base).accepted

    ok = job("Analista de Suporte Técnico N1"); ok.salary = 3200
    r = filters.evaluate(ok, base)
    assert r.accepted and r.area == "suporte" and any("3200" in x for x in r.reasons)
    assert r.score < filters.evaluate(job("Desenvolvedor Python Jr"), CFG).score     # dev vem na frente

    pleno = job("Analista de Service Desk Pleno"); pleno.salary = 4000                  # N2/pleno pode
    assert filters.evaluate(pleno, base).accepted
    senior = job("Coordenador de Suporte Técnico"); senior.salary = 9000
    assert not filters.evaluate(senior, base).accepted


def test_suporte_salario_desconhecido_pode_ser_incluido():
    j = job("Técnico de Suporte N1")
    assert not filters.evaluate(j, CFG).accepted
    r = filters.evaluate(j, {**CFG, "support_unknown_salary": "incluir"})
    assert r.accepted and "salário não informado" in r.reasons
    assert not filters.evaluate(job("Técnico de Suporte N1"), {**CFG, "support_enabled": False}).accepted


def test_suporte_ao_cliente_nao_e_suporte_de_ti():
    for t in ("Analista de Suporte ao Cliente", "Atendente de Suporte SAC", "Suporte Comercial"):
        j = job(t); j.salary = 5000
        assert not filters.evaluate(j, CFG).accepted, t


def test_dev_com_suporte_no_titulo_segue_regra_de_dev():
    r = filters.evaluate(job("Desenvolvedor Python Jr (Suporte a Sistemas)"), CFG)
    assert r.accepted and r.area == "dev"


def test_apply_le_salario_da_descricao():
    j = job("Analista de Suporte N1", description="Salário: R$ 3.500,00 + VR de R$ 1.200,00. CLT.")
    assert filters.apply(j, CFG) and j.salary == 3500 and j.area == "suporte"
    j2 = job("Analista de Suporte N1", description="Benefício VR R$ 1.200,00. Sem informação de pagamento.")
    assert not filters.apply(j2, CFG) and j2.salary == 0


def test_extract_salary_e_monthly():
    from vagas.text import extract_salary, monthly
    assert extract_salary("Remuneração: de R$ 2.800 a R$ 3.600 mensais") == 3600
    assert extract_salary("Salário R$3200,00") == 3200
    assert extract_salary("Bolsa-auxílio R$ 1.500") == 1500
    assert extract_salary("Vale refeição de R$ 1.200 por mês") == 0           # não é salário
    assert extract_salary("Salário: R$ 80.000.000") == 0                       # fora da faixa plausível
    assert extract_salary(None) == 0
    assert monthly(0) == 0 and monthly(3200) == 3200 and monthly(42000) == 3500


def test_grande_empresa_marca_e_pontua():
    a = job("Desenvolvedor Java Jr", company="Itaú Unibanco")
    b = job("Desenvolvedor Java Jr", company="Padaria do Zé")
    assert filters.apply(a, CFG) and filters.apply(b, CFG)
    assert a.grande and not b.grande and a.score == b.score + 10
    assert "grande empresa" in a.reasons
    assert filters.big_company("Vale a pena? Claro que sim", {}) == ""      # palavras comuns não contam
    assert filters.big_company("Nubank abre vagas", {}) == "Nubank"
    assert filters.big_company("Sicredi contrata", {"big_companies_extra": ["Sicredi"]}) == "Sicredi"


def news(title, posted=None, source="Exame"):
    posted = posted or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Job(id="n:1", source="noticias", title=title, company="", url="https://n/1",
               location=f"via {source}", posted_at=posted, tipo="noticia")


@pytest.mark.parametrize("title,empresa", [
    ("Itaú abre processo seletivo com 300 vagas em tecnologia", "Itaú"),
    ("Amazon abre inscrições para programa de trainee em TI", "Amazon"),
    ("Programa de jovens talentos de tecnologia tem inscrições abertas", ""),
    ("Microsoft contrata desenvolvedores júnior no Brasil", "Microsoft"),
])
def test_noticias_aceitas(title, empresa):
    n = news(title)
    assert filters.apply(n, {}), n.reasons
    assert n.tipo == "noticia" and n.area == "dev"
    assert n.company == (empresa or "Empresa não identificada") and n.grande == bool(empresa)


@pytest.mark.parametrize("title", [
    "Prefeitura abre processo seletivo para analista de TI",
    "Concurso público de tecnologia da informação tem edital publicado",
    "Empresa de tecnologia demite 500 e fecha vagas",
    "Resultado do processo seletivo de trainee em tecnologia",
    "Itaú lança novo aplicativo de investimentos",
    "Ambev abre processo seletivo para vendedores",
    "Google contrata engenheiro sênior para liderar equipe",
])
def test_noticias_descartadas(title):
    assert not filters.apply(news(title), {})


def test_noticia_grande_empresa_pontua_mais_e_recencia():
    velha = news("Itaú abre processo seletivo em tecnologia",
                 posted=(datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%d"))
    nova = news("Itaú abre processo seletivo em tecnologia")
    filters.apply(velha, {}); filters.apply(nova, {})
    assert nova.score == velha.score + 10
    anon = news("Empresa abre processo seletivo em tecnologia")
    filters.apply(anon, {})
    assert anon.score < nova.score


def test_noticia_estagio_depende_da_config():
    n = news("Itaú abre programa de estágio em tecnologia")
    assert not filters.apply(n, {})
    assert filters.apply(news("Itaú abre programa de estágio em tecnologia"), {"include_estagio": True})


# ------------------------------------------------------------- localização: Salvador/RMS ou remoto
LOC = {**CFG, "location_filter": True}


def com_local(title="Desenvolvedor Python Jr", location="", workplace="", **kw):
    j = job(title, workplace=workplace, **kw)
    j.location = location
    return j


@pytest.mark.parametrize("location,workplace", [
    ("Salvador, BA", "presencial"), ("Salvador - BA", "hibrido"), ("Lauro de Freitas, BA", ""),
    ("Camaçari, Bahia", "presencial"), ("Simões Filho, BA", "hibrido"), ("Pituba, Salvador", ""),
    ("São Paulo, SP", "remoto"), ("Remote - Brazil", "remoto"), ("", "remoto"),
    ("Remote - LATAM", "remoto"),
])
def test_local_aceito(location, workplace):
    r = filters.evaluate(com_local(location=location, workplace=workplace), LOC)
    assert r.accepted, r.reasons


@pytest.mark.parametrize("location,workplace", [
    ("São Paulo, SP", "presencial"), ("São Paulo, SP", "hibrido"), ("Feira de Santana, BA", "presencial"),
    ("Recife, PE", ""), ("", "presencial"), ("", ""),
    ("San Salvador, El Salvador", "presencial"),              # El Salvador não é Salvador
    ("Berlin, Germany", "presencial"), ("Lisboa, Portugal", "hibrido"),
])
def test_local_rejeitado(location, workplace):
    r = filters.evaluate(com_local(location=location, workplace=workplace), LOC)
    assert not r.accepted and "fora de Salvador" in r.reasons[0], r.reasons


def test_filtro_de_local_opcoes():
    j = com_local(location="", workplace="")
    assert not filters.evaluate(j, LOC).accepted
    assert filters.evaluate(j, {**LOC, "unknown_location": "incluir"}).accepted
    assert not filters.evaluate(com_local(location="Recife", workplace="remoto"), {**LOC, "allow_remote": False}).accepted
    assert filters.evaluate(com_local(location="Recife"), {**LOC, "allowed_cities": ["Recife"]}).accepted
    assert filters.evaluate(com_local(location="Recife"), CFG).accepted            # filtro desligado


def test_local_pontua_e_suporte_respeita_local():
    ssa = filters.evaluate(com_local(location="Salvador, BA", workplace="presencial"), LOC)
    sem_filtro = filters.evaluate(com_local(location="Salvador, BA", workplace="presencial"), CFG)
    assert ssa.score == sem_filtro.score + 10 and "região de Salvador" in ssa.reasons
    sup = com_local("Analista de Suporte N1", location="São Paulo", workplace="presencial"); sup.salary = 4000
    assert not filters.evaluate(sup, {**LOC, "support_min_salary": 3200}).accepted
    sup2 = com_local("Analista de Suporte N1", location="Salvador", workplace="presencial"); sup2.salary = 4000
    assert filters.evaluate(sup2, {**LOC, "support_min_salary": 3200}).accepted


def test_noticia_nao_passa_por_filtro_de_local():
    n = Job(id="n:1", source="noticias", title="Itaú abre processo seletivo em tecnologia", company="",
            url="https://n", location="via Exame", tipo="noticia")
    assert filters.apply(n, LOC)


# ------------------------------------------------------------- remoto no exterior e nível de inglês
from vagas.text import english_level


@pytest.mark.parametrize("location", ["Remote - US only", "Remote, United States", "Remote - Europe", "Remote - Canada"])
def test_remoto_no_exterior_entra_e_e_marcado(location):
    r = filters.evaluate(com_local(location=location, workplace="remoto"), LOC)
    assert r.accepted and r.abroad and "no exterior" in r.reasons
    brasil = filters.evaluate(com_local(location="Remote - Brazil", workplace="remoto"), LOC)
    assert brasil.accepted and not brasil.abroad
    off = filters.evaluate(com_local(location=location, workplace="remoto"), {**LOC, "remote_abroad": False})
    assert not off.accepted and "outro país" in off.reasons[0]


@pytest.mark.parametrize("texto,nivel", [
    ("Inglês avançado é necessário", "avancado"), ("Fluent English required", "avancado"),
    ("Inglês fluente e comunicação", "avancado"), ("English level C1", "avancado"),
    ("Full professional proficiency in English", "avancado"),
    ("Inglês intermediário", "intermediario"), ("Intermediate English", "intermediario"),
    ("English B2 or higher", "intermediario"), ("Inglês (B1)", "intermediario"),
    ("Inglês básico para leitura técnica", "basico"), ("Basic English", "basico"),
    ("Inglês avançado (diferencial)", ""), ("Advanced English is a plus", ""),
    ("Inglês desejável", ""), ("Sem menção a idiomas", ""), ("", ""),
    ("Inglês intermediário, avançado para a liderança", "intermediario"),   # vale o mais baixo
])
def test_nivel_de_ingles(texto, nivel):
    assert english_level(texto) == nivel


def test_limite_de_ingles():
    avancado = com_local(location="Remote - US", workplace="remoto", description="Fluent English is required.")
    r = filters.evaluate(avancado, LOC)
    assert not r.accepted and "inglês avancado" in r.reasons[0] and r.english == "avancado"

    inter = com_local(location="Remote - US", workplace="remoto", description="Intermediate English (B1/B2).")
    r = filters.evaluate(inter, LOC)
    assert r.accepted and r.english == "intermediario" and "inglês intermediario" in r.reasons

    sem = com_local(location="Remote - US", workplace="remoto")           # não informado: entra
    assert filters.evaluate(sem, LOC).accepted

    assert filters.evaluate(avancado, {**LOC, "max_english": "qualquer"}).accepted
    assert not filters.evaluate(inter, {**LOC, "max_english": "basico"}).accepted
    # vale também para vaga em Salvador
    local = com_local(location="Salvador, BA", workplace="presencial", description="Inglês avançado")
    assert not filters.evaluate(local, LOC).accepted


def test_apply_grava_ingles_e_exterior():
    j = com_local(location="Remote - Germany", workplace="remoto", description="B2 English")
    assert filters.apply(j, LOC) and j.english == "intermediario" and j.abroad
