import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(autouse=True)
def sem_firebase_de_verdade(monkeypatch):
    """Os testes nunca entram no Firebase de verdade, mesmo com a conta do robô no ambiente."""
    monkeypatch.delenv("FIREBASE_ROBO_EMAIL", raising=False)
    monkeypatch.delenv("FIREBASE_ROBO_SENHA", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
