"""Decide se uma vaga (ou notícia de processo seletivo) serve para um dev júnior.

VAGAS (evaluate), em ordem:
1. Título com termo de dev (python, desenvolvedor, backend...) ou de área correlata
   (dados, QA, DevOps, segurança...). Correlata exige "júnior" no título.
2. Título com sênior/líder/especialista/etc. é descartado sempre.
3. Título com "pleno" é descartado, a menos que também diga júnior ("Jr/Pleno").
4. Estágio só entra se include_estagio = true.
5. Pede mais anos de experiência que max_years e não diz júnior no título: descartado.
6. O resto vira nota; abaixo de min_score é descartado.

NOTÍCIAS (evaluate_news): o título precisa parecer anúncio de seleção
("processo seletivo", "trainee", "abre vagas"...) e falar de tecnologia. Notícia sobre
demissão, concurso público ou resultado é descartada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Job
from .text import ENGLISH_RANK, english_level, extract_salary, find_term, norm

DEV_TERMS = [
    "desenvolvedor", "desenvolvedora", "developer", "dev", "programador", "programadora",
    "engenheiro de software", "engenheira de software", "software engineer",
    "software developer", "web developer", "desenvolvimento de software",
    "analista de desenvolvimento", "analista desenvolvedor", "analista programador",
    "analista de sistemas", "backend", "back-end", "back end", "frontend", "front-end",
    "front end", "full stack", "fullstack", "full-stack", "mobile developer",
    "android", "ios", "python", "java", "javascript", "typescript", "react", "angular",
    "vue", "node", "nodejs", "node.js", ".net", "dotnet", "c#", "php", "golang",
    "ruby", "kotlin", "swift", "flutter", "react native",
]
# Áreas correlatas. Suporte técnico e service desk ficam de fora de propósito
# (quem quer sair do suporte não quer essas vagas); ligue com related_terms_extra.
RELATED_TERMS = [
    "analista de dados", "engenheiro de dados", "engenheira de dados", "cientista de dados",
    "data analyst", "data engineer", "data scientist", "business intelligence", "power bi",
    "machine learning", "inteligencia artificial", "analista de bi",
    "qa", "quality assurance", "analista de qualidade de software", "analista de testes",
    "engenheiro de qualidade", "tester", "test engineer", "sdet",
    "devops", "sre", "cloud", "engenheiro de nuvem", "analista de nuvem",
    "seguranca da informacao", "ciberseguranca", "cybersecurity", "analista de seguranca",
    "analista de infraestrutura", "infraestrutura de ti", "analista de redes",
    "analista de ti", "analista de tecnologia",
]
# Suporte técnico: só entra com salário informado igual ou acima de support_min_salary.
SUPPORT_TERMS = [
    "suporte tecnico", "analista de suporte", "tecnico de suporte", "suporte n1", "suporte n2",
    "suporte nivel 1", "suporte nivel 2", "suporte ti", "suporte de ti", "suporte a usuarios",
    "service desk", "help desk", "helpdesk", "central de servicos", "atendimento tecnico",
    "technical support", "it support", "analista de service desk", "analista de help desk",
]
NOT_IT_SUPPORT = [
    "cliente", "clientes", "customer", "sac", "vendas", "comercial", "financeiro", "rh",
    "juridico", "cobranca", "call center", "telemarketing", "atendente", "recepcionista",
]
JUNIOR_TERMS = [
    "junior", "jr", "trainee", "entry level", "entry-level", "nivel 1", "iniciante",
    "recem formado", "recem-formado", "primeiro emprego", "sem experiencia",
]
SENIOR_TERMS = [
    "senior", "sr", "lead", "leader", "lider", "especialista", "specialist", "staff",
    "principal", "head", "gerente", "manager", "coordenador", "coordenadora",
    "arquiteto", "arquiteta", "architect", "tech lead", "semi senior", "semi-senior",
]
PLENO_TERMS = ["pleno", "pl", "mid", "mid-level", "intermediario", "intermediate"]
ESTAGIO_TERMS = ["estagio", "estagiario", "estagiaria", "intern", "internship"]

# Empresas grandes e multinacionais com operação no Brasil. Termos ambíguos em
# português (vale, claro, porto, caixa, meta, visa, inter, tim, 99) ficam de fora.
BIG_COMPANIES = [
    "Itaú", "Bradesco", "Santander", "Banco do Brasil", "BTG Pactual", "XP Inc", "Nubank",
    "Banco Inter", "C6 Bank", "Sicredi", "Sicoob", "Safra", "Mercado Livre", "Mercado Pago",
    "Amazon", "AWS", "Microsoft", "Google", "Apple", "IBM", "Oracle", "SAP", "Salesforce",
    "Cisco", "Dell", "HP", "Intel", "Nvidia", "Adobe", "Accenture", "Capgemini", "Deloitte",
    "PwC", "KPMG", "Thoughtworks", "CI&T", "Stefanini", "TOTVS", "Zup", "Stone", "PagBank",
    "Magalu", "Americanas", "Natura", "Ambev", "Petrobras", "Gerdau", "Embraer", "WEG",
    "Vivo", "Telefônica", "Siemens", "Bosch", "Mastercard", "Visa Inc", "Ford", "Volkswagen",
    "Toyota", "Unilever", "Nestlé", "Samsung", "Globo", "B3", "JBS", "BRF", "Suzano",
    "Raízen", "Localiza", "iFood", "Uber", "Shopee", "Wellhub", "Gympass", "Pipefy",
    "Creditas", "Neon", "Bayer", "Johnson & Johnson", "Pfizer", "Shell", "Cielo", "Serasa",
    "Vtex", "Cloudflare", "Datadog", "Spotify", "Netflix", "Meta Platforms", "Atlassian",
    "Dataprev", "Serpro", "Embratel", "Claro Brasil", "TIM Brasil", "Banco Pan", "Votorantim",
]

# Região Metropolitana de Salvador (usada quando location_filter = true).
RMS_CITIES = [
    "Salvador", "Lauro de Freitas", "Camaçari", "Simões Filho", "Candeias", "Dias d'Ávila",
    "São Francisco do Conde", "Madre de Deus", "Mata de São João", "Vera Cruz", "Itaparica",
    "Pojuca", "São Sebastião do Passé", "SSA",
]
# Vaga "remota" restrita a outro país não serve.
REMOTE_BLOCK = [
    "united states", "usa", "us only", "u.s.", "canada", "united kingdom", "uk", "europe",
    "emea", "apac", "india", "germany", "portugal", "spain", "mexico", "argentina", "colombia",
    "chile", "philippines", "australia", "poland", "ireland", "netherlands", "france",
]
REMOTE_OK = ["brasil", "brazil", "latam", "america latina", "latin america", "worldwide", "global"]

# --- notícias ---
NEWS_SELECTION = [
    "processo seletivo", "processos seletivos", "programa de trainee", "trainee",
    "programa de estagio", "programa de talentos", "jovem talento", "jovens talentos",
    "early careers", "inscricoes abertas", "abre inscricoes", "abre vagas", "abre selecao",
    "vagas abertas", "oferece vagas", "oferta de vagas", "contrata", "contratacao",
    "seleciona", "vagas", "oportunidades",
]
NEWS_TECH = [
    "tecnologia", "ti", "software", "desenvolvimento de software", "desenvolvedor",
    "desenvolvedora", "desenvolvedores", "programador", "programadores", "programacao",
    "dev", "devs", "dados", "cloud", "nuvem", "devops", "ciberseguranca",
    "seguranca da informacao", "inteligencia artificial", "machine learning",
    "engenharia de software", "engenheiro de software", "analista de sistemas", "qa",
    "python", "java", "javascript", "front-end", "back-end", "full stack", "digital",
]
NEWS_DEV_SPECIFIC = [
    "tecnologia", "ti", "software", "desenvolvimento de software", "desenvolvedor",
    "desenvolvedora", "desenvolvedores", "programador", "programadores", "programacao",
    "dev", "devs", "engenharia de software", "engenheiro de software", "analista de sistemas",
    "python", "java", "javascript", "front-end", "back-end", "full stack",
]
NEWS_EXCLUDE = [
    "concurso", "concursos", "prefeitura", "camara municipal", "tribunal", "secretaria",
    "gabarito", "resultado", "convocacao", "convocados", "edital", "enem", "sisu", "prova",
    "demissao", "demissoes", "demite", "demitir", "layoff", "layoffs", "corte de vagas",
    "fecha vagas", "extingue", "golpe", "fraude", "falso", "acidente",
]
NEWS_JUNIOR = JUNIOR_TERMS + ["jovem talento", "jovens talentos", "early careers", "programa de talentos"]
NEWS_SENIOR = ["senior", "sr", "lider", "gerente", "diretor", "executivo", "especialista"]

# "Desenvolvedor II/III/IV" costuma ser pleno ou acima; "Desenvolvedor I" é júnior.
_ROMAN_HIGH = re.compile(r"(?:^|\s)(?:ii|iii|iv)\s*$")
_ROMAN_ONE = re.compile(r"(?:^|\s)(?:i|1)\s*$")
_YEARS = [
    re.compile(r"(?:experiencia|experience)[^.\n]{0,60}?(\d{1,2})\s*\+?\s*(?:anos|ano|years|yrs)"),
    re.compile(r"(\d{1,2})\s*\+?\s*(?:anos|ano|years|yrs)[^.\n]{0,40}?(?:de )?(?:experiencia|experience)"),
]


@dataclass
class Result:
    accepted: bool
    score: int
    reasons: list[str] = field(default_factory=list)
    area: str = "dev"
    english: str = ""
    abroad: bool = False


def required_years(text_norm: str) -> int:
    """Maior número de anos de experiência pedido na descrição (0 se não achar)."""
    found = [int(m.group(1)) for rx in _YEARS for m in rx.finditer(text_norm)]
    return max(found, default=0)


def big_company(text: str, cfg: dict) -> str:
    """Nome da grande empresa citada no texto ('' se nenhuma)."""
    names = BIG_COMPANIES + list(cfg.get("big_companies_extra", []))
    t = norm(text)
    for name in names:
        if find_term(t, [name]):
            return name
    return ""


def is_abroad(job: Job) -> bool:
    """Remoto cujo local cita outro país e não cita Brasil/LATAM/global."""
    loc = norm(job.location)
    return bool(find_term(loc, REMOTE_BLOCK) and not find_term(loc, REMOTE_OK))


def location_check(job: Job, cfg: dict) -> tuple[bool, str]:
    """Aceita vaga remota (do Brasil) ou em Salvador/região metropolitana."""
    if not cfg.get("location_filter", False):
        return True, ""
    not_ssa = lambda t: norm(t).replace("el salvador", "").replace("san salvador", "")  # outro país
    loc = not_ssa(job.location)
    if job.workplace == "remoto" and cfg.get("allow_remote", True):
        if is_abroad(job):
            if not cfg.get("remote_abroad", True):
                return False, f"remoto restrito a outro país ({job.location})"
            return True, "remoto no exterior"
        return True, "remoto"
    cities = [norm(c) for c in cfg.get("allowed_cities", RMS_CITIES)]
    if find_term(loc, cities) or find_term(not_ssa(job.title), cities):
        return True, "região de Salvador"
    if not loc and cfg.get("unknown_location", "descartar") == "incluir":
        return True, "local não informado"
    return False, f"fora de Salvador e região ({job.location or 'local não informado'})"


def age_days(job: Job) -> int | None:
    """Há quantos dias a vaga foi publicada (None se a fonte não informa a data)."""
    if not job.posted_at:
        return None
    try:
        posted = datetime.fromisoformat(job.posted_at).date()
    except ValueError:
        return None
    return (datetime.now(timezone.utc).date() - posted).days


def evaluate(job: Job, cfg: dict) -> Result:
    title = norm(job.title)
    desc = norm(job.description or job.snippet)
    kind = norm(job.kind)
    reasons: list[str] = []

    dev_terms = DEV_TERMS + [norm(t) for t in cfg.get("dev_terms_extra", [])]
    related_terms = RELATED_TERMS + [norm(t) for t in cfg.get("related_terms_extra", [])]
    junior_terms = JUNIOR_TERMS + [norm(t) for t in cfg.get("junior_terms_extra", [])]

    if norm(job.company) in {norm(c) for c in cfg.get("exclude_companies", [])}:
        return Result(False, 0, ["empresa na lista de exclusão"])
    if find_term(title, [norm(t) for t in cfg.get("exclude_title_terms", [])]):
        return Result(False, 0, ["termo excluído no título"])
    max_age = int(cfg.get("max_age_days", 0) or 0)
    age = age_days(job)
    if max_age and age is not None and age > max_age:
        return Result(False, 0, [f"publicada há {age} dias (limite: {max_age})"])

    dev_hit = find_term(title, dev_terms)
    related_hit = None if dev_hit or not cfg.get("related_enabled", True) else find_term(title, related_terms)
    support_hit = None
    if not (dev_hit or related_hit) and cfg.get("support_enabled", True):
        support_terms = SUPPORT_TERMS + [norm(t) for t in cfg.get("support_terms_extra", [])]
        if find_term(title, support_terms) and not find_term(title, NOT_IT_SUPPORT):
            support_hit = True
    if not (dev_hit or related_hit or support_hit):
        return Result(False, 0, ["sem termo de dev, área correlata ou suporte no título"])
    area = "dev" if dev_hit else "correlata" if related_hit else "suporte"

    if find_term(title, SENIOR_TERMS) or _ROMAN_HIGH.search(title):
        return Result(False, 0, ["título de nível sênior ou acima"], area)

    junior_in_title = bool(find_term(title, junior_terms) or _ROMAN_ONE.search(title))
    is_estagio = bool(find_term(title, ESTAGIO_TERMS) or find_term(kind, ESTAGIO_TERMS))

    if is_estagio and not cfg.get("include_estagio", False):
        return Result(False, 0, ["estágio (include_estagio = false)"], area)
    if area != "suporte" and find_term(title, PLENO_TERMS) and not junior_in_title:
        return Result(False, 0, ["título de nível pleno"], area)
    if area == "correlata" and not (junior_in_title or is_estagio):
        return Result(False, 0, ["área correlata sem 'júnior' no título"], area)

    loc_ok, loc_reason = location_check(job, cfg)
    if not loc_ok:
        return Result(False, 0, [loc_reason], area)

    abroad = loc_reason == "remoto no exterior"
    english = english_level(f"{job.title} {job.description or job.snippet}")
    cap = cfg.get("max_english", "intermediario")
    if cap in ENGLISH_RANK and ENGLISH_RANK[english] > ENGLISH_RANK[cap]:
        return Result(False, 0, [f"exige inglês {english} (limite: {cap})"], area, english, abroad)

    if area == "suporte":
        minimum = cfg.get("support_min_salary", 3200)
        if job.salary <= 0 and cfg.get("support_unknown_salary", "descartar") != "incluir":
            return Result(False, 0, [f"suporte sem salário informado (mínimo R$ {minimum})"], area)
        if 0 < job.salary < minimum:
            return Result(False, 0, [f"suporte paga R$ {job.salary} (mínimo R$ {minimum})"], area)

    years = required_years(desc)
    max_years = cfg.get("max_years", 2)
    if area != "suporte" and years > max_years and not junior_in_title:
        return Result(False, 0, [f"pede {years} anos de experiência"], area)

    score = {"dev": 20, "correlata": 10, "suporte": 40}[area]
    reasons.append({"dev": "termo de dev no título", "correlata": "área correlata no título",
                    "suporte": "suporte técnico"}[area])
    if area == "suporte":
        reasons.append(f"salário R$ {job.salary}" if job.salary else "salário não informado")
    elif junior_in_title:
        score += 50
        reasons.append("júnior no título")
    elif is_estagio:
        score += 50
        reasons.append("estágio")
    elif find_term(desc, junior_terms):
        score += 20
        reasons.append("júnior na descrição")
    if area != "suporte" and junior_in_title and find_term(desc, ["sem experiencia", "recem formado", "primeiro emprego"]):
        score += 5
        reasons.append("aceita pouca experiência")
    if area != "suporte" and 0 < years <= max_years:
        score += 5
        reasons.append(f"pede até {years} anos")
    if area != "suporte" and years > max_years:
        score -= 30
        reasons.append(f"pede {years} anos (penalizado)")
    if job.grande:
        score += cfg.get("big_bonus", 10)
        reasons.append("grande empresa")
    if job.workplace == "remoto":
        score += cfg.get("remote_bonus", 10)
        reasons.append("remoto")
    elif loc_reason == "região de Salvador":
        score += 10
        reasons.append("região de Salvador")
    if abroad:
        reasons.append("no exterior")
    if english:
        reasons.append(f"inglês {english}")
    preferred = {s.upper() for s in cfg.get("preferred_states", [])}
    if job.uf and job.uf in preferred:
        score += 10
        reasons.append(f"estado preferido ({job.uf})")

    accepted = score >= cfg.get("min_score", 40)
    if not accepted:
        reasons.append("nota abaixo do mínimo")
    return Result(accepted, score, reasons, area, english, abroad)


def evaluate_news(job: Job, cfg: dict) -> Result:
    title = norm(job.title)
    if find_term(title, NEWS_EXCLUDE + [norm(t) for t in cfg.get("news_exclude_extra", [])]):
        return Result(False, 0, ["notícia fora do tema (concurso, demissão, resultado...)"])
    selection = find_term(title, NEWS_SELECTION)
    if not selection:
        return Result(False, 0, ["não parece anúncio de seleção"])
    tech = find_term(title, NEWS_TECH)
    if not tech:
        return Result(False, 0, ["não fala de tecnologia"])
    junior = find_term(title, NEWS_JUNIOR)
    estagio = find_term(title, ESTAGIO_TERMS)
    if find_term(title, NEWS_SENIOR) and not junior:
        return Result(False, 0, ["fala de nível sênior ou gestão"])
    if estagio and not junior and not cfg.get("include_estagio", False):
        return Result(False, 0, ["estágio (include_estagio = false)"])

    area = "dev" if find_term(title, NEWS_DEV_SPECIFIC) else "correlata"
    score = 20
    reasons = ["anúncio de seleção", "tecnologia"]
    score += 20
    if junior or (estagio and cfg.get("include_estagio", False)):
        score += 30
        reasons.append("trainee/júnior")
    if job.grande:
        score += 25
        reasons.append("grande empresa")
    if job.posted_at:
        try:
            age = (datetime.now(timezone.utc).date() - datetime.fromisoformat(job.posted_at).date()).days
            if age <= 7:
                score += 10
                reasons.append("recente")
        except ValueError:
            pass
    accepted = score >= cfg.get("news_min_score", 40)
    if not accepted:
        reasons.append("nota abaixo do mínimo")
    return Result(accepted, score, reasons, area)


def apply(job: Job, cfg: dict) -> bool:
    """Marca grande empresa, avalia, grava score/reasons/area na vaga e diz se foi aceita."""
    if job.tipo == "noticia":
        name = big_company(job.title, cfg)
        job.grande = bool(name)
        job.company = name or "Empresa não identificada"
        result = evaluate_news(job, cfg)
    else:
        job.grande = bool(big_company(job.company, cfg))
        if not job.salary:
            job.salary = extract_salary(f"{job.description} {job.snippet}")
        result = evaluate(job, cfg)
    job.score, job.reasons, job.area = result.score, result.reasons, result.area
    job.english, job.abroad = result.english, result.abroad
    return result.accepted
