"""Funções de texto usadas em todo o projeto."""

from __future__ import annotations

import html
import re
import unicodedata
from functools import lru_cache

UF_BY_NAME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA",
    "ceara": "CE", "distrito federal": "DF", "espirito santo": "ES", "goias": "GO",
    "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS",
    "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO",
    "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}
UFS = set(UF_BY_NAME.values())


def norm(text: str | None) -> str:
    """Minúsculas, sem acento, espaços normalizados. 'Júnior' -> 'junior'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def strip_html(text: str | None) -> str:
    """Remove tags HTML (inclusive quando o HTML veio escapado, como no Greenhouse)."""
    text = html.unescape(text or "")
    text = re.sub(r"<(?:br|/p|/li|/div|/h\d)\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


@lru_cache(maxsize=2048)
def term_regex(term: str) -> re.Pattern[str]:
    """Casa o termo como palavra inteira ('java' não casa com 'javascript')."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(norm(term)) + r"(?![a-z0-9])")


def find_term(text_norm: str, terms: list[str]) -> str | None:
    """Primeiro termo da lista presente no texto (já normalizado), ou None."""
    for term in terms:
        if term_regex(term).search(text_norm):
            return term
    return None


def to_uf(value: str | None) -> str:
    """'Bahia' / 'BA' / 'ba' -> 'BA'. Vazio se não reconhecer."""
    v = norm(value)
    if not v:
        return ""
    if len(v) == 2 and v.upper() in UFS:
        return v.upper()
    return UF_BY_NAME.get(v, "")


_REMOTE = re.compile(r"(?<![a-z])(remoto|remota|home ?office|remote|100% remoto|trabalho remoto)(?![a-z])")
_HYBRID = re.compile(r"(?<![a-z])(hibrido|hibrida|hybrid)(?![a-z])")
_ONSITE = re.compile(r"(?<![a-z])(presencial|on-?site)(?![a-z])")


def infer_workplace(*texts: str) -> str:
    """Descobre 'remoto' / 'hibrido' / 'presencial' a partir de textos livres."""
    t = norm(" ".join(texts))
    if _HYBRID.search(t):
        return "hibrido"
    if _REMOTE.search(t):
        return "remoto"
    if _ONSITE.search(t):
        return "presencial"
    return ""


_SALARY_KEY = re.compile(
    r"(salario|remuneracao|faixa salarial|vencimentos?|bolsa|pagamento|valor da vaga|ganhos)")
_MONEY = re.compile(r"r\$\s*(\d{1,3}(?:\.\d{3})+|\d{3,6})(?:,\d{1,2})?")


def extract_salary(text: str | None) -> int:
    """Maior valor mensal em reais citado logo depois de 'salário/remuneração/bolsa...'.

    Só olha valores perto dessas palavras (para não confundir com vale-refeição,
    bônus etc.). Devolve 0 se não achar.
    """
    t = norm(text)
    best = 0
    for key in _SALARY_KEY.finditer(t):
        for m in _MONEY.finditer(t[key.end(): key.end() + 90]):
            value = int(m.group(1).replace(".", ""))
            if 800 <= value <= 40000:
                best = max(best, value)
    return best


def monthly(value: float) -> int:
    """Adzuna informa o salário anual no Brasil; acima de 30 mil, divide por 12."""
    if not value:
        return 0
    return int(round(value / 12)) if value > 30000 else int(round(value))


# Nível de inglês pedido na vaga. Ordem: "" (não informado) < basico < intermediario < avancado.
ENGLISH_RANK = {"": 0, "basico": 1, "intermediario": 2, "avancado": 3}
_EN = r"(?:ingles|english)"
_LEVELS = {
    "avancado": [
        r"ingles (?:avancado|fluente)", r"fluencia (?:em|no|de) ingles", r"fluente em ingles",
        r"advanced english", r"english (?:advanced|fluency)", r"fluent (?:in )?english",
        r"(?:full )?professional (?:working )?proficiency", r"native[- ]level english",
        rf"{_EN}[^.\n]{{0,25}}\b(?:c1|c2)\b", rf"\b(?:c1|c2)\b[^.\n]{{0,25}}{_EN}",
    ],
    "intermediario": [
        r"ingles intermediario", r"intermediate english", r"intermediate (?:level )?(?:of )?english",
        r"upper[- ]intermediate", r"ingles conversacional", r"conversational english",
        rf"{_EN}[^.\n]{{0,25}}\b(?:b1|b2)\b", rf"\b(?:b1|b2)\b[^.\n]{{0,25}}{_EN}",
    ],
    "basico": [
        r"ingles basico", r"basic english", r"ingles instrumental", r"leitura (?:tecnica )?em ingles",
        r"ingles para leitura", rf"{_EN}[^.\n]{{0,25}}\b(?:a1|a2)\b", rf"\b(?:a1|a2)\b[^.\n]{{0,25}}{_EN}",
    ],
}
_NICE = re.compile(r"(?:diferencial|desejavel|desejado|plus|nice to have|bonus|preferred|a plus)")


def english_level(text: str | None) -> str:
    """Nível de inglês pedido: 'basico', 'intermediario', 'avancado' ou '' (não informado).

    Se a vaga cita mais de um nível, vale o mais baixo. Nível citado como diferencial
    ou desejável não conta como exigência.
    """
    t = norm(text)
    found = set()
    for level, patterns in _LEVELS.items():
        for pattern in patterns:
            for m in re.finditer(pattern, t):
                if _NICE.search(t[m.end(): m.end() + 40]) or _NICE.search(t[max(0, m.start() - 25): m.start()]):
                    continue
                found.add(level)
    if not found:
        return ""
    return min(found, key=ENGLISH_RANK.get)
