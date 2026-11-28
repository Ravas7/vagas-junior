"""Cliente HTTP mínimo (só biblioteca padrão): GET/POST que devolvem JSON ou texto."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "vagas-junior/1.0 (alerta pessoal de vagas; uso individual)"


class SourceError(Exception):
    """Falha ao consultar uma fonte (rede, status HTTP, resposta inválida)."""


def _fetch(url: str, params: dict | None = None, headers: dict | None = None,
           body: dict | None = None, timeout: int = 20, retries: int = 2, method: str | None = None) -> bytes:
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)   # sem method: POST se houver corpo
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = SourceError(f"HTTP {e.code} em {_short(url)}")
            if e.code not in (429, 500, 502, 503, 504):
                break  # 404, 403 etc. não adianta tentar de novo
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = SourceError(f"falha de rede em {_short(url)}: {e}")
        time.sleep(1.5 * (attempt + 1))
    raise last or SourceError(f"falha em {_short(url)}")


def get_json(url: str, params: dict | None = None, headers: dict | None = None,
             timeout: int = 20, retries: int = 2):
    raw = _fetch(url, params, headers, None, timeout, retries)
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SourceError(f"resposta de {_short(url)} não é JSON") from None


def post_json(url: str, body: dict, headers: dict | None = None,
              timeout: int = 25, retries: int = 2):
    raw = _fetch(url, None, headers, body, timeout, retries)
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SourceError(f"resposta de {_short(url)} não é JSON") from None


def send_json(url: str, body: dict, method: str = "PATCH", headers: dict | None = None,
              timeout: int = 25, retries: int = 1):
    """PATCH/PUT com corpo JSON (o robô grava no Firestore)."""
    raw = _fetch(url, None, headers, body, timeout, retries, method)
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SourceError(f"resposta de {_short(url)} não é JSON") from None


def get_text(url: str, headers: dict | None = None, timeout: int = 20, retries: int = 2) -> str:
    """GET que devolve texto (RSS/XML). A URL deve vir pronta, já com a querystring."""
    raw = _fetch(url, None, {"Accept": "application/rss+xml, text/xml, */*", **(headers or {})},
                 None, timeout, retries)
    return raw.decode("utf-8", errors="replace")


def _short(url: str) -> str:
    # esconde a querystring nas mensagens (pode conter chave de API)
    return url.split("?", 1)[0]
