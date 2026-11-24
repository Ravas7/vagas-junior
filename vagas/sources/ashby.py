"""Ashby: API pública de quadros de vagas (api.ashbyhq.com/posting-api/job-board/<nome>).

O nome do quadro é o final do endereço jobs.ashbyhq.com/<nome>. Muito usado por
empresas globais de tecnologia que contratam remoto para o Brasil.
"""

from __future__ import annotations

import time

from ..http import SourceError, get_json
from ..models import Job
from ..text import infer_workplace, to_uf
from .base import date_of, finish, pick, snippet_of
from .greenhouse import location_ok

NAME = "ashby"
BASE = "https://api.ashbyhq.com/posting-api/job-board/{board}"
_WORKPLACE = {"remote": "remoto", "hybrid": "hibrido", "onsite": "presencial", "on-site": "presencial"}


def parse(raw: dict, board: str) -> Job | None:
    ext_id, title, url = pick(raw, "id"), pick(raw, "title"), pick(raw, "jobUrl")
    if not (ext_id and title and url):
        return None
    location = pick(raw, "location")
    wp = _WORKPLACE.get(pick(raw, "workplaceType").lower(), "")
    if not wp and raw.get("isRemote") is True:
        wp = "remoto"
    wp = wp or infer_workplace(title, location)
    region = ((raw.get("address") or {}).get("postalAddress") or {}).get("addressRegion", "")
    description = pick(raw, "descriptionPlain")
    return Job(
        id=f"ashby:{board}:{ext_id}",
        source=NAME,
        title=title.strip(),
        company=board.replace("-", " ").title(),
        url=url,
        location=location,
        uf=to_uf(region),
        workplace=wp,
        posted_at=date_of(pick(raw, "publishedAt")),
        snippet=snippet_of(description),
        description=snippet_of(description, 3000),
        kind=pick(raw, "employmentType"),
    )


def fetch(cfg: dict) -> list[Job]:
    boards = cfg.get("companies", [])
    keywords = cfg.get("location_keywords", ["brasil", "brazil", "remote", "remoto", "latam"])
    delay = float(cfg.get("delay", 0.4))
    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for board in boards:
        try:
            data = get_json(BASE.format(board=board))
        except SourceError as exc:
            errors.append(str(exc))
            continue
        ok_calls += 1
        for raw in (data.get("jobs", []) if isinstance(data, dict) else []):
            job = parse(raw, board)
            if job and location_ok(job.location, keywords):
                found[job.id] = job
        time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
