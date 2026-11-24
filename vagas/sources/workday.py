"""Workday: sites de carreira de muitas multinacionais (*.myworkdayjobs.com).

Cada site tem uma busca JSON usada pela própria página (POST em /wday/cxs/...).
Não é API documentada, mas é a mesma para todos os sites Workday. Aqui o endereço
do site de carreiras vai em `sites` no config.toml, ex.:
  https://accenture.wd103.myworkdayjobs.com/AccentureCareers
A busca de texto (`terms`) roda no servidor; o filtro de local roda aqui.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from ..http import SourceError, post_json
from ..models import Job
from ..text import find_term, infer_workplace, norm
from .base import finish, pick

NAME = "workday"
PAGE = 20                        # o Workday recusa limit acima de 20
_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_MULTI = re.compile(r"^\d+ locations?$", re.I)


def split_site(url: str) -> tuple[str, str, str]:
    """'https://x.wd5.myworkdayjobs.com/en-US/Site' -> (host, tenant, site)."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p and not _LOCALE.match(p)]
    if not parsed.netloc or not parts:
        raise SourceError(f"endereço Workday inválido: {url}")
    return parsed.netloc, parsed.netloc.split(".")[0], parts[0]


def posted_date(text: str, today: datetime | None = None) -> str:
    """'Posted 3 Days Ago' / 'Posted Today' / 'Posted 30+ Days Ago' -> AAAA-MM-DD."""
    today = today or datetime.now(timezone.utc)
    t = norm(text)
    if "today" in t or "hoje" in t:
        days = 0
    elif "yesterday" in t or "ontem" in t:
        days = 1
    else:
        m = re.search(r"(\d+)\+?\s*(?:days?|dias?)", t)
        if not m:
            return ""
        days = int(m.group(1))
    return (today - timedelta(days=days)).strftime("%Y-%m-%d")


def parse(raw: dict, host: str, tenant: str, site: str) -> Job | None:
    title, path = pick(raw, "title"), pick(raw, "externalPath")
    if not (title and path):
        return None
    bullets = raw.get("bulletFields") or []
    ref = str(bullets[0]) if bullets else path.rsplit("_", 1)[-1]
    location = pick(raw, "locationsText")
    return Job(
        id=f"workday:{tenant}:{ref}",
        source=NAME,
        title=title.strip(),
        company=tenant.replace("-", " ").title(),
        url=f"https://{host}/en-US/{site}{path}",
        location=location,
        workplace=infer_workplace(title, location),
        posted_at=posted_date(pick(raw, "postedOn")),
    )


def fetch(cfg: dict) -> list[Job]:
    sites = cfg.get("sites", [])
    terms = cfg.get("terms", ["junior", "trainee", "desenvolvedor"])
    pages = int(cfg.get("pages", 2))
    delay = float(cfg.get("delay", 0.6))
    keywords = [norm(k) for k in cfg.get("location_keywords", ["brazil", "brasil", "remote", "remoto"])]
    keep_multi = bool(cfg.get("keep_multi_location", False))

    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for site_url in sites:
        host, tenant, site = split_site(site_url)
        endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        for term in terms:
            for page in range(pages):
                body = {"appliedFacets": {}, "limit": PAGE, "offset": page * PAGE, "searchText": term}
                try:
                    data = post_json(endpoint, body)
                except SourceError as exc:
                    errors.append(str(exc))
                    break
                ok_calls += 1
                items = data.get("jobPostings", []) if isinstance(data, dict) else []
                for raw in items:
                    job = parse(raw, host, tenant, site)
                    if not job:
                        continue
                    loc = norm(job.location)
                    if _MULTI.match(job.location.strip()):
                        if not keep_multi:
                            continue
                    elif loc and keywords and not find_term(loc, keywords):
                        continue
                    found[job.id] = job
                if len(items) < PAGE:
                    break
                time.sleep(delay)
            time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
