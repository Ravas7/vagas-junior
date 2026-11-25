"""Gera tests/fixtures/paridade.json: vagas + perfis + o que o Python decide.

O teste tests/perfil.test.js confere que o JS (docs/perfil.js) decide igual.
Rode depois de mexer em evaluate_profile ou nas vagas de exemplo:

    python tests/make_paridade.py

(tests/test_perfil.py avisa se o arquivo ficou desatualizado.)
"""

from __future__ import annotations

import copy
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vagas import filters  # noqa: E402
from vagas.models import Job  # noqa: E402
from vagas.runner import load_config  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "paridade.json"


def corpus() -> list[Job]:
    """Vagas de exemplo do painel + combinações de título, descrição e local."""
    jobs = []
    for d in json.loads((ROOT / "docs/data/jobs.sample.json").read_text(encoding="utf-8"))["jobs"]:
        if d.get("tipo") == "noticia":
            continue
        j = Job.from_dict(d)
        j.description = d.get("snippet", "")
        jobs.append(j)
    titles = ["Desenvolvedor Python Júnior", "Estágio em Desenvolvimento de Software", "Analista de Dados Jr",
              "Analista de Suporte N1", "Desenvolvedor Full Stack", "QA Júnior", "Desenvolvedor Java Pleno",
              "Engenheiro de Software Sênior", "Técnico de Manutenção de Computadores", "DevOps Jr",
              "Desenvolvedor Java II", "Analista de Segurança da Informação Júnior"]
    descs = ["", "Inglês avançado. 3 anos de experiência com React.",
             "Inglês intermediário. Salário R$ 3.500. Python e SQL. Experiência de 1 ano",
             "Vaga para júnior, sem experiência, primeiro emprego. Salário de R$ 2.000. AWS e Docker"]
    locs = [("", "", "remoto"), ("Remote - United States", "", "remoto"), ("Lauro de Freitas, BA", "BA", "hibrido"),
            ("", "", ""), ("Recife, PE", "PE", "presencial"), ("Remote - Brazil", "", "remoto")]
    for i, (t, d, (loc, uf, wp)) in enumerate(itertools.product(titles, descs, locs)):
        jobs.append(Job(id=f"s:{i}", source="s", title=t, company="Itaú" if i % 3 == 0 else "Acme", url="u",
                        location=loc, uf=uf, workplace=wp, description=d))
    news = ["TCE-ES abre processo seletivo para profissionais de Tecnologia da Informação",
            "Itaú abre programa de trainee em tecnologia", "iFood abre seleção nacional de trainee em tecnologia",
            "Empresa de Camaçari abre vagas de tecnologia para júnior", "IFSP abre processo seletivo de TI",
            "Startup abre vagas remotas para desenvolvedores júnior", "Prefeitura de Recife abre vagas de TI",
            "Vagas de trainee em tecnologia em São Paulo e Salvador"]
    for i, t in enumerate(news):
        jobs.append(Job(id=f"n:{i}", source="noticias", title=t, company="", url="u", tipo="noticia"))
    return jobs


def profiles(padrao: dict) -> dict[str, dict]:
    p = lambda **kw: {**padrao, **kw}
    amigo = dict(cidades=[], regiao_nome="", estado="PE")
    return {
        "padrao": padrao,
        "so_estagio": p(niveis=["estagio"]),
        "pleno_senior": p(niveis=["pleno", "senior"], anos_max=0),
        "todos_niveis": p(niveis=["estagio", "junior", "pleno", "senior"], anos_max=5),
        "recife_estado": p(**amigo),
        "recife_cidade": p(cidades=["Recife", "Olinda"], regiao_nome="Recife", estado="PE"),
        "so_remoto": p(presencial=False, exterior=False),
        "exterior_fluente": p(ingles_max="qualquer"),
        "sem_exterior": p(exterior=False),
        "dados_qa": p(areas=["dados", "qa"]),
        "hardware": p(areas=["hardware", "suporte"], suporte_salario_min=2000, suporte_sem_salario=True, **amigo),
        "techs_destaque": p(tecnologias=["Python", "React", "SQL"]),
        "techs_filtro": p(tecnologias=["Python", "SQL"], so_minhas_techs=True),
        "local_desconhecido": p(local_desconhecido=True, nota_minima=30, estados_preferidos=["BA"]),
        "sem_estado": p(estado=""),
    }


def build() -> str:
    cfg = load_config(str(ROOT / "config.toml"))["filter"]
    cfg = {**cfg, "max_age_days": 0}                # sem data: o arquivo não muda com o dia
    padrao = filters.profile_from_config(cfg)
    jobs = []
    for j in corpus():
        j = copy.deepcopy(j)
        if filters.classify(j, cfg):
            jobs.append(j)
    perfis = profiles(padrao)
    esperado = {}
    for nome, perfil in perfis.items():
        out = []
        for j in jobs:
            r = (filters.evaluate_news_profile(j, perfil) if j.tipo == "noticia"
                 else filters.evaluate_profile(j, filters.base_from_job(j), perfil))
            out.append([r.accepted, r.score, r.reasons])
        esperado[nome] = out
    usados = ["id", "tipo", "title", "location", "uf", "workplace", "salary", "grande", "area", "subarea",
              "nivel", "english", "techs", "years", "junior_title", "junior_desc", "pouca_exp"]
    noticia = ["ufs", "score", "reasons"]
    vagas = [{k: j.to_dict()[k] for k in usados + (noticia if j.tipo == "noticia" else [])} for j in jobs]
    data = {"vagas": vagas, "perfis": perfis, "esperado": esperado}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} gravado")
