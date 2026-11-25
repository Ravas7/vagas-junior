"""Orquestra uma execução: coletar -> filtrar -> juntar -> avisar -> salvar."""

from __future__ import annotations

import os
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import emailer, filters, storage
from .http import SourceError
from .models import Job
from .sources import REGISTRY
from .sources.base import SourceSkipped


def log(msg: str) -> None:
    print(msg, flush=True)


def load_dotenv(path: str = ".env") -> None:
    """Lê KEY=VALUE de um .env local (opcional). Não sobrescreve o que já existe."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: str) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def now_local(cfg: dict) -> datetime:
    name = cfg.get("timezone", "America/Sao_Paulo")
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(name))
    except Exception:  # sem tzdata (ex.: Windows): usa UTC-3 fixo
        return datetime.now(timezone(timedelta(hours=-3)))


def dashboard_url(cfg: dict) -> str:
    url = cfg.get("email", {}).get("dashboard_url") or os.environ.get("DASHBOARD_URL", "")
    if url:
        return url
    repo = os.environ.get("GITHUB_REPOSITORY", "")      # "usuario/repositorio" no Actions
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"
    return ""


def collect(cfg: dict, only: str | None = None) -> tuple[list[Job], dict]:
    """Roda as fontes ligadas. Devolve (vagas sem filtrar, status por fonte)."""
    jobs: list[Job] = []
    status: dict[str, dict] = {}
    for name, module in REGISTRY.items():
        scfg = cfg.get("sources", {}).get(name, {})
        if only and name != only:
            continue
        if not scfg.get("enabled", False):
            continue
        try:
            extra = {"big_companies_extra": cfg.get("filter", {}).get("big_companies_extra", [])}
            found = module.fetch({**extra, **scfg})
            status[name] = {"ok": True, "count": len(found), "error": ""}
            jobs += found
            log(f"[{name}] {len(found)} vagas coletadas")
        except SourceSkipped as exc:
            status[name] = {"ok": None, "count": 0, "error": str(exc)}
            log(f"[{name}] ignorada: {exc}")
        except SourceError as exc:
            status[name] = {"ok": False, "count": 0, "error": str(exc)}
            log(f"[{name}] ERRO: {exc}")
    return jobs, status


def run(cfg: dict, send_email: bool = True) -> int:
    fcfg = cfg.get("filter", {})
    ecfg = cfg.get("email", {})
    path = cfg.get("storage", {}).get("path", "docs/data/jobs.json")
    now = now_local(cfg)
    today = now.strftime("%Y-%m-%d")

    raw, status = collect(cfg)
    ok_sources = {n for n, s in status.items() if s["ok"]}
    if not ok_sources:
        log("Nenhuma fonte respondeu. Nada foi salvo.")
        return 1

    # guarda tudo que passou na base; o painel filtra pelo perfil de cada pessoa
    accepted = [j for j in raw if filters.classify(j, fcfg)]
    n_padrao = sum(1 for j in accepted if j.padrao)
    log(f"{len(raw)} coletadas, {len(accepted)} passaram na base, {n_padrao} no seu perfil (config.toml)")

    existing = storage.load(path)
    jobs, new = storage.merge(existing, accepted, ok_sources, today,
                                fcfg.get("keep_days", 45), fcfg.get("keep_days_news", 30))
    n_news = sum(1 for j in new if j.tipo == "noticia")
    log(f"{len(new) - n_news} vagas novas e {n_news} notícias novas")

    # --- e-mail: todas as vagas ativas ainda não avisadas ---
    pending = sorted(
        (j for j in jobs.values()
         if j.active and j.padrao and not j.notified and j.score >= ecfg.get("min_score", 0)),
        key=lambda j: (j.score, j.first_seen), reverse=True,
    )
    if send_email and ecfg.get("enabled", True) and (pending or ecfg.get("send_when_empty", False)):
        user, password, to = emailer.credentials()
        if not (user and password):
            log("E-mail não enviado: defina EMAIL_USER e EMAIL_APP_PASSWORD.")
        elif pending:
            msg = emailer.build_message(pending, ecfg, dashboard_url(cfg), user, to, now.strftime("%d/%m"))
            try:
                emailer.send(msg, user, password, ecfg.get("smtp_host", "smtp.gmail.com"),
                             int(ecfg.get("smtp_port", 465)))
                for j in pending:
                    j.notified = True
                log(f"E-mail enviado para {to} ({len(pending)} itens novos)")
            except Exception as exc:  # noqa: BLE001 - qualquer falha de SMTP
                log(f"ERRO ao enviar e-mail: {type(exc).__name__}: {exc}")
    elif not send_email and pending:
        out = Path("out")
        out.mkdir(exist_ok=True)
        msg = emailer.build_message(pending, ecfg, dashboard_url(cfg),
                                    "voce@exemplo.com", "voce@exemplo.com", now.strftime("%d/%m"))
        html = msg.get_body(("html",)).get_content()
        (out / "email_preview.html").write_text(html, encoding="utf-8")
        log("Pré-visualização do e-mail salva em out/email_preview.html")

    meta = {
        "updated_at": now.isoformat(timespec="seconds"),
        "sources": status,
        "active": sum(1 for j in jobs.values() if j.active),
        "perfil_padrao": filters.profile_from_config(fcfg),   # o painel usa para preencher o perfil
    }
    storage.save(path, jobs, meta)
    log(f"Salvo em {path}: {meta['active']} vagas ativas")
    return 0


def check(cfg: dict, only: str | None = None, show: int = 5) -> int:
    """Diagnóstico: mostra o que cada fonte devolve e como o filtro reage."""
    fcfg = cfg.get("filter", {})
    raw, status = collect(cfg, only)
    for name, s in status.items():
        flag = {True: "OK", False: "FALHOU", None: "IGNORADA"}[s["ok"]]
        log(f"\n== {name}: {flag} ({s['count']} vagas) {s['error']}")
    accepted, rejected = [], []
    in_base = 0
    for j in raw:
        in_base += filters.classify(j, fcfg)
        (accepted if j.padrao else rejected).append(j)
    log(f"\nTotal: {len(raw)} coletadas, {len(accepted)} aceitas no seu perfil, {len(rejected)} descartadas")
    log(f"O painel recebe {in_base} que passaram na base (para quem tem outro perfil).\n")
    log("Exemplos ACEITOS:")
    for j in sorted(accepted, key=lambda x: -x.score)[:show]:
        log(f"  [{j.score}] ({j.tipo}/{j.area}) {j.title} | {j.company} | {j.location or '-'} | {', '.join(j.reasons)}")
    log("\nExemplos DESCARTADOS (para ajustar o filtro):")
    for j in rejected[:show]:
        log(f"  {j.title} | {j.company} | {j.reasons[0] if j.reasons else ''}")
    return 0 if status and any(s["ok"] for s in status.values()) else 1


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="vagas", description="Ragas: central de vagas")
    parser.add_argument("--config", default="config.toml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="coleta, filtra, envia e-mail e salva")
    p_run.add_argument("--no-email", action="store_true", help="não envia; salva prévia em out/")
    p_check = sub.add_parser("check", help="testa as fontes e o filtro sem salvar nada")
    p_check.add_argument("--source", help="testar só uma fonte (gupy, adzuna...)")
    args = parser.parse_args(argv)

    load_dotenv()
    cfg = load_config(args.config)
    if args.cmd == "run":
        return run(cfg, send_email=not args.no_email)
    return check(cfg, args.source)


if __name__ == "__main__":
    sys.exit(main())
