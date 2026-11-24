"""Greenhouse: API pública de quadros de vagas (boards-api.greenhouse.io).

Muitas empresas de tecnologia usam. O "slug" é o final do endereço do quadro
de vagas: boards.greenhouse.io/<slug>. Liste os slugs em `companies` no config.toml.
"""

from __future__ import annotations

import time

from ..http import SourceError, get_json
from ..models import Job
from ..text import find_term, infer_workplace, norm, to_uf
from .base import SourceSkipped, date_of, finish, pick, snippet_of

NAME = "greenhouse"
BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def location_ok(location: str, keywords: list[str]) -> bool:
    if not location or not keywords:
        return True
    return bool(find_term(norm(location), [norm(k) for k in keywords]))


def parse(raw: dict, slug: str) -> Job | None:
    ext_id, title, url = pick(raw, "id"), pick(raw, "title"), pick(raw, "absolute_url")
    if not (ext_id and title and url):
        return None
    location = pick(raw, "location")
    description = pick(raw, "content")
    uf = next((to_uf(p.strip()) for p in location.replace("-", ",").split(",") if to_uf(p.strip())), "")
    return Job(
        id=f"greenhouse:{slug}:{ext_id}",
        source=NAME,
        title=title.strip(),
        company=pick(raw, "company_name", default=slug.replace("-", " ").title()),
        url=url,
        location=location,
        uf=uf,
        workplace=infer_workplace(title, location),
        posted_at=date_of(pick(raw, "first_published", "updated_at")),
        snippet=snippet_of(description),
        description=snippet_of(description, 3000),
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
            data = get_json(BASE.format(slug=slug), {"content": "true"})
        except SourceError as exc:
            errors.append(str(exc))
            continue
        ok_calls += 1
        for raw in (data.get("jobs", []) if isinstance(data, dict) else []):
            job = parse(raw, slug)
            if job and location_ok(job.location, keywords):
                found[job.id] = job
        time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
