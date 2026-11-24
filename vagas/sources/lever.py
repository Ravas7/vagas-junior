"""Lever: API pública de vagas (api.lever.co/v0/postings/<empresa>).

O "slug" é o final do endereço: jobs.lever.co/<slug>. Liste em `companies`.
"""

from __future__ import annotations

import time

from ..http import SourceError, get_json
from ..models import Job
from ..text import infer_workplace, to_uf
from .base import SourceSkipped, date_of, finish, pick, snippet_of
from .greenhouse import location_ok

NAME = "lever"
BASE = "https://api.lever.co/v0/postings/{slug}"
_WORKPLACE = {"remote": "remoto", "hybrid": "hibrido", "onsite": "presencial", "on-site": "presencial"}


def parse(raw: dict, slug: str) -> Job | None:
    ext_id, title, url = pick(raw, "id"), pick(raw, "text"), pick(raw, "hostedUrl")
    if not (ext_id and title and url):
        return None
    categories = raw.get("categories") or {}
    location = pick(categories, "location")
    description = pick(raw, "descriptionPlain", "description")
    wp = _WORKPLACE.get(pick(raw, "workplaceType").lower(), "") or infer_workplace(title, location)
    uf = next((to_uf(p.strip()) for p in location.replace("-", ",").split(",") if to_uf(p.strip())), "")
    return Job(
        id=f"lever:{slug}:{ext_id}",
        source=NAME,
        title=title.strip(),
        company=slug.replace("-", " ").title(),
        url=url,
        location=location,
        uf=uf,
        workplace=wp,
        posted_at=date_of(raw.get("createdAt")),
        snippet=snippet_of(description),
        description=snippet_of(description, 3000),
        kind=pick(categories, "commitment"),
    )


def fetch(cfg: dict) -> list[Job]:
    companies = cfg.get("companies", [])
    if not companies:
        raise SourceSkipped("nenhuma empresa em companies no config.toml")
    keywords = cfg.get("location_keywords", ["brasil", "brazil", "remote", "remoto", "latam"])
    delay = float(cfg.get("delay", 0.4))
    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for slug in companies:
        try:
            data = get_json(BASE.format(slug=slug), {"mode": "json"})
        except SourceError as exc:
            errors.append(str(exc))
            continue
        ok_calls += 1
        for raw in (data if isinstance(data, list) else []):
            job = parse(raw, slug)
            if job and location_ok(job.location, keywords):
                found[job.id] = job
        time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
