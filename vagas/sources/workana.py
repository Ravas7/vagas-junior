"""Freelas da Workana (projetos de TI em português).

A página de projetos (workana.com/jobs) devolve JSON quando a chamada leva o cabeçalho
X-Requested-With, como o próprio site faz ao trocar de página. Não é API documentada:
se quebrar, rode `python -m vagas check --source workana` e leia o erro.
O robots.txt da Workana bloqueia só /api/; esta página é aberta.

Cada página traz uns 9 projetos. Os em destaque se repetem nas páginas seguintes (o
robô junta pelo endereço). O nome do cliente NÃO é guardado: o jobs.json é público.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape

from ..http import SourceError, get_json
from ..models import Job
from ..text import norm, strip_html
from .base import finish, snippet_of

NAME = "workana"
URL = "https://www.workana.com/jobs"
SITE = "https://www.workana.com/job/"
HEADERS = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}


def clean(value) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).replace("\xa0", " ").strip()


def _num(text: str) -> int:
    return int(text.replace(".", "").replace(",", ""))


def budget(text: str) -> tuple[int, int, str, bool]:
    """'USD 250 - 500' -> (250, 500, 'USD', False); 'Menos de USD 15 / hora' -> (0, 15, 'USD', True);
    'Mais de USD 3.000' -> (3000, 0, 'USD', False)."""
    t = " ".join(text.split())
    moeda = "USD" if "USD" in t else "BRL" if ("R$" in t or "BRL" in t) else ""
    hora = "hora" in t.lower()
    nums = [_num(n) for n in re.findall(r"\d[\d.,]*", t)]
    low = t.lower()
    if not nums:
        return 0, 0, moeda, hora
    if low.startswith("menos"):
        return 0, nums[0], moeda, hora
    if low.startswith("mais"):
        return nums[0], 0, moeda, hora
    return nums[0], (nums[1] if len(nums) > 1 else nums[0]), moeda, hora


def posted_date(text: str, today: datetime | None = None) -> str:
    """'há 15 horas' / 'Há quase uma hora' / 'Ontem' / 'há 3 dias' / 'há 2 semanas' -> AAAA-MM-DD."""
    today = today or datetime.now(timezone.utc)
    t = norm(text)
    if re.search(r"minut|hora|agora", t):
        days = 0
    elif "ontem" in t:
        days = 1
    elif m := re.search(r"(\d+)\s*dias?", t):
        days = int(m.group(1))
    elif m := re.search(r"(\d+|uma)\s*semanas?", t):
        days = 7 * (1 if m.group(1) == "uma" else int(m.group(1)))
    else:
        return ""
    return (today - timedelta(days=days)).strftime("%Y-%m-%d")


def parse(raw: dict, today: datetime | None = None) -> Job | None:
    slug = str(raw.get("slug") or "").strip()
    full = re.search(r'title="([^"]+)"', str(raw.get("title") or ""))     # o texto visível vem cortado com "..."
    title = clean(full.group(1) if full else raw.get("title"))
    if not (slug and title):
        return None
    desc = strip_html(str(raw.get("description") or ""))
    skills = [clean(s.get("anchorText")) for s in raw.get("skills") or [] if isinstance(s, dict)]
    shown = clean(raw.get("budget"))
    low, high, moeda, hora = budget(shown)
    bids = re.search(r"\d+", clean(raw.get("totalBids")))
    country = clean(raw.get("country"))
    return Job(
        id=f"{NAME}:{slug}",
        source=NAME,
        title=title,
        company="",                                # o nome do cliente não é guardado
        url=SITE + slug,
        location=country,
        workplace="remoto",
        posted_at=posted_date(clean(raw.get("postedDate") or raw.get("publishedDate")), today),
        snippet=snippet_of(desc, 400),
        description=f"{desc} {' '.join(skills)}",
        tipo="freela",
        orcamento=shown,
        orcamento_min=low,
        orcamento_max=high,
        moeda=moeda,
        por_hora=hora,
        propostas=int(bids.group()) if bids else -1,
        pagamento_verificado=bool(raw.get("hasVerifiedPaymentMethod")),
    )


def fetch(cfg: dict) -> list[Job]:
    pages = int(cfg.get("pages", 3))
    delay = float(cfg.get("delay", 1.5))
    params = {"category": cfg.get("category", "it-programming"), "language": cfg.get("language", "pt")}
    jobs: dict[str, Job] = {}
    ok, errors = 0, []
    for page in range(1, pages + 1):
        if page > 1 and delay:
            time.sleep(delay)
        try:
            data = get_json(URL, {**params, "page": page}, headers=HEADERS)
        except SourceError as exc:
            errors.append(str(exc))
            break
        rows = ((data or {}).get("results") or {}).get("results") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            errors.append("resposta sem a lista de projetos (o site mudou?)")
            break
        ok += 1
        for raw in rows:
            job = parse(raw)
            if job and job.id not in jobs:
                jobs[job.id] = job
        if not rows:
            break
    finish(ok, errors, NAME)
    return list(jobs.values())
