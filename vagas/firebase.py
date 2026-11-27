"""Leitura do Firebase pelo robô (só biblioteca padrão).

O robô entra com uma conta própria (FIREBASE_ROBO_EMAIL e FIREBASE_ROBO_SENHA, nos
Secrets do GitHub) e lê, pela API REST do Firestore:
- acesso/{uid}: quem está liberado (status "aprovado");
- users/{uid}/perfil/atual: o perfil de cada pessoa.
As regras do Firestore só deixam essa conta LER essas duas coisas (README, passo 9).

Projeto e chave da web vêm de docs/firebase-config.js, que já é público.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .http import SourceError, get_json, post_json

SIGN_IN = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
FIRESTORE = "https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents"


class FirebaseSkipped(Exception):
    """Firebase não configurado para o robô (sem conta do robô): avisos por pessoa ficam desligados."""


@dataclass
class Recipient:
    uid: str
    email: str
    nome: str = ""
    perfil: dict | None = None          # None = ainda não salvou o perfil
    extra: dict = field(default_factory=dict)


def web_config(path: str | Path = "docs/firebase-config.js") -> dict:
    """Lê apiKey e projectId do firebase-config.js do painel."""
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    out = {}
    for key in ("apiKey", "projectId"):
        m = re.search(rf'{key}\s*:\s*"([^"]+)"', text)
        if m:
            out[key] = m.group(1)
    return out


def decode(value: dict):
    """Valor tipado do Firestore REST -> Python."""
    if "stringValue" in value:
        return value["stringValue"]
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "timestampValue" in value:
        return value["timestampValue"]
    if "nullValue" in value:
        return None
    if "arrayValue" in value:
        return [decode(v) for v in value["arrayValue"].get("values", [])]
    if "mapValue" in value:
        return decode_fields(value["mapValue"].get("fields", {}))
    return None


def decode_fields(fields: dict) -> dict:
    return {k: decode(v) for k, v in (fields or {}).items()}


class Client:
    """Conversa com o Firestore como a conta do robô."""

    def __init__(self, project: str, token: str):
        self.base = FIRESTORE.format(project=project)
        self.headers = {"Authorization": f"Bearer {token}"}

    @classmethod
    def login(cls, email: str = "", password: str = "", config_path: str | Path = "docs/firebase-config.js"):
        email = email or os.environ.get("FIREBASE_ROBO_EMAIL", "")
        password = password or os.environ.get("FIREBASE_ROBO_SENHA", "")
        if not (email and password):
            raise FirebaseSkipped("defina FIREBASE_ROBO_EMAIL e FIREBASE_ROBO_SENHA para os avisos por pessoa")
        cfg = web_config(config_path)
        if not (cfg.get("apiKey") and cfg.get("projectId")):
            raise FirebaseSkipped("docs/firebase-config.js sem apiKey ou projectId")
        try:
            data = post_json(f"{SIGN_IN}?key={cfg['apiKey']}",
                             {"email": email, "password": password, "returnSecureToken": True})
        except SourceError as exc:
            raise SourceError(f"o robô não conseguiu entrar no Firebase ({exc}). Confira e-mail e senha do robô.") from None
        token = data.get("idToken") if isinstance(data, dict) else None
        if not token:
            raise SourceError("o Firebase não devolveu o acesso do robô")
        return cls(cfg["projectId"], token)

    def list_docs(self, collection: str) -> list[tuple[str, dict]]:
        """Todos os documentos de uma coleção: [(id, campos)]."""
        out, page = [], None
        while True:
            params = {"pageSize": 300, **({"pageToken": page} if page else {})}
            data = get_json(f"{self.base}/{collection}", params, headers=self.headers)
            for doc in data.get("documents", []):
                out.append((doc["name"].rsplit("/", 1)[-1], decode_fields(doc.get("fields", {}))))
            page = data.get("nextPageToken")
            if not page:
                return out

    def get_doc(self, path: str) -> dict | None:
        """Um documento (None se não existe)."""
        try:
            doc = get_json(f"{self.base}/{path}", headers=self.headers, retries=1)
        except SourceError as exc:
            if str(exc).startswith("HTTP 404"):
                return None
            raise
        return decode_fields(doc.get("fields", {}))


def recipients(client: Client) -> list[Recipient]:
    """Quem está liberado, com o perfil de cada um."""
    out = []
    for uid, data in client.list_docs("acesso"):
        if data.get("status") != "aprovado" or not data.get("email"):
            continue
        perfil = client.get_doc(f"users/{uid}/perfil/atual")
        out.append(Recipient(uid=uid, email=data["email"], nome=data.get("nome", ""), perfil=perfil))
    return out
