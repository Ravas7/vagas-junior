"""Freelas do 99Freelas (projetos de TI em português).

O site não tem API: o robô lê a página de projetos (99freelas.com.br/projects) como um
navegador. É a fonte mais frágil: se o site mudar o visual, ela quebra. Nesse caso,
rode `python -m vagas check --source freelas99` e leia o erro.

A lista não mostra o orçamento, mas mostra o nível pedido (Iniciante, Intermediário,
Especialista), o que ajuda a achar projeto para quem está começando.
"""

from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import urlencode

from ..http import SourceError, get_text
from ..models import Job
from ..text import norm, strip_html
from .base import date_of, finish, snippet_of

NAME = "freelas99"
SITE = "https://www.99freelas.com.br"
ITEM = re.compile(r'<li class="[^"]*\bresult-item\b[^"]*"\s+data-id="(\d+)"(.*?)(?=<li class="[^"]*\bresult-item\b|</ul>)',
                  re.S)
NIVEIS = {"iniciante": "iniciante", "intermediario": "intermediario", "especialista": "especialista"}


def _text(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def parse_page(html: str) -> list[Job]:
    jobs = []
    for pid, block in ITEM.findall(html):
        link = re.search(r'<h1 class="title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        href, title = link.group(1).split("?", 1)[0], _text(link.group(2))
        info = re.search(r'<p class="item-text information">(.*?)</p>|<p class="item-text information">(.*?)</hgroup>',
                         block, re.S)
        info_html = (info.group(1) or info.group(2)) if info else ""
        info_text = norm(_text(info_html))
        nivel = next((v for k, v in NIVEIS.items() if re.search(rf"\b{k}\b", info_text)), "")
        stamp = re.search(r'class="datetime"[^>]*cp-datetime="(\d+)"', info_html)
        bids = re.search(r"Propostas:\s*<b>\s*(\d+)", info_html)
        categoria = _text(info_html.split("|", 1)[0]) if "|" in info_html else ""
        desc_attr = re.search(r'class="item-text description[^"]*"\s+data-content="([^"]*)"', block)
        desc = strip_html(unescape(desc_attr.group(1))) if desc_attr else ""
        skills = [_text(s) for s in re.findall(r'<a class="habilidade"[^>]*>(.*?)</a>', block, re.S)]
        jobs.append(Job(
            id=f"{NAME}:{pid}",
            source=NAME,
            title=title,
            company="",
            url=SITE + href,
            location=categoria,                      # "Desenvolvimento Web", "Apps para Android"...
            workplace="remoto",
            posted_at=date_of(int(stamp.group(1))) if stamp else "",
            snippet=snippet_of(desc, 400),
            description=f"{desc} {' '.join(skills)}",
            tipo="freela",
            propostas=int(bids.group(1)) if bids else -1,
            nivel_freela=nivel,
        ))
    return jobs


def fetch(cfg: dict) -> list[Job]:
    pages = int(cfg.get("pages", 2))
    delay = float(cfg.get("delay", 1.5))
    jobs: dict[str, Job] = {}
    ok, errors = 0, []
    first = True
    for cat in cfg.get("categorias", ["web-mobile-e-software"]):
        for page in range(1, pages + 1):
            if not first and delay:
                time.sleep(delay)
            first = False
            url = f"{SITE}/projects?{urlencode({'categoria': cat, 'page': page})}"
            try:
                html = get_text(url)
            except SourceError as exc:
                errors.append(str(exc))
                break
            found = parse_page(html)
            if not found and page == 1:
                errors.append(f"nenhum projeto lido em '{cat}' (o site mudou o visual?)")
                break
            ok += 1
            for job in found:
                jobs.setdefault(job.id, job)
            if not found:
                break
    finish(ok, errors, NAME)
    return list(jobs.values())
