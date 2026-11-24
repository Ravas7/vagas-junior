"""Adzuna: agregador com API oficial e gratuita (cobre vagas do Brasil).

Crie uma conta em https://developer.adzuna.com/ e guarde ADZUNA_APP_ID e
ADZUNA_APP_KEY nas variáveis de ambiente (ou no .env / Secrets do GitHub).
"""

from __future__ import annotations

import os
import time

from ..http import SourceError, get_json
from ..models import Job
from ..text import infer_workplace, monthly, to_uf
from .base import SourceSkipped, date_of, finish, pick, snippet_of

NAME = "adzuna"


def parse(raw: dict) -> Job | None:
    ext_id = pick(raw, "id")
    title = pick(raw, "title")
    url = pick(raw, "redirect_url")
    if not (ext_id and title and url):
        return None
    loc = raw.get("location") or {}
    area = [a for a in loc.get("area", []) if a]          # ["Brasil", "Bahia", "Salvador"]
    uf = next((to_uf(a) for a in area if to_uf(a)), "")
    location = loc.get("display_name") or ", ".join(area[1:])
    description = pick(raw, "description")
    predicted = str(raw.get("salary_is_predicted", "0")) == "1"      # estimativa do Adzuna: ignora
    salary = 0 if predicted else monthly(raw.get("salary_max") or raw.get("salary_min") or 0)
    return Job(
        id=f"adzuna:{ext_id}",
        source=NAME,
        title=title.strip(),
        company=pick(raw, "company", default="(empresa não informada)"),
        url=url,
        location=location,
        uf=uf,
        workplace=infer_workplace(title, location, description),
        posted_at=date_of(pick(raw, "created")),
        snippet=snippet_of(description),
        description=description,
        kind=pick(raw, "contract_time"),
        salary=salary,
    )


def fetch(cfg: dict) -> list[Job]:
    app_id = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not (app_id and app_key):
        raise SourceSkipped("defina ADZUNA_APP_ID e ADZUNA_APP_KEY para usar o Adzuna")

    country = cfg.get("country", "br")
    terms = cfg.get("terms", ["desenvolvedor junior"])
    pages = int(cfg.get("pages", 2))
    per_page = int(cfg.get("results_per_page", 50))
    delay = float(cfg.get("delay", 0.6))

    # wheres = ["Salvador", ""]: "" busca no país todo e acrescenta "remoto" ao termo
    wheres = cfg.get("wheres") or [cfg.get("where", "")]
    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for where in wheres:
        for term in terms:
            for page in range(1, pages + 1):
                params = {
                    "app_id": app_id, "app_key": app_key,
                    "what": term if where else f"{term} remoto", "results_per_page": per_page,
                    "sort_by": "date", "max_days_old": cfg.get("max_days_old", 14),
                    "content-type": "application/json",
                }
                if where:
                    params["where"] = where
                    params["distance"] = cfg.get("distance_km", 50)
                try:
                    data = get_json(f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}", params)
                except SourceError as exc:
                    errors.append(str(exc))
                    break
                ok_calls += 1
                items = data.get("results", []) if isinstance(data, dict) else []
                for raw in items:
                    job = parse(raw)
                    if job:
                        found[job.id] = job
                if len(items) < per_page:
                    break
                time.sleep(delay)
            time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
