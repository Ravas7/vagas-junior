"""Peças comuns às fontes de vagas.

Para criar uma fonte nova, copie um arquivo desta pasta e:
1. defina NAME;
2. escreva fetch(cfg) -> list[Job] (sem filtrar; o filtro é central);
3. registre o módulo em sources/__init__.py;
4. adicione [sources.<NAME>] no config.toml.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from ..text import strip_html


class SourceSkipped(Exception):
    """A fonte está ligada, mas falta algo (ex.: chave de API). Não é erro grave."""


def pick(data: dict, *keys: str, default: str = "") -> str:
    """Primeiro valor preenchido entre várias chaves possíveis.

    Se o valor for um objeto (ex.: {"display_name": "Acme"}), usa o nome dentro dele.
    """
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            value = value.get("display_name") or value.get("name") or value.get("label") or ""
        if value not in (None, "", [], {}):
            return str(value)
    return default


def snippet_of(text: str, size: int = 400) -> str:
    clean = strip_html(text)
    return clean if len(clean) <= size else clean[: size - 1].rstrip() + "…"


def date_of(value) -> str:
    """Converte ISO string ou epoch (s/ms) para AAAA-MM-DD. Vazio se não entender."""
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d")
    text = str(value)
    if len(text) >= 10 and text[4] == "-":
        return text[:10]
    try:                                    # datas de RSS: "Mon, 23 Nov 2026 10:00:00 GMT"
        return parsedate_to_datetime(text).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return ""


def finish(ok_calls: int, errors: list[str], name: str) -> None:
    """Se nenhuma chamada deu certo, a fonte falhou; se só algumas falharam, segue."""
    from ..http import SourceError
    if ok_calls == 0 and errors:
        raise SourceError(f"{name}: {errors[0]}")
    for error in dict.fromkeys(errors):          # falhas parciais: avisa e segue
        print(f"  aviso [{name}]: {error}", flush=True)
