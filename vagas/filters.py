"""Decide se uma vaga (ou notícia de processo seletivo) serve para um dev júnior.

VAGAS: duas partes. evaluate() = evaluate_base() + evaluate_profile() com o perfil do config.

Base (evaluate_base, vale para todo mundo): só classifica e corta o que não é de TI.
1. Área pelo título: dev (python, desenvolvedor...), correlata (dados, QA, DevOps,
   segurança...), suporte técnico ou hardware (assistência técnica, manutenção...).
2. Nível pelo título: estágio, júnior, pleno, sênior (inclui líder, gerente...) ou
   "" quando o título não diz. Correlata precisa dizer o nível no título.
3. Junta os fatos que o perfil usa: inglês pedido, exterior, anos de experiência.

Perfil (evaluate_profile, muda de pessoa para pessoa): áreas, níveis, cidade/remoto/
exterior, inglês máximo, anos de experiência, salário mínimo de suporte e nota mínima.
Também calcula a nota. O perfil padrão sai do [filter] do config.toml (profile_from_config).

NOTÍCIAS (evaluate_news): o título precisa parecer anúncio de seleção
("processo seletivo", "trainee", "abre vagas"...) e falar de tecnologia. Notícia sobre
demissão, concurso público ou resultado é descartada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Job
from .text import ENGLISH_RANK, UF_BY_NAME, UFS, english_level, extract_salary, find_term, norm

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
# Agrupadas por subárea (o perfil pode escolher só dados, só QA...).
RELATED_GROUPS = {
    "dados": ["analista de dados", "engenheiro de dados", "engenheira de dados", "cientista de dados",
              "data analyst", "data engineer", "data scientist", "business intelligence", "power bi",
              "machine learning", "inteligencia artificial", "analista de bi", "banco de dados"],
    "qa": ["qa", "quality assurance", "analista de qualidade de software", "analista de testes",
           "engenheiro de qualidade", "tester", "test engineer", "sdet"],
    "devops": ["devops", "sre", "cloud", "engenheiro de nuvem", "analista de nuvem"],
    "seguranca": ["seguranca da informacao", "ciberseguranca", "cybersecurity", "analista de seguranca"],
    "infra": ["analista de infraestrutura", "infraestrutura de ti", "analista de redes",
              "analista de ti", "analista de tecnologia",
              # genéricos, comuns em estágio ("Estagiário em TI"); correlata exige o nível no título
              "ti", "tecnologia da informacao", "sistemas de informacao"],
}
RELATED_TERMS = [t for terms in RELATED_GROUPS.values() for t in terms]

# Tecnologias que aparecem como etiqueta e que o perfil pode exigir.
# Nome mostrado -> termos procurados no título e na descrição (já sem acento).
TECH_TERMS = {
    "Python": ["python", "django", "flask", "fastapi"],
    "Java": ["java", "spring", "spring boot"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript"],
    "React": ["react", "reactjs", "react.js", "next.js", "nextjs"],
    "React Native": ["react native"],
    "Angular": ["angular"],
    "Vue": ["vue", "vuejs", "vue.js", "nuxt"],
    "Node.js": ["node", "nodejs", "node.js", "nestjs"],
    ".NET / C#": [".net", "dotnet", "c#", "asp.net"],
    "PHP": ["php", "laravel"],
    "Go": ["golang"],
    "Ruby": ["ruby", "rails"],
    "Kotlin": ["kotlin"],
    "Swift / iOS": ["swift", "ios"],
    "Android": ["android"],
    "Flutter": ["flutter", "dart"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sql server"],
    "Power BI": ["power bi", "powerbi"],
    "Cloud (AWS/Azure/GCP)": ["aws", "azure", "gcp", "google cloud"],
    "Docker / Kubernetes": ["docker", "kubernetes", "k8s"],
    "Linux": ["linux"],
    "Redes": ["redes de computadores", "tcp/ip", "ccna", "roteadores", "switches"],
    "Hardware": ["hardware", "manutencao de computadores", "manutencao de notebooks"],
}
# Suporte técnico: uma área como as outras (a pessoa marca no perfil se quer ver).
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
# Hardware e assistência técnica (montagem, manutenção e reparo de equipamentos).
HARDWARE_TERMS = [
    "hardware", "assistencia tecnica", "tecnico de informatica", "tecnico em informatica",
    "tecnico de hardware", "manutencao de computadores", "manutencao de notebooks",
    "manutencao de hardware", "manutencao de equipamentos de informatica",
    "montagem de computadores", "tecnico de bancada", "reparo de computadores",
    "reparo de notebooks", "reparo de celulares", "tecnico de celular", "tecnico de celulares",
    "tecnico em eletronica", "tecnico de eletronica", "microinformatica",
    "tecnico de microinformatica", "field service", "hardware technician",
]
# Assistência técnica de outras coisas (ar-condicionado, carro...) não é TI.
NOT_HARDWARE = [
    "ar condicionado", "ar-condicionado", "refrigeracao", "automotivo", "automotiva",
    "veiculos", "eletrodomesticos", "elevador", "elevadores", "predial", "eletricista",
    "mecanico", "mecanica", "vendas", "comercial", "atendente",
    "engenharia civil", "civil", "obras", "construcao", "seguranca do trabalho", "eletrica",
]
JUNIOR_TERMS = [
    "junior", "jr", "trainee", "entry level", "entry-level", "nivel 1", "iniciante",
    "recem formado", "recem-formado", "primeiro emprego", "sem experiencia",
]
SENIOR_TERMS = [
    "senior", "sr", "lead", "leader", "lider", "especialista", "specialist", "staff",
    "principal", "head", "gerente", "manager", "coordenador", "coordenadora",
    "arquiteto", "arquiteta", "architect", "tech lead",
]
PLENO_TERMS = ["pleno", "pl", "mid", "mid-level", "intermediario", "intermediate",
               "semi senior", "semi-senior"]
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

# --- onde é a notícia: estados citados no título ou "vale para todo lugar" ---
NEWS_REMOTE = [
    "remoto", "remota", "remotos", "remotas", "home office", "teletrabalho", "trabalho a distancia",
    "todo o brasil", "todo o pais", "qualquer lugar do brasil", "selecao nacional", "ead", "a distancia", "online",
]
# Nomes de estado (sem acento). "Pará" fica de fora daqui porque "para" é palavra comum (ver _PARA).
NEWS_STATES = {nome: uf for nome, uf in UF_BY_NAME.items() if nome != "para"}
# Capitais e cidades grandes. Natal, Vitória e Palmas ficam de fora: são palavras comuns.
NEWS_CITIES = {
    "rio branco": "AC", "maceio": "AL", "macapa": "AP", "manaus": "AM", "salvador": "BA",
    "feira de santana": "BA", "fortaleza": "CE", "brasilia": "DF", "grande vitoria": "ES",
    "goiania": "GO", "sao luis": "MA", "cuiaba": "MT", "campo grande": "MS", "belo horizonte": "MG",
    "uberlandia": "MG", "juiz de fora": "MG", "belem": "PA", "joao pessoa": "PB", "curitiba": "PR",
    "londrina": "PR", "maringa": "PR", "recife": "PE", "teresina": "PI", "rio de janeiro": "RJ",
    "niteroi": "RJ", "porto alegre": "RS", "porto velho": "RO", "florianopolis": "SC",
    "joinville": "SC", "blumenau": "SC", "sao paulo": "SP", "campinas": "SP", "guarulhos": "SP",
    "ribeirao preto": "SP", "sorocaba": "SP", "sao jose dos campos": "SP", "aracaju": "SE",
    **{norm(c): "BA" for c in RMS_CITIES if norm(c) != "ssa"},
}
_UF_RE = "|".join(sorted(UFS))
# sigla solta ("TCE-ES", "Vitória/ES", "(PE)") ou dentro de instituição ("IFSP", "UFRN", "UERN")
_UF_TOKEN = re.compile(rf"(?<![A-Za-zÀ-ÿ])(?:IF|UF|UE)?({_UF_RE})(?![A-Za-zÀ-ÿ])")
_PARA = re.compile(r"(?<![A-Za-zÀ-ÿ])Pará(?![A-Za-zÀ-ÿ])")


def news_places(title: str) -> tuple[list[str], bool]:
    """Estados citados no título de uma notícia e se ela vale para todo lugar (remoto, EaD...)."""
    t = norm(title).replace("el salvador", "")
    found = []
    for name, uf in {**NEWS_STATES, **NEWS_CITIES}.items():
        if find_term(t, [name]):
            found.append(uf)
    found += _UF_TOKEN.findall(title)
    if _PARA.search(title):
        found.append("PA")
    ufs = sorted(set(found))
    return ufs, bool(find_term(t, NEWS_REMOTE))


def news_location_check(job: Job, perfil: dict) -> tuple[bool, str]:
    """Notícia de vaga segue o local do perfil: remota ou sem lugar vale para todos."""
    ufs = job.ufs or []
    if not perfil.get("filtrar_local", True) or job.workplace == "remoto" or not ufs:
        return True, ""
    if not perfil.get("presencial", True):
        return False, f"notícia de vaga local ({', '.join(ufs)})"
    estado = (perfil.get("estado") or "").upper()
    if not estado or estado in ufs:      # sem estado no perfil não dá para saber: mostra
        return True, ""
    return False, f"notícia de outro estado ({', '.join(ufs)})"


def evaluate_news_profile(job: Job, perfil: dict) -> Result:
    """Perfil sobre uma notícia já aceita: só olha o local. Nota e motivos ficam os da notícia."""
    ok, why = news_location_check(job, perfil)
    if not ok:
        return Result(False, 0, [why], job.area)
    return Result(True, job.score, list(job.reasons), job.area)

# "Desenvolvedor I" é júnior, "II" é pleno, "III/IV" é sênior.
_ROMAN_PLENO = re.compile(r"(?:^|\s)(?:ii|2)\s*$")
_ROMAN_SENIOR = re.compile(r"(?:^|\s)(?:iii|iv|3|4)\s*$")
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
    area: str = "dev"            # dev | correlata | suporte | hardware
    english: str = ""
    abroad: bool = False
    nivel: str = ""              # estagio | junior | pleno | senior | "" (título não diz)
    # fatos que o perfil usa para a nota (vêm da descrição, que não fica salva)
    junior_title: bool = False   # "júnior", "jr", "trainee"... no título
    junior_desc: bool = False    # "júnior" só na descrição
    pouca_exp: bool = False      # júnior no título e "sem experiência" na descrição
    years: int = 0               # anos de experiência pedidos (0 = não diz)
    subarea: str = ""            # dev | dados | qa | devops | seguranca | infra | suporte | hardware


NIVEIS = ["estagio", "junior", "pleno", "senior"]
NIVEL_NOME = {"estagio": "estágio", "junior": "júnior", "pleno": "pleno", "senior": "sênior ou acima"}
AREAS = ["dev", "correlata", "suporte", "hardware"]
AREA_NOME = {"dev": "desenvolvimento", "correlata": "área correlata", "suporte": "suporte técnico",
             "hardware": "hardware e assistência técnica"}


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


def age_days(job: Job) -> int | None:
    """Há quantos dias a vaga foi publicada (None se a fonte não informa a data)."""
    if not job.posted_at:
        return None
    try:
        posted = datetime.fromisoformat(job.posted_at).date()
    except ValueError:
        return None
    return (datetime.now(timezone.utc).date() - posted).days


SUBAREA_NOME = {
    "dev": "Desenvolvimento", "dados": "Dados e BI", "qa": "QA e testes", "devops": "DevOps e cloud",
    "seguranca": "Segurança da informação", "infra": "Infraestrutura e redes",
    "suporte": "Suporte técnico", "hardware": "Hardware e assistência técnica",
}


def profile_options(cfg: dict) -> dict:
    """O que o formulário de perfil do painel precisa: o perfil padrão e as opções.

    Gravado em docs/perfil-padrao.json pelo comando `python -m vagas perfil`.
    """
    return {
        "perfil": profile_from_config(cfg),
        "niveis": [{"id": n, "nome": NIVEL_NOME[n]} for n in NIVEIS],
        "areas": [{"id": a, "nome": nome} for a, nome in SUBAREA_NOME.items()],
        "correlatas": list(RELATED_GROUPS),          # "correlata" no config = estas subáreas
        "tecnologias": list(TECH_TERMS),
        "cidades_padrao": list(RMS_CITIES),
        # o painel repete evaluate_profile em JS (docs/perfil.js) e precisa destas listas
        "regras": {
            "remote_block": REMOTE_BLOCK,
            "remote_ok": REMOTE_OK,
            "english_rank": ENGLISH_RANK,
            "area_nome": AREA_NOME,
            "nivel_nome": NIVEL_NOME,
        },
    }


def base_from_job(job: Job) -> Result:
    """Remonta o resultado da base a partir dos campos salvos no jobs.json.

    É o que o painel tem em mãos; serve para o teste de paridade com o JS e,
    no futuro, para o e-mail de cada pessoa.
    """
    return Result(True, 0, [], job.area, job.english, job.abroad, job.nivel, job.junior_title,
                  job.junior_desc, job.pouca_exp, job.years, job.subarea)


def related_group(title_norm: str) -> str:
    """Subárea de uma vaga de área correlata (dados, qa, devops, seguranca, infra)."""
    for group, terms in RELATED_GROUPS.items():
        if find_term(title_norm, terms):
            return group
    return "correlata"              # termo extra do config.toml, sem grupo


def find_techs(text: str) -> list[str]:
    """Tecnologias citadas no texto, na ordem de TECH_TERMS."""
    t = norm(text)
    return [name for name, terms in TECH_TERMS.items() if find_term(t, terms)]


def city_of(job: Job) -> str:
    """Cidade da vaga quando o local vem como "Cidade, UF"."""
    if not job.uf or job.workplace == "remoto" or "," not in job.location:
        return ""
    return job.location.split(",")[0].strip()


def job_level(title_norm: str, kind_norm: str, junior_terms: list[str]) -> tuple[str, bool]:
    """Nível da vaga pelo título (e tipo de contrato). Devolve (nível, júnior no título)."""
    junior_title = bool(find_term(title_norm, junior_terms) or _ROMAN_ONE.search(title_norm))
    sem_semi = title_norm.replace("semi senior", "").replace("semi-senior", "")
    if find_term(sem_semi, SENIOR_TERMS) or _ROMAN_SENIOR.search(title_norm):
        return "senior", junior_title
    if find_term(title_norm, ESTAGIO_TERMS):
        return "estagio", junior_title
    # "Jr/Pleno" conta como júnior; "Pleno" sozinho manda mais que o tipo de contrato.
    if not junior_title and (find_term(title_norm, PLENO_TERMS) or _ROMAN_PLENO.search(title_norm)):
        return "pleno", False
    if find_term(kind_norm, ESTAGIO_TERMS):      # contrato de estágio, mesmo com "Jr" no título
        return "estagio", junior_title
    if junior_title:
        return "junior", True
    return "", False


# ---------------------------------------------------------------- perfil
# O perfil guarda o que muda de pessoa para pessoa. As chaves são simples (JSON)
# porque o mesmo perfil vai ser lido pelo painel e salvo no Firestore.
PROFILE_DEFAULTS = {
    "niveis": ["junior"],           # estagio | junior | pleno | senior (um ou mais)
    "areas": ["dev", "correlata", "suporte"],   # + "hardware"
    "filtrar_local": True,          # False = aceita qualquer local
    "regiao_nome": "Salvador",      # só para as mensagens ("região de Salvador")
    "cidades": RMS_CITIES,          # cidades aceitas para vaga presencial/híbrida
    "local_desconhecido": False,    # True = aceita vaga não remota sem local informado
    "remoto": True,                 # aceita remoto no Brasil
    "exterior": True,               # aceita remoto de empresa/local fora do Brasil
    "ingles_max": "intermediario",  # basico | intermediario | qualquer
    "anos_max": 2,                  # pede mais anos que isso: descarta (0 = sem limite)
    "salario_min": 0,               # R$ por mês, para QUALQUER vaga que informa salário (0 = sem mínimo)
    "sem_salario": True,            # False = com mínimo, esconde vaga que não informa salário
    "estado": "",                   # UF; sem cidades, aceita o estado inteiro
    "presencial": True,             # False = só remoto
    "tecnologias": [],              # nomes de TECH_TERMS; dão +10 de nota
    "so_minhas_techs": False,       # True = só vagas que citam uma das tecnologias
    "bonus_tecnologia": 10,
    "estados_preferidos": [],       # +10 de nota
    "bonus_remoto": 10,
    "bonus_grande": 10,
    "nota_minima": 40,
}


def profile_from_config(cfg: dict) -> dict:
    """Monta o perfil a partir da seção [filter] do config.toml (o perfil padrão)."""
    areas = ["dev"]
    if cfg.get("related_enabled", True):
        areas.append("correlata")
    if cfg.get("support_enabled", True):
        areas.append("suporte")
    if cfg.get("hardware_enabled", False):
        areas.append("hardware")
    niveis = list(cfg.get("levels", ["junior"]))
    if cfg.get("include_estagio", False) and "estagio" not in niveis:
        niveis.insert(0, "estagio")
    return {
        **PROFILE_DEFAULTS,
        "niveis": niveis,
        "areas": areas,
        "filtrar_local": bool(cfg.get("location_filter", False)),
        "cidades": list(cfg.get("allowed_cities", RMS_CITIES)),
        "local_desconhecido": cfg.get("unknown_location", "descartar") == "incluir",
        "remoto": bool(cfg.get("allow_remote", True)),
        "exterior": bool(cfg.get("remote_abroad", True)),
        "ingles_max": cfg.get("max_english", "intermediario"),
        "anos_max": cfg.get("max_years", 2),
        "salario_min": int(cfg.get("min_salary", 0) or 0),
        "sem_salario": cfg.get("unknown_salary", "incluir") != "descartar",
        "estado": (cfg.get("state") or "").upper(),
        "estados_preferidos": [s.upper() for s in cfg.get("preferred_states", [])],
        "bonus_remoto": cfg.get("remote_bonus", 10),
        "bonus_grande": cfg.get("big_bonus", 10),
        "nota_minima": cfg.get("min_score", 40),
    }


def location_check(job: Job, perfil: dict) -> tuple[bool, str]:
    """Aceita vaga remota (do Brasil, ou de fora se o perfil deixar) ou nas cidades do perfil."""
    if not perfil.get("filtrar_local", True):
        return True, ""
    regiao = perfil.get("regiao_nome", "")
    not_ssa = lambda t: norm(t).replace("el salvador", "").replace("san salvador", "")  # outro país
    loc = not_ssa(job.location)
    if job.workplace == "remoto" and perfil.get("remoto", True):
        if is_abroad(job):
            if not perfil.get("exterior", True):
                return False, f"remoto restrito a outro país ({job.location})"
            return True, "remoto no exterior"
        return True, "remoto"
    if not perfil.get("presencial", True):              # só remoto
        return False, f"não é remota ({job.location or 'local não informado'})"
    cities = [norm(c) for c in perfil.get("cidades", [])]
    if cities and (find_term(loc, cities) or find_term(not_ssa(job.title), cities)):
        return True, f"região de {regiao}" if regiao else "sua região"
    estado = (perfil.get("estado") or "").upper()
    if not cities and estado and job.uf == estado:      # sem cidades: vale o estado inteiro
        return True, f"região de {regiao}" if regiao else f"seu estado ({estado})"
    if not loc and perfil.get("local_desconhecido", False):
        return True, "local não informado"
    fora = (f"fora de {regiao} e região" if regiao
            else f"fora de {estado}" if estado and not cities else "fora das suas cidades")
    return False, f"{fora} ({job.location or 'local não informado'})"


def level_check(area: str, nivel: str, niveis: list[str]) -> bool:
    """A vaga tem um nível que o perfil quer?"""
    if nivel in niveis:
        return True
    if nivel == "":                 # título não diz: entra para quem não quer só estágio
        return any(n in niveis for n in ("junior", "pleno", "senior"))
    # Suporte "pleno" entra para quem quer júnior: em suporte quem decide é o salário.
    return area == "suporte" and nivel == "pleno" and "junior" in niveis


# ---------------------------------------------------------------- vagas
def evaluate_base(job: Job, cfg: dict) -> Result:
    """Regras que valem para todo mundo: é vaga de TI? De que área e nível?

    Não descarta por nível, local, inglês ou salário: isso é do perfil.
    `accepted` aqui quer dizer "passou na base"; a nota é calculada pelo perfil.
    """
    title = norm(job.title)
    desc = norm(job.description or job.snippet)
    kind = norm(job.kind)

    dev_terms = DEV_TERMS + [norm(t) for t in cfg.get("dev_terms_extra", [])]
    related_terms = RELATED_TERMS + [norm(t) for t in cfg.get("related_terms_extra", [])]
    support_terms = SUPPORT_TERMS + [norm(t) for t in cfg.get("support_terms_extra", [])]
    junior_terms = JUNIOR_TERMS + [norm(t) for t in cfg.get("junior_terms_extra", [])]

    if norm(job.company) in {norm(c) for c in cfg.get("exclude_companies", [])}:
        return Result(False, 0, ["empresa na lista de exclusão"])
    if find_term(title, [norm(t) for t in cfg.get("exclude_title_terms", [])]):
        return Result(False, 0, ["termo excluído no título"])
    max_age = int(cfg.get("max_age_days", 0) or 0)
    age = age_days(job)
    if max_age and age is not None and age > max_age:
        return Result(False, 0, [f"publicada há {age} dias (limite: {max_age})"])

    if find_term(title, dev_terms):
        area = "dev"
    elif find_term(title, related_terms):
        area = "correlata"
    elif find_term(title, support_terms) and not find_term(title, NOT_IT_SUPPORT):
        area = "suporte"
    elif find_term(title, HARDWARE_TERMS) and not find_term(title, NOT_HARDWARE):
        area = "hardware"
    else:
        return Result(False, 0, ["sem termo de dev, área correlata, suporte ou hardware no título"])

    subarea = area if area != "correlata" else related_group(title)
    nivel, junior_title = job_level(title, kind, junior_terms)
    if area == "correlata" and not nivel:
        return Result(False, 0, ["área correlata sem nível no título"], area)

    return Result(
        True, 0, [], area,
        english=english_level(f"{job.title} {job.description or job.snippet}"),
        abroad=job.workplace == "remoto" and is_abroad(job),
        nivel=nivel,
        junior_title=junior_title,
        junior_desc=not junior_title and bool(find_term(desc, junior_terms)),
        pouca_exp=junior_title and bool(find_term(desc, ["sem experiencia", "recem formado", "primeiro emprego"])),
        years=required_years(desc),
        subarea=subarea,
    )


def evaluate_profile(job: Job, base: Result, perfil: dict) -> Result:
    """Aplica o perfil de uma pessoa sobre uma vaga que já passou na base e dá a nota.

    Só usa dados que ficam salvos na vaga (local, modalidade, salário) e o
    resultado da base. Assim o painel consegue repetir a mesma conta em JS.
    """
    area, nivel, english = base.area, base.nivel, base.english
    niveis = perfil.get("niveis", ["junior"])
    facts = dict(area=area, english=english, nivel=nivel, junior_title=base.junior_title,
                 junior_desc=base.junior_desc, pouca_exp=base.pouca_exp, years=base.years,
                 subarea=base.subarea)

    def rejected(why: str, abroad: bool = base.abroad) -> Result:
        return Result(False, 0, [why], abroad=abroad, **facts)

    areas = perfil.get("areas", ["dev", "correlata", "suporte"])
    if area not in areas and base.subarea not in areas:     # aceita "correlata" ou só "dados", "qa"...
        return rejected(f"{AREA_NOME[area]} fora do perfil")
    minhas = {t for t in perfil.get("tecnologias", [])}
    comuns = [t for t in job.techs if t in minhas]
    if minhas and perfil.get("so_minhas_techs", False) and not comuns:
        return rejected("não cita suas tecnologias")
    if not level_check(area, nivel, niveis):
        return rejected(f"nível {NIVEL_NOME.get(nivel, 'não informado')} fora do perfil"
                        if nivel else "nível não informado (perfil só de estágio)")

    loc_ok, loc_reason = location_check(job, perfil)
    if not loc_ok:
        return rejected(loc_reason)
    abroad = loc_reason == "remoto no exterior"

    cap = perfil.get("ingles_max", "intermediario")
    if cap in ENGLISH_RANK and ENGLISH_RANK[english] > ENGLISH_RANK[cap]:
        return rejected(f"exige inglês {english} (limite: {cap})", abroad)

    minimum = int(perfil.get("salario_min", 0) or 0)          # vale para qualquer área
    if minimum:
        if job.salary <= 0 and not perfil.get("sem_salario", True):
            return rejected(f"salário não informado (mínimo R$ {minimum})")
        if 0 < job.salary < minimum:
            return rejected(f"paga R$ {job.salary} (mínimo R$ {minimum})")

    tech_area = area in ("dev", "correlata")      # suporte e hardware não olham experiência
    years, max_years = base.years, int(perfil.get("anos_max", 0) or 0)
    if tech_area and max_years and years > max_years and not base.junior_title:
        return rejected(f"pede {years} anos de experiência")

    # --- nota ---
    score = {"dev": 20, "correlata": 10, "suporte": 40, "hardware": 40}[area]
    reasons = [{"dev": "termo de dev no título", "correlata": "área correlata no título",
                "suporte": "suporte técnico", "hardware": "hardware e assistência técnica"}[area]]
    if area == "suporte":
        reasons.append(f"salário R$ {job.salary}" if job.salary else "salário não informado")
    elif area == "hardware":
        if job.salary:
            reasons.append(f"salário R$ {job.salary}")
    elif nivel and nivel in niveis:
        score += 50
        reasons.append("júnior no título" if base.junior_title
                       else "estágio" if nivel == "estagio" else f"{NIVEL_NOME[nivel]} no título")
    elif not nivel and base.junior_desc and "junior" in niveis:
        score += 20
        reasons.append("júnior na descrição")
    if tech_area and base.pouca_exp:
        score += 5
        reasons.append("aceita pouca experiência")
    if tech_area and max_years and 0 < years <= max_years:
        score += 5
        reasons.append(f"pede até {years} anos")
    if tech_area and max_years and years > max_years:
        score -= 30
        reasons.append(f"pede {years} anos (penalizado)")
    if job.grande:
        score += perfil.get("bonus_grande", 10)
        reasons.append("grande empresa")
    if comuns:
        score += perfil.get("bonus_tecnologia", 10)
        reasons.append("sua tecnologia: " + ", ".join(comuns))
    if job.workplace == "remoto":
        score += perfil.get("bonus_remoto", 10)
        reasons.append("remoto")
    elif loc_reason.startswith(("região de", "seu estado")) or loc_reason == "sua região":
        score += 10
        reasons.append(loc_reason)
    if abroad:
        reasons.append("no exterior")
    if english:
        reasons.append(f"inglês {english}")
    preferred = {s.upper() for s in perfil.get("estados_preferidos", [])}
    if job.uf and job.uf in preferred:
        score += 10
        reasons.append(f"estado preferido ({job.uf})")

    accepted = score >= perfil.get("nota_minima", 40)
    if not accepted:
        reasons.append("nota abaixo do mínimo")
    return Result(accepted, score, reasons, abroad=abroad, **facts)


def evaluate(job: Job, cfg: dict) -> Result:
    """Base + perfil padrão (o do config.toml). É o que o e-mail usa."""
    base = evaluate_base(job, cfg)
    if not base.accepted:
        return base
    return evaluate_profile(job, base, profile_from_config(cfg))


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


def _prepare(job: Job, cfg: dict) -> None:
    """Marca grande empresa e acha o salário na descrição."""
    if job.tipo == "noticia":
        name = big_company(job.title, cfg)
        job.grande = bool(name)
        job.company = name or "Empresa não identificada"
    else:
        job.grande = bool(big_company(job.company, cfg))
        if not job.salary:
            job.salary = extract_salary(f"{job.description} {job.snippet}")


# ---------------------------------------------------------------- freelas
# Projeto que não é de TI ou que parece golpe/ilegal. Some com freela que só cai em
# "it-programming" por engano (trabalho de faculdade) e com pedido suspeito.
# "tradução" NÃO entra: na categoria de TI quase sempre é parte do sistema ("ferramenta de tradução com IA").
FREELA_BLOCK = [
    # não é TI
    "projeto extensionista", "extensionista", "tcc", "monografia", "trabalho academico", "trabalho de faculdade",
    "artigo cientifico", "atividade academica",
    # aposta, golpe, invasão
    "bac bo", "aposta", "apostas", "cassino", "casino", "bet", "tigrinho", "fortune tiger", "aviator",
    "roleta", "piramide financeira", "hackear", "invadir", "clonar whatsapp", "espionar",
]
NIVEL_FREELA_NOME = {"iniciante": "para iniciante", "intermediario": "nível intermediário", "especialista": "pede especialista"}


def classify_freela(job: Job, cfg: dict) -> bool:
    """Guarda o freela se for de TI e não parecer golpe. Nota só para ordenar a lista:
    iniciante, poucas propostas, pagamento verificado e tecnologias citadas sobem."""
    text = norm(f"{job.title} {job.description or job.snippet}")
    block = FREELA_BLOCK + [norm(t) for t in cfg.get("freela_bloquear", [])]
    hit = find_term(text, block)
    job.padrao = False                        # não vai no e-mail de vagas nem na lista de vagas
    if hit:
        job.score, job.reasons = 0, [f"fora de TI ou suspeito: {hit}"]
        return False
    job.techs = find_techs(f"{job.title} {job.description or job.snippet}")
    score, reasons = 50, ["freela de TI"]
    if job.nivel_freela in NIVEL_FREELA_NOME:
        reasons.append(NIVEL_FREELA_NOME[job.nivel_freela])
        score += {"iniciante": 15, "intermediario": 5, "especialista": -10}[job.nivel_freela]
    if 0 <= job.propostas <= 10:
        score, reasons = score + 15, reasons + [f"só {job.propostas} propostas"]
    elif 0 <= job.propostas <= 30:
        score += 5
    elif job.propostas > 80:
        score -= 10
    if job.pagamento_verificado:
        score, reasons = score + 5, reasons + ["pagamento verificado"]
    if job.techs:
        score, reasons = score + 5 * min(len(job.techs), 3), reasons + ["cita " + ", ".join(job.techs[:3])]
    job.score, job.reasons = max(score, 0), reasons
    job.area = job.subarea = "dev"
    return True


# Preferências de freela no perfil (campo "freelas"). Mesmas chaves e regras em docs/perfil.js.
FREELA_DEFAULTS = {"ver": True, "nivel": "", "orcamento_min": 0, "propostas_max": 0,
                   "so_minhas_techs": False, "avisar": False}


def freela_prefs(perfil: dict | None) -> dict:
    """Preferências de freela do perfil, com os padrões e valores estranhos corrigidos."""
    raw = (perfil or {}).get("freelas") or {}
    raw = raw if isinstance(raw, dict) else {}

    def num(v):
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            return 0
    return {
        "ver": raw.get("ver", True) is not False,
        "nivel": raw.get("nivel") if raw.get("nivel") in ("iniciante", "intermediario") else "",
        "orcamento_min": num(raw.get("orcamento_min")),
        "propostas_max": num(raw.get("propostas_max")),
        "so_minhas_techs": raw.get("so_minhas_techs") is True,
        "avisar": raw.get("avisar") is True,
    }


def evaluate_freela(job: Job, perfil: dict | None) -> Result:
    """O freela combina com o perfil? Orçamento ou propostas que o site não informa não tiram o projeto."""
    fp = freela_prefs(perfil)
    no = lambda why: Result(False, 0, [why])  # noqa: E731
    if not fp["ver"]:
        return no("você não quer ver freelas")
    if fp["nivel"] == "iniciante" and job.nivel_freela != "iniciante":
        return no("não é para iniciante")
    if fp["nivel"] == "intermediario" and job.nivel_freela == "especialista":
        return no("pede especialista")
    top = max(job.orcamento_min or 0, job.orcamento_max or 0)
    if fp["orcamento_min"] and top and not job.por_hora and top < fp["orcamento_min"]:
        return no(f"orçamento abaixo de USD {fp['orcamento_min']}")
    if fp["propostas_max"] and job.propostas > fp["propostas_max"]:
        return no(f"mais de {fp['propostas_max']} propostas")
    minhas = set((perfil or {}).get("tecnologias") or [])
    comuns = [t for t in (job.techs or []) if t in minhas]
    if fp["so_minhas_techs"] and minhas and not comuns:
        return no("não cita suas tecnologias")
    reasons = list(job.reasons or [])
    score = job.score
    if comuns:
        score += 10
        reasons.append("sua tecnologia: " + ", ".join(comuns))
    return Result(True, score, reasons)


def classify(job: Job, cfg: dict) -> bool:
    """Avalia a vaga para guardar no jobs.json. Devolve True se passou na BASE.

    Grava na vaga os fatos que o painel usa para filtrar pelo perfil de cada pessoa
    (nível, subárea, tecnologias, anos...) e o resultado no perfil padrão
    (padrao, score, reasons), que é o que o e-mail usa.
    """
    if job.tipo == "freela":
        return classify_freela(job, cfg)
    _prepare(job, cfg)
    if job.tipo == "noticia":
        result = evaluate_news(job, cfg)
        job.score, job.reasons, job.area = result.score, result.reasons, result.area
        job.subarea = result.area
        ufs, everywhere = news_places(job.title)
        job.ufs = ufs
        job.uf = ufs[0] if len(ufs) == 1 else ""
        job.workplace = "remoto" if everywhere else ""
        # guarda a notícia para todos; o perfil padrão decide se vai no e-mail
        job.padrao = result.accepted and news_location_check(job, profile_from_config(cfg))[0]
        return result.accepted

    base = evaluate_base(job, cfg)
    if not base.accepted:
        job.score, job.reasons, job.padrao = 0, base.reasons, False
        return False
    job.techs = find_techs(f"{job.title} {job.description or job.snippet}")
    result = evaluate_profile(job, base, profile_from_config(cfg))
    job.score, job.reasons, job.padrao = result.score, result.reasons, result.accepted
    job.area, job.subarea, job.nivel = base.area, base.subarea, base.nivel
    job.english, job.abroad = base.english, base.abroad
    job.years, job.junior_title, job.junior_desc, job.pouca_exp = (
        base.years, base.junior_title, base.junior_desc, base.pouca_exp)
    job.city = city_of(job)
    return True


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
