"""SmartRecruiters: API pública de vagas de várias multinacionais (Bosch, Visa...).

O identificador da empresa (companyIdentifier) é o trecho do endereço
jobs.smartrecruiters.com/<Identificador> e diferencia maiúsculas de minúsculas.
A API devolve também o nível de experiência (ex.: "Entry Level"), que ajuda a achar júnior.
"""

from __future__ import annotations

import time

from ..http import SourceError, get_json
from ..models import Job
from ..text import to_uf
from .base import date_of, finish, pick

NAME = "smartrecruiters"
BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"


def parse(raw: dict, company_id: str) -> Job | None:
    ext_id, title = pick(raw, "id"), pick(raw, "name")
    if not (ext_id and title):
        return None
    loc = raw.get("location") or {}
    city, region, country = loc.get("city", ""), loc.get("region", ""), loc.get("country", "")
    uf = to_uf(region)
    location = ", ".join(x for x in (city, uf or region) if x)
    wp = "remoto" if loc.get("remote") else "hibrido" if loc.get("hybrid") else ""
    level = pick(raw, "experienceLevel")                 # "Entry Level", "Associate"...
    return Job(
        id=f"smartrecruiters:{company_id}:{ext_id}",
        source=NAME,
        title=title.strip(),
        company=pick(raw, "company", default=company_id),
        url=f"https://jobs.smartrecruiters.com/{company_id}/{ext_id}",
        location=location,
        uf=uf,
        workplace=wp,
        posted_at=date_of(pick(raw, "releasedDate")),
        snippet=f"Nível: {level}" if level else "",
        description=level,                                 # "entry level" conta como sinal de júnior
        kind=pick(raw, "typeOfEmployment"),
    )


def fetch(cfg: dict) -> list[Job]:
    companies = cfg.get("companies", [])
    country = cfg.get("country", "br")
    pages = int(cfg.get("pages", 3))
    limit = int(cfg.get("limit", 100))
    delay = float(cfg.get("delay", 0.5))
    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for company_id in companies:
        for page in range(pages):
            params = {"limit": limit, "offset": page * limit}
            if country:
                params["country"] = country
            try:
                data = get_json(BASE.format(company=company_id), params)
            except SourceError as exc:
                errors.append(str(exc))
                break
            ok_calls += 1
            items = data.get("content", []) if isinstance(data, dict) else []
            for raw in items:
                job = parse(raw, company_id)
                if job:
                    found[job.id] = job
            if len(items) < limit:
                break
            time.sleep(delay)
        time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
