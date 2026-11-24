"""Gupy (portal.gupy.io): maior portal de vagas de empresas brasileiras.

ATENÇÃO: o portal não tem API pública documentada. O endereço abaixo é o que
o próprio site chama e pode mudar. Se `python -m vagas check` mostrar erro ou
zero vagas, abra portal.gupy.io no navegador, aperte F12, aba Network, faça uma
busca e copie a URL da requisição JSON para `url` no config.toml (README, passo 6).
Por isso o leitor abaixo aceita vários nomes de campo.
"""

from __future__ import annotations

import time

from ..http import SourceError, get_json
from ..models import Job
from ..text import infer_workplace, to_uf
from .base import date_of, finish, pick, snippet_of

NAME = "gupy"
DEFAULT_URL = "https://portal.gupy.io/api/job-search/jobs"

_WORKPLACE = {"remote": "remoto", "hybrid": "hibrido", "on-site": "presencial",
              "onsite": "presencial", "on_site": "presencial"}


def extract_list(data) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("data", "results", "jobs", "items", "content"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def parse(raw: dict) -> Job | None:
    ext_id = pick(raw, "id", "jobId")
    title = pick(raw, "name", "title", "jobName")
    url = pick(raw, "jobUrl", "url", "applicationUrl", "link")
    if not (ext_id and title and url):
        return None
    city = pick(raw, "city")
    state_raw = pick(raw, "state")
    uf = to_uf(state_raw)
    location = ", ".join(x for x in (city, uf or state_raw) if x)

    wp = _WORKPLACE.get(pick(raw, "workplaceType").lower(), "")
    if not wp and raw.get("isRemoteWork") is True:
        wp = "remoto"
    description = pick(raw, "description")
    if not wp:
        wp = infer_workplace(title, location)

    return Job(
        id=f"gupy:{ext_id}",
        source=NAME,
        title=title.strip(),
        company=pick(raw, "careerPageName", "companyName", "company", default="(empresa não informada)"),
        url=url,
        location=location,
        uf=uf,
        workplace=wp,
        posted_at=date_of(pick(raw, "publishedDate", "publishedAt", "createdAt")),
        snippet=snippet_of(description),
        description=description,
        kind=pick(raw, "type", "jobType", "vacancyType"),
    )


def fetch(cfg: dict) -> list[Job]:
    url = cfg.get("url", DEFAULT_URL)
    terms = cfg.get("terms", ["desenvolvedor junior"])
    pages = int(cfg.get("pages", 2))
    limit = int(cfg.get("limit", 50))
    delay = float(cfg.get("delay", 0.6))
    term_param = cfg.get("term_param", "jobName")
    limit_param = cfg.get("limit_param", "limit")
    offset_param = cfg.get("offset_param", "offset")
    extra = dict(cfg.get("extra_params", {}))
    # variants: cada item é um conjunto de parâmetros extra (ex.: só Bahia; só remoto).
    # Os nomes dos parâmetros vêm do DevTools (README, passo 6).
    variants = cfg.get("variants") or [{}]

    found: dict[str, Job] = {}
    ok_calls, errors = 0, []
    for variant in variants:
        for term in terms:
            for page in range(pages):
                params = {term_param: term, limit_param: limit, offset_param: page * limit,
                          **extra, **variant}
                try:
                    data = get_json(url, params)
                except SourceError as exc:
                    errors.append(str(exc))
                    break
                ok_calls += 1
                items = extract_list(data)
                for raw in items:
                    job = parse(raw)
                    if job:
                        found[job.id] = job
                if len(items) < limit:
                    break
                time.sleep(delay)
            time.sleep(delay)
    finish(ok_calls, errors, NAME)
    return list(found.values())
