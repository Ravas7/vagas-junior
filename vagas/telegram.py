"""Aviso pelo Telegram (só biblioteca padrão).

Como a pessoa liga:
1. Em "Meu perfil" ela escolhe Telegram. O painel cria um código e mostra o botão
   "Abrir o Telegram", que abre o bot com esse código (t.me/<bot>?start=<código>).
2. Ela toca em "Começar". O Telegram guarda a mensagem "/start <código>" para o bot.
3. Na coleta seguinte, o robô lê essas mensagens (getUpdates), acha de quem é o código
   (perfil.aviso.telegram_codigo) e grava a conversa em telegram/{uid} no Firestore.
   Daí em diante, os avisos dessa pessoa vão por lá.

O token do bot fica no Secret TELEGRAM_BOT_TOKEN. Ele vai no endereço da API, por isso
nenhuma mensagem de erro daqui mostra o endereço.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from html import escape

from .http import SourceError, get_json, post_json
from .models import Job

API = "https://api.telegram.org/bot{token}/{method}"
LIMIT = 3800                       # o Telegram aceita até 4096 caracteres por mensagem
START = re.compile(r"^/start(?:@\w+)?\s+([A-Za-z0-9]{6,32})\s*$")
WHERE = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}


class TelegramSkipped(Exception):
    """Sem token do bot: o Telegram fica desligado (quem escolheu recebe por e-mail)."""


def token() -> str:
    t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not t:
        raise TelegramSkipped("defina TELEGRAM_BOT_TOKEN para mandar avisos pelo Telegram")
    return t


def _call(tok: str, method: str, body: dict | None = None):
    url = API.format(token=tok, method=method)
    try:
        data = post_json(url, body or {}, retries=1) if body is not None else get_json(url, retries=1)
    except SourceError as exc:
        code = str(exc).split(" em ", 1)[0]          # "HTTP 401" etc., sem o endereço (tem o token)
        hint = " (token do bot errado?)" if "401" in code or "404" in code else ""
        raise SourceError(f"Telegram {method}: {code}{hint}") from None
    if not isinstance(data, dict) or not data.get("ok"):
        raise SourceError(f"Telegram {method}: resposta inesperada")
    return data.get("result")


def updates(tok: str) -> list[dict]:
    """Mensagens que chegaram ao bot desde a última confirmação (o Telegram guarda por 24 horas)."""
    return _call(tok, "getUpdates", {"timeout": 0, "allowed_updates": ["message"]}) or []


def confirm(tok: str, last_update_id: int) -> None:
    """Marca as mensagens como lidas, para não voltarem na próxima coleta."""
    _call(tok, "getUpdates", {"offset": last_update_id + 1, "timeout": 0, "limit": 1})


def send(tok: str, chat_id: int | str, text: str) -> None:
    _call(tok, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                               "disable_web_page_preview": True})


def start_codes(ups: list[dict]) -> list[tuple[str, int, str]]:
    """[(código, chat_id, nome no Telegram)] das mensagens "/start <código>" em conversa privada."""
    out = []
    for u in ups:
        m = u.get("message") or {}
        chat = m.get("chat") or {}
        hit = START.match((m.get("text") or "").strip())
        if hit and chat.get("type") == "private" and chat.get("id"):
            out.append((hit.group(1), chat["id"], chat.get("first_name", "")))
    return out


def strays(ups: list[dict], used: set[int]) -> list[int]:
    """Conversas que mandaram outra coisa (ou código que não existe): recebem uma explicação curta."""
    out = []
    for u in ups:
        chat = (u.get("message") or {}).get("chat") or {}
        cid = chat.get("id")
        if cid and chat.get("type") == "private" and cid not in used and cid not in out:
            out.append(cid)
    return out


def link(client, people: list, links: dict, tok: str, log=print) -> dict:
    """Liga as conversas novas às pessoas (pelo código do perfil). Devolve links atualizado."""
    ups = updates(tok)
    if not ups:
        return links
    by_code = {}
    for p in people:
        code = ((p.perfil or {}).get("aviso") or {}).get("telegram_codigo")
        if code:
            by_code[code] = p
    used: set[int] = set()
    for code, chat_id, tg_name in start_codes(ups):
        p = by_code.get(code)
        if not p:
            continue
        used.add(chat_id)
        if (links.get(p.uid) or {}).get("chat_id") == chat_id and links[p.uid].get("codigo") == code:
            continue                                     # já estava ligado
        data = {"chat_id": chat_id, "codigo": code, "nome_telegram": tg_name,
                "ligadoEm": datetime.now().astimezone().isoformat(timespec="seconds")}
        try:
            client.set_doc(f"telegram/{p.uid}", data)
        except SourceError as exc:
            log(f"ERRO ao ligar o Telegram de pessoa {p.uid[:6]}: {exc}")   # registros do Actions são públicos
            continue
        links[p.uid] = data
        log(f"Telegram ligado: pessoa {p.uid[:6]}")
        try:
            send(tok, chat_id, f"Pronto, {escape((p.nome or tg_name or '').split(' ')[0]) or 'tudo certo'}! "
                               "Seus avisos de vagas do Ragas agora chegam por aqui.")
        except SourceError as exc:
            log(f"AVISO: {exc}")
    for cid in strays(ups, used):
        try:
            send(tok, cid, "Oi! Para receber avisos de vagas por aqui, abra o Ragas, vá em Meu perfil, "
                           "escolha Telegram e toque em \"Abrir o Telegram\".")
        except SourceError:
            pass
    confirm(tok, max(u["update_id"] for u in ups))
    return links


def _line(j: Job) -> str:
    if j.tipo == "noticia":
        second = " · ".join(x for x in (j.company, j.location) if x)
    else:
        where = WHERE.get(j.workplace, "")
        loc = j.location if j.location and j.location.lower() != where.lower() else ""
        money = f"R$ {j.salary:,}".replace(",", ".") if j.salary else ""
        second = " · ".join(x for x in (j.company, where, loc, money) if x)
    return f'<a href="{escape(j.url, quote=True)}">{escape(j.title)}</a>\n{escape(second)}'


def _freela(j: Job) -> str:
    from .emailer import freela_line
    return f'<a href="{escape(j.url, quote=True)}">{escape(j.title)}</a>\n{escape(freela_line(j))}'


def messages(jobs: list[Job], greeting: str, dashboard_url: str, max_items: int = 40,
             freelas: list[Job] | None = None) -> list[str]:
    """O aviso em uma ou mais mensagens (cada uma abaixo do limite do Telegram)."""
    vagas = [j for j in jobs if j.tipo != "noticia"][:max_items]
    news = [j for j in jobs if j.tipo == "noticia"][:10]
    blocks = [f"<b>{escape(greeting)}</b>"]
    blocks += [_line(j) for j in vagas]
    if news:
        blocks.append("<b>Processos seletivos nas notícias</b>")
        blocks += [_line(j) for j in news]
    if freelas:
        blocks.append("<b>Freelas novos</b>")
        blocks += [_freela(j) for j in freelas]
    hidden = len(jobs) - len(vagas) - len(news)
    tail = (f"Mais {hidden} no painel. " if hidden > 0 else "") + (
        f'<a href="{escape(dashboard_url, quote=True)}">Abrir o painel</a>' if dashboard_url else "")
    tail += "\n<i>Para parar ou mudar o que recebe, use Meu perfil no painel.</i>"
    blocks.append(tail.strip())
    out, cur = [], ""
    for b in blocks:
        if cur and len(cur) + 2 + len(b) > LIMIT:
            out.append(cur)
            cur = b
        else:
            cur = f"{cur}\n\n{b}" if cur else b
    if cur:
        out.append(cur)
    return out
