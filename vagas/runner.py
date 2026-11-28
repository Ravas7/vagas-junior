"""Orquestra uma execução: coletar -> filtrar -> juntar -> avisar -> salvar."""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import avisos, emailer, filters, firebase, storage, telegram
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
                                fcfg.get("keep_days", 45), fcfg.get("keep_days_news", 30),
                                fcfg.get("keep_days_freela", 7))
    n_news = sum(1 for j in new if j.tipo == "noticia")
    n_freela = sum(1 for j in new if j.tipo == "freela")
    log(f"{len(new) - n_news - n_freela} vagas novas, {n_news} notícias novas e {n_freela} freelas novos")

    # --- e-mail: todas as vagas ativas ainda não avisadas ---
    pending = sorted(
        (j for j in jobs.values()
         if j.active and j.padrao and not j.notified and j.score >= ecfg.get("min_score", 0)),
        key=lambda j: (j.score, j.first_seen), reverse=True,
    )
    # --- avisos por pessoa (perfil de cada um no Firebase) ---
    people = load_people()
    user, password, to = emailer.credentials()
    plans = avisos.plan(people or [], list(jobs.values()), {j.id for j in new}, today, avisos.is_evening(now, cfg),
                        telegram_on=bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()))
    send_avisos(plans, ecfg, cfg, send_email, now)
    if avisos.covers(people, to):
        # o dono já recebe pelo próprio perfil: o e-mail do config.toml não sai (não duplica)
        for j in pending:
            j.notified = True
        log(f"E-mail do config.toml não enviado: {avisos.mask_email(to)} já recebe pelo perfil.")
        pending = []

    if send_email and ecfg.get("enabled", True) and (pending or ecfg.get("send_when_empty", False)):
        if not (user and password):
            log("E-mail não enviado: defina EMAIL_USER e EMAIL_APP_PASSWORD.")
        elif pending:
            msg = emailer.build_message(pending, ecfg, dashboard_url(cfg), user, to, now.strftime("%d/%m"))
            try:
                emailer.send(msg, user, password, ecfg.get("smtp_host", "smtp.gmail.com"),
                             int(ecfg.get("smtp_port", 465)))
                for j in pending:
                    j.notified = True
                log(f"E-mail enviado para {avisos.mask_email(to)} ({len(pending)} itens novos)")
            except Exception as exc:  # noqa: BLE001 - qualquer falha de SMTP
                log(f"ERRO ao enviar e-mail: {type(exc).__name__}")   # a mensagem do SMTP pode trazer o e-mail
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
        ok = filters.classify(j, fcfg)
        in_base += ok
        (accepted if j.padrao or (j.tipo == "freela" and ok) else rejected).append(j)
    log(f"\nTotal: {len(raw)} coletadas, {len(accepted)} aceitas no seu perfil, {len(rejected)} descartadas")
    log(f"O painel recebe {in_base} que passaram na base (para quem tem outro perfil).\n")
    log("Exemplos ACEITOS:")
    for j in sorted(accepted, key=lambda x: -x.score)[:show]:
        if j.tipo == "freela":
            bids = f"{j.propostas} propostas" if j.propostas >= 0 else "propostas: ?"
            log(f"  [{j.score}] (freela) {j.title} | {j.orcamento or 'orçamento não informado'} | {bids} | "
                f"{j.posted_at or '-'} | {', '.join(j.reasons)}")
            continue
        log(f"  [{j.score}] ({j.tipo}/{j.area}) {j.title} | {j.company} | {j.location or '-'} | {', '.join(j.reasons)}")
    log("\nExemplos DESCARTADOS (para ajustar o filtro):")
    for j in rejected[:show]:
        log(f"  {j.title} | {j.company} | {j.reasons[0] if j.reasons else ''}")
    return 0 if status and any(s["ok"] for s in status.values()) else 1


PROFILE_PATH = "docs/perfil-padrao.json"


def profile_json(cfg: dict) -> str:
    opts = filters.profile_options(cfg.get("filter", {}))
    opts["telegram_bot"] = cfg.get("avisos", {}).get("telegram_bot", "").lstrip("@")   # vazio = Telegram "em breve"
    return json.dumps(opts, ensure_ascii=False, indent=1) + "\n"


def write_profile(cfg: dict, path: str = PROFILE_PATH) -> int:
    """Grava o perfil padrão (do config.toml) e as opções do formulário para o painel."""
    Path(path).write_text(profile_json(cfg), encoding="utf-8")
    log(f"Perfil padrão salvo em {path}. Faça o commit desse arquivo.")
    return 0


def load_people() -> list | None:
    """Pessoas liberadas e perfis, pelo Firebase. None = sem Firebase (vale só o e-mail do config.toml)."""
    try:
        client = firebase.Client.login()
        people = firebase.recipients(client)
    except firebase.FirebaseSkipped as exc:
        log(f"Avisos por pessoa desligados: {exc}.")
        return None
    except SourceError as exc:
        log(f"AVISO: Firebase indisponível, avisos por pessoa ficam para a próxima coleta ({exc})")
        return None
    load_telegram(client, people)
    return people


def load_telegram(client, people: list) -> None:
    """Liga as conversas novas do Telegram e anota em cada pessoa (extra["telegram"]). Falha aqui só gera aviso:
    quem escolheu Telegram e não está ligado recebe por e-mail."""
    if not any(((p.perfil or {}).get("aviso") or {}).get("canal") == "telegram" for p in people):
        return
    try:
        links = firebase.telegram_links(client)
    except SourceError as exc:
        log(f"AVISO: não deu para ler as conversas do Telegram ({exc}); vai por e-mail.")
        return
    try:
        links = telegram.link(client, people, links, telegram.token(), log)
    except telegram.TelegramSkipped as exc:
        log(f"Telegram desligado: {exc}.")
    except SourceError as exc:
        log(f"AVISO: {exc}")
    for p in people:
        if p.uid in links:
            p.extra["telegram"] = links[p.uid]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "pessoa"


def send_avisos(plans: list, ecfg: dict, cfg: dict, send_email: bool, now: datetime) -> None:
    """Manda (ou, sem envio, salva em out/) um e-mail por pessoa com as vagas do perfil dela."""
    if not plans:
        log("Avisos por pessoa: ninguém com vaga nova que combine.")
        return
    user, password, _ = emailer.credentials()
    day = now.strftime("%d/%m")
    if not send_email:
        out = Path("out")
        out.mkdir(exist_ok=True)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    for pl in plans:
        p = pl.person
        what = "vagas e freelas" if pl.jobs and pl.freelas else "freelas" if pl.freelas else "vagas"
        hello = avisos.greeting(p, pl.kind, what)
        if pl.channel == "telegram":
            texts = telegram.messages(pl.jobs, hello, dashboard_url(cfg), ecfg.get("max_per_email", 40), pl.freelas)
            if not send_email:
                name = out / f"aviso_{_slug(p.nome or p.email)}_telegram.txt"
                name.write_text("\n\n----- (próxima mensagem) -----\n\n".join(texts), encoding="utf-8")
                log(f"Prévia do Telegram de {p.nome or p.email} salva em {name}")
                continue
            try:
                for t in texts:
                    telegram.send(tok, pl.chat_id, t)
                log(f"Aviso pelo Telegram para {avisos.who(p)} ({len(pl.jobs) + len(pl.freelas)} itens)")
                continue
            except SourceError as exc:
                log(f"ERRO no Telegram de {avisos.who(p)} ({exc}); vai por e-mail.")
        msg = emailer.build_message(pl.jobs, ecfg, dashboard_url(cfg), user or "voce@exemplo.com", p.email, day,
                                    greeting=hello, footer=avisos.FOOTER, freelas=pl.freelas)
        label = f"{p.nome or p.email} ({len(pl.jobs) + len(pl.freelas)} itens)"
        if not send_email:
            name = out / f"aviso_{_slug(p.nome or p.email)}.html"
            name.write_text(msg.get_body(("html",)).get_content(), encoding="utf-8")
            log(f"Prévia do aviso de {label} salva em {name}")
            continue
        if not (ecfg.get("enabled", True) and user and password):
            log("Avisos não enviados: defina EMAIL_USER e EMAIL_APP_PASSWORD.")
            return
        try:
            emailer.send(msg, user, password, ecfg.get("smtp_host", "smtp.gmail.com"), int(ecfg.get("smtp_port", 465)))
            log(f"Aviso enviado para {avisos.who(p)} ({len(pl.jobs) + len(pl.freelas)} itens)")
        except Exception as exc:  # noqa: BLE001 - uma pessoa com problema não derruba as outras
            log(f"ERRO ao enviar aviso para {avisos.who(p)}: {type(exc).__name__}")   # a mensagem do SMTP pode trazer o e-mail


def matches_for(job: Job, perfil: dict | None, fcfg: dict) -> bool:
    """A vaga (já salva no jobs.json) combina com o perfil? Sem perfil, vale o do config.toml."""
    if perfil is None:
        return job.padrao
    if job.tipo == "noticia":
        return filters.evaluate_news_profile(job, perfil).accepted
    return filters.evaluate_profile(job, filters.base_from_job(job), perfil).accepted


def cmd_avisos(cfg: dict, previa: bool = False) -> int:
    """Diagnóstico dos avisos por pessoa: entra no Firebase como robô e mostra quem
    receberia e quantas vagas ativas combinam com cada perfil. Não envia nada.
    Com previa=True, monta o aviso de cada pessoa com o que chegou nos últimos 3 dias e salva em out/."""
    fcfg = cfg.get("filter", {})
    try:
        client = firebase.Client.login()
        people = firebase.recipients(client)
    except firebase.FirebaseSkipped as exc:
        log(f"Avisos por pessoa desligados: {exc}.")
        return 1
    except SourceError as exc:
        log(f"ERRO no Firebase: {exc}")
        return 1
    load_telegram(client, people)          # liga quem tocou em Começar no bot
    jobs = [j for j in storage.load(cfg.get("storage", {}).get("path", "docs/data/jobs.json")).values() if j.active]
    log(f"O robô entrou no Firebase. {len(people)} {'pessoa liberada' if len(people) == 1 else 'pessoas liberadas'}:")
    for r in people:
        hits = [j for j in jobs if matches_for(j, r.perfil, fcfg)]
        vagas = sum(1 for j in hits if j.tipo == "vaga")
        perfil = (f"perfil: {', '.join(r.perfil.get('niveis', []))} | {r.perfil.get('estado') or '-'}"
                  if r.perfil else "sem perfil (vale o do config.toml)")
        noticias = len(hits) - vagas
        pr = avisos.prefs(r.perfil)
        canal = ("desligado" if not pr["ativo"] else "Telegram" if avisos.telegram_chat(r)
                 else "e-mail (Telegram ainda não ligado)" if pr["canal"] == "telegram" else "e-mail")
        if r.perfil:
            perfil += f" | aviso: {canal}, {'resumo diário' if pr['frequencia'] == 'diario' else 'a cada coleta'}"
        log(f"  {r.nome or '(sem nome)'} <{r.email}> | {perfil} | combinam {vagas} {'vaga' if vagas == 1 else 'vagas'}"
            f" e {noticias} {'notícia' if noticias == 1 else 'notícias'} ativas")
    if previa:
        now = now_local(cfg)
        today = now.strftime("%Y-%m-%d")
        since = (now - timedelta(days=2)).strftime("%Y-%m-%d")           # hoje e os 2 dias anteriores
        todays = {j.id for j in jobs if (j.first_seen or "") >= since}
        log(f"\nPrévia com as {len(todays)} que chegaram nos últimos 3 dias, como se fossem novas:")
        send_avisos(avisos.plan(people, jobs, todays, today, evening=True,
                                telegram_on=bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())),
                    cfg.get("email", {}), cfg, False, now)
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="vagas", description="Ragas: central de vagas")
    parser.add_argument("--config", default="config.toml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="coleta, filtra, envia e-mail e salva")
    p_run.add_argument("--no-email", action="store_true", help="não envia; salva prévia em out/")
    p_check = sub.add_parser("check", help="testa as fontes e o filtro sem salvar nada")
    p_check.add_argument("--source", help="testar só uma fonte (gupy, adzuna...)")
    sub.add_parser("perfil", help=f"grava {PROFILE_PATH} (perfil padrão e opções do formulário)")
    p_av = sub.add_parser("avisos", help="testa a leitura do Firebase: quem recebe aviso e quantas vagas combinam (não envia)")
    p_av.add_argument("--previa", action="store_true", help="salva em out/ o aviso de cada pessoa com o que chegou nos últimos 3 dias")
    args = parser.parse_args(argv)

    load_dotenv()
    cfg = load_config(args.config)
    if args.cmd == "run":
        return run(cfg, send_email=not args.no_email)
    if args.cmd == "avisos":
        return cmd_avisos(cfg, args.previa)
    if args.cmd == "perfil":
        return write_profile(cfg)
    return check(cfg, args.source)


if __name__ == "__main__":
    sys.exit(main())
