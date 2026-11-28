"""Aviso de vagas novas por pessoa, por e-mail ou Telegram.

Cada pessoa liberada no painel tem um perfil no Firestore. Em cada coleta o robô:
1. pega as vagas novas (ou, para quem quer resumo diário, as do dia, só na coleta da noite);
2. passa cada uma pelo perfil da pessoa, com o mesmo filtro do painel (evaluate_profile);
3. monta um e-mail só com as que combinam. Quem não tem vaga nova que combine não recebe nada.

Preferências ficam no perfil, no campo "aviso": {ativo, canal, frequencia, telegram_codigo}.
Sem o campo, vale: ligado, por e-mail, a cada coleta.
Quem escolheu Telegram e ainda não ligou a conversa (ou se o bot estiver fora) recebe por e-mail.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from . import filters
from .firebase import Recipient
from .models import Job

FOOTER = "Você recebe este aviso porque usa o Ragas. Para parar ou mudar o que recebe, abra o painel e use Meu perfil."


def prefs(perfil: dict | None) -> dict:
    """Preferências de aviso do perfil, com os padrões combinados."""
    aviso = (perfil or {}).get("aviso") or {}
    return {
        "ativo": aviso.get("ativo", True) is not False,
        "canal": aviso.get("canal") or "email",
        "frequencia": aviso.get("frequencia") or "coleta",      # coleta | diario
    }


def is_evening(now: datetime, cfg: dict) -> bool:
    """Coleta da noite: a que manda o resumo diário (padrão: a partir das 15h)."""
    return now.hour >= int(cfg.get("avisos", {}).get("hora_resumo", 15))


def for_profile(jobs: list[Job], perfil: dict) -> list[Job]:
    """Vagas que combinam com o perfil, com a nota e os motivos DESSE perfil, das melhores para as piores."""
    out = []
    for j in jobs:
        if j.tipo == "noticia":
            r = filters.evaluate_news_profile(j, perfil)
        else:
            r = filters.evaluate_profile(j, filters.base_from_job(j), perfil)
        if r.accepted:
            out.append(replace(j, score=r.score, reasons=r.reasons))
    return sorted(out, key=lambda j: (j.tipo == "noticia", -j.score, j.first_seen))


@dataclass
class Plan:
    person: Recipient
    jobs: list[Job]
    kind: str                       # coleta | diario
    channel: str = "email"          # email | telegram
    chat_id: int | None = None


def telegram_chat(p: Recipient) -> int | None:
    """Conversa do Telegram ligada ao código ATUAL do perfil (trocou o código = precisa ligar de novo)."""
    link = (p.extra or {}).get("telegram") or {}
    code = ((p.perfil or {}).get("aviso") or {}).get("telegram_codigo")
    return link.get("chat_id") if link.get("chat_id") and code and link.get("codigo") == code else None


def plan(people: list[Recipient], all_jobs: list[Job], new_ids: set[str], today: str, evening: bool,
         telegram_on: bool = True) -> list[Plan]:
    """Quem recebe o quê nesta coleta, e por onde. telegram_on=False: bot fora, todo mundo por e-mail."""
    out = []
    for p in people:
        if p.perfil is None:
            continue                                 # ainda não montou o perfil
        pr = prefs(p.perfil)
        if not pr["ativo"]:
            continue
        if pr["frequencia"] == "diario":
            if not evening:
                continue
            pool = [j for j in all_jobs if j.active and j.first_seen == today]
        else:
            pool = [j for j in all_jobs if j.active and j.id in new_ids]
        hits = for_profile(pool, p.perfil)
        if hits:
            chat = telegram_chat(p) if pr["canal"] == "telegram" and telegram_on else None
            out.append(Plan(p, hits, pr["frequencia"], "telegram" if chat else "email", chat))
    return out


def covers(people: list[Recipient] | None, email: str) -> bool:
    """Essa pessoa já recebe pelo perfil? (então o e-mail do config.toml não vai para ela, para não duplicar)"""
    if not people or not email:
        return False
    for p in people:
        if p.email.lower() == email.lower() and p.perfil is not None:
            return True                  # recebe pelo perfil (e-mail ou Telegram), ou desligou de propósito
    return False


def greeting(p: Recipient, kind: str) -> str:
    first = (p.nome or "").split(" ")[0]
    hello = f"Olá, {first}!" if first else "Olá!"
    when = "Resumo do dia com as vagas" if kind == "diario" else "Chegaram vagas"
    return f"{hello} {when} que combinam com o seu perfil."
