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
    area: str = "dev"            # dev | correlata | suporte | hardware
    english: str = ""            # basico | intermediario | avancado | "" (não informado)
    abroad: bool = False         # vaga remota de empresa/local fora do Brasil
    salary: int = 0              # maior salário mensal em R$ informado na vaga; 0 = não informado
    grande: bool = False         # empresa grande / multinacional
    # --- fatos para o filtro do perfil no painel (filters.evaluate_profile em JS) ---
    subarea: str = ""            # dev | dados | qa | devops | seguranca | infra | suporte | hardware
    nivel: str = ""              # estagio | junior | pleno | senior | "" (título não diz)
    city: str = ""               # cidade, quando a fonte informa
    techs: list[str] = field(default_factory=list)   # tecnologias citadas (python, react...)
    years: int = 0               # anos de experiência pedidos (0 = não diz)
    junior_title: bool = False   # "júnior", "jr", "trainee"... no título
    junior_desc: bool = False    # "júnior" só na descrição
    pouca_exp: bool = False      # júnior no título e "sem experiência" na descrição
    # --- resultado no perfil padrão (o do config.toml): e-mail e quem ainda não tem perfil ---
    padrao: bool = True          # vagas antigas (sem o campo) já tinham passado no perfil padrão
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
