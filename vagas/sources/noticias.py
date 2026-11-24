"""Notícias de processos seletivos (Google News em RSS).

Cada notícia vira um item do tipo "noticia" no painel: título, veículo e link para
a matéria. O filtro (filters.evaluate_news) descarta concurso público, demissão etc.

Além das buscas fixas em `queries`, monta buscas com os nomes das grandes empresas
(`company_queries = true`) para achar anúncios de multinacionais.
"""

from __future__ import annotations

import hashlib
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from ..filters import BIG_COMPANIES
from ..http import SourceError, get_text
from ..models import Job
from .base import date_of, finish

NAME = "noticias"
BASE = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
# O ceid leva ":" sem codificar (por isso a URL é montada à mão, não com urlencode).

DEFAULT_QUERIES = [
    '"processo seletivo" tecnologia inscrições abertas',
    '"programa de trainee" tecnologia',
    '"vagas" tecnologia "desenvolvedor" júnior',
    '"jovem talento" OR "jovens talentos" tecnologia vagas',
    'multinacional abre vagas tecnologia Brasil',
]


def company_queries(extra: list[str], size: int) -> list[str]:
    names = BIG_COMPANIES + list(extra)
    out = []
    for i in range(0, len(names), size):
        group = " OR ".join(f'"{n}"' for n in names[i:i + size])
        out.append(f'({group}) ("processo seletivo" OR trainee OR "abre vagas") tecnologia')
    return out


def parse_feed(xml_text: str) -> list[Job]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError(f"RSS inválido: {exc}") from None
    jobs = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not (title and link):
            continue
        publisher = (item.findtext("source") or "").strip()
        suffix = f" - {publisher}"
        if publisher and title.endswith(suffix):          # "Manchete - Veículo"
            title = title[: -len(suffix)].strip()
        elif " - " in title and not publisher:
            title, publisher = (p.strip() for p in title.rsplit(" - ", 1))
        jobs.append(Job(
            id="noticias:" + hashlib.sha1(link.encode("utf-8")).hexdigest()[:14],
            source=NAME,
            title=title,
            company="",                                    # o filtro preenche (grande empresa)
            url=link,
            location=f"via {publisher}" if publisher else "",
            posted_at=date_of(item.findtext("pubDate")),
            snippet="",
            tipo="noticia",
        ))
    return jobs


def fetch(cfg: dict) -> list[Job]:
    queries = list(cfg.get("queries", DEFAULT_QUERIES))
    if cfg.get("company_queries", True):
        queries += company_queries(cfg.get("big_companies_extra", []), int(cfg.get("group_size", 8)))
    when = cfg.get("when", "21d")
    max_age = int(cfg.get("max_age_days", 30))
    delay = float(cfg.get("delay", 1.0))
    oldest = (datetime.now(timezone.utc) - timedelta(days=max_age)).strftime("%Y-%m-%d")

    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for query in queries:
        url = BASE.format(q=quote(f"{query} when:{when}", safe=""))
        try:
            jobs = parse_feed(get_text(url))
        except SourceError as exc:
            errors.append(str(exc))
            continue
        ok_calls += 1
        for job in jobs:
            if not job.posted_at or job.posted_at >= oldest:
                found[job.id] = job
        time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
