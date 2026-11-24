"""Armazenamento em um único JSON (docs/data/jobs.json).

O mesmo arquivo é o "banco" do coletor e a fonte de dados do painel.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .models import Job


def load(path: str | Path) -> dict[str, Job]:
    """Lê as vagas já conhecidas, indexadas por id. Arquivo ausente = vazio."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {j["id"]: Job.from_dict(j) for j in data.get("jobs", []) if "id" in j}


def merge(existing: dict[str, Job], fetched: list[Job], ok_sources: set[str],
          today: str, keep_days: int = 45, keep_days_news: int = 30) -> tuple[dict[str, Job], list[Job]]:
    """Junta o que foi coletado agora com o que já se conhecia.

    Devolve (todas as vagas, vagas novas). Regras:
    - mesmo id: atualiza dados, mantém first_seen e notified;
    - mesma vaga já vista em outra fonte (título+empresa+local): ignora;
    - vaga conhecida de uma fonte que respondeu agora e não apareceu: active=False;
    - vagas não vistas há mais de keep_days dias: removidas.
    """
    jobs = dict(existing)
    by_key = {j.dedupe_key(): j.id for j in jobs.values()}
    seen_ids: set[str] = set()
    new: list[Job] = []

    for job in fetched:
        if job.id in seen_ids:
            continue
        seen_ids.add(job.id)
        if job.id in jobs:
            old = jobs[job.id]
            job.first_seen, job.notified = old.first_seen or today, old.notified
            job.last_seen, job.active = today, True
            jobs[job.id] = job
            continue
        key = job.dedupe_key()
        if key in by_key and by_key[key] in jobs:
            other = jobs[by_key[key]]
            other.last_seen, other.active = today, True
            seen_ids.add(other.id)
            continue
        job.first_seen = job.last_seen = today
        job.active, job.notified = True, False
        jobs[job.id] = job
        by_key[key] = job.id
        new.append(job)

    for job in jobs.values():
        # notícia não "encerra": some sozinha quando fica velha
        if job.tipo == "vaga" and job.id not in seen_ids and job.source in ok_sources:
            job.active = False

    base = date.fromisoformat(today)
    limits = {"vaga": (base - timedelta(days=keep_days)).isoformat(),
              "noticia": (base - timedelta(days=keep_days_news)).isoformat()}
    jobs = {i: j for i, j in jobs.items() if (j.last_seen or today) >= limits.get(j.tipo, limits["vaga"])}
    return jobs, new


def save(path: str | Path, jobs: dict[str, Job], meta: dict) -> None:
    ordered = sorted(jobs.values(), key=lambda j: (j.active, j.score, j.first_seen), reverse=True)
    payload = {"meta": meta, "jobs": [j.to_dict() for j in ordered]}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)
