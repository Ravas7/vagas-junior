"""Modelo de dados: uma vaga."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .text import norm

# Campos que só existem durante a execução (não vão para o jobs.json).
_TRANSIENT = {"description", "kind"}


@dataclass
class Job:
    id: str                      # "<fonte>:<id na fonte>", único
    source: str                  # gupy, adzuna, greenhouse, lever
    title: str
    company: str
    url: str
    location: str = ""
    uf: str = ""
    workplace: str = ""          # remoto | hibrido | presencial | ""
    posted_at: str = ""          # AAAA-MM-DD, quando a fonte informa
    snippet: str = ""            # primeiras linhas da descrição
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    active: bool = True
    notified: bool = False
    tipo: str = "vaga"           # vaga | noticia
    area: str = "dev"            # dev | correlata | suporte
    english: str = ""            # basico | intermediario | avancado | "" (não informado)
    abroad: bool = False         # vaga remota de empresa/local fora do Brasil
    salary: int = 0              # maior salário mensal em R$ informado na vaga; 0 = não informado
    grande: bool = False         # empresa grande / multinacional
    # transitórios
    description: str = field(default="", repr=False)
    kind: str = field(default="", repr=False)   # tipo de contratação, ex.: estágio

    def dedupe_key(self) -> str:
        """Mesma vaga publicada em duas fontes tem a mesma chave.

        Notícia usa só o título: o mesmo anúncio sai em vários veículos.
        """
        if self.tipo == "noticia":
            return "noticia|" + norm(self.title)
        return "|".join(norm(x) for x in (self.title, self.company, self.location))

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in _TRANSIENT:
            data.pop(key, None)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
