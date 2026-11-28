"""Monta e envia o e-mail com as vagas novas e as notícias de processos seletivos."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from .models import Job

WORKPLACE_LABEL = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}
SOURCE_LABEL = {
    "gupy": "Gupy", "adzuna": "Adzuna", "greenhouse": "Greenhouse", "lever": "Lever",
    "ashby": "Ashby", "smartrecruiters": "SmartRecruiters", "workday": "Workday",
    "noticias": "Notícia", "workana": "Workana", "freelas99": "99Freelas",
}
NIVEL_FREELA = {"iniciante": "para iniciante", "intermediario": "nível intermediário", "especialista": "pede especialista"}


def freela_line(j: Job) -> str:
    """'Workana · USD 250 - 500 · 7 propostas · para iniciante'"""
    bids = "" if j.propostas < 0 else ("1 proposta" if j.propostas == 1 else f"{j.propostas} propostas")
    return " · ".join(x for x in (SOURCE_LABEL.get(j.source, j.source), j.orcamento, bids,
                                  NIVEL_FREELA.get(j.nivel_freela, "")) if x)


EN_LABEL = {"": "não informado", "basico": "básico", "intermediario": "intermediário", "avancado": "avançado"}


def _where(job: Job) -> str:
    label = WORKPLACE_LABEL.get(job.workplace, "")
    parts = [label] if label else []
    if job.location and job.location.lower() != label.lower():
        parts.append(job.location)
    return " — ".join(parts) or "Local não informado"


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def build_message(jobs: list[Job], cfg: dict, dashboard_url: str,
                  sender: str, recipient: str, today_label: str,
                  greeting: str = "", footer: str = "", freelas: list[Job] | None = None) -> EmailMessage:
    """greeting/footer: usados no aviso por pessoa ("Olá, Ana" / "Para parar, use Meu perfil").
    freelas: seção "Freelas novos" (só no aviso de quem ligou essa opção)."""
    freelas = freelas or []
    vagas_all = [j for j in jobs if j.tipo != "noticia"]
    news_all = [j for j in jobs if j.tipo == "noticia"]
    vagas = vagas_all[: cfg.get("max_per_email", 40)]
    news = news_all[: cfg.get("max_news_per_email", 10)]
    hidden = (len(vagas_all) - len(vagas)) + (len(news_all) - len(news))

    pieces = []
    if vagas_all:
        pieces.append(_count(len(vagas_all), "vaga nova", "vagas novas"))
    if news_all:
        pieces.append(_count(len(news_all), "notícia de seleção", "notícias de seleção"))
    if freelas:
        pieces.append(_count(len(freelas), "freela novo", "freelas novos"))
    headline = " e ".join(pieces) or "Sem novidades"

    msg = EmailMessage()
    msg["Subject"] = f"{cfg.get('subject_prefix', 'Ragas')}: {headline} em {today_label}"
    msg["From"] = sender
    msg["To"] = recipient

    # --- texto simples ---
    lines = ([greeting, ""] if greeting else []) + [f"{headline}.", ""]
    for j in vagas:
        tag = (" [grande empresa]" if j.grande else "") + (f" [R$ {j.salary:,}]".replace(",", ".") if j.salary else "")
        lines += [j.title, f"{j.company}{tag} | {_where(j)}", j.url, ""]
    if news:
        lines += ["Processos seletivos nas notícias:", ""]
        for j in news:
            lines += [j.title, f"{j.company} | {j.location}", j.url, ""]
    if freelas:
        lines += ["Freelas novos:", ""]
        for j in freelas:
            lines += [j.title, freela_line(j), j.url, ""]
    if hidden > 0:
        lines.append(f"+ {hidden} no painel.")
    if dashboard_url:
        lines.append(f"Painel: {dashboard_url}")
    if footer:
        lines += ["", footer]
    msg.set_content("\n".join(lines))

    # --- HTML ---
    def row(j: Job) -> str:
        why = escape(", ".join(j.reasons[1:4])) if len(j.reasons) > 1 else ""
        posted = (f"publicada em {escape(j.posted_at[8:10])}/{escape(j.posted_at[5:7])}"
                  if j.posted_at else "")
        badges = " ".join(b for b in (
            '<span style="background:#DCECEF;color:#0B5563;border-radius:9px;padding:1px 7px;font-size:11px">grande empresa</span>' if j.grande else "",
            '<span style="background:#EEE9FB;color:#4B3A8F;border-radius:9px;padding:1px 7px;font-size:11px">área correlata</span>' if j.area == "correlata" else "",
            '<span style="background:#FFF1CC;color:#5A4300;border-radius:9px;padding:1px 7px;font-size:11px">suporte técnico</span>' if j.area == "suporte" else "",
            '<span style="background:#1B2A3B;color:#fff;border-radius:9px;padding:1px 7px;font-size:11px">exterior</span>' if j.abroad else "",
            f'<span style="background:#E3E8EE;color:#1B2A3B;border-radius:9px;padding:1px 7px;font-size:11px">inglês {EN_LABEL[j.english]}</span>' if j.english or j.abroad else "",
            f'<span style="background:#E3E8EE;color:#1B2A3B;border-radius:9px;padding:1px 7px;font-size:11px">R$ {j.salary:,}'.replace(",", ".") + "</span>" if j.salary else "",
        ) if b)
        if j.tipo == "noticia":
            second = f"{escape(j.company)} &nbsp;<span style=\"font-size:13px;color:#5B6B7B\">{escape(j.location)}</span>"
        else:
            second = (f"{escape(j.company)} &nbsp;<span style=\"font-size:13px;color:#5B6B7B\">"
                      f"{escape(_where(j))}</span>")
        meta = " &middot; ".join(x for x in (escape(SOURCE_LABEL.get(j.source, j.source)), posted, why) if x)
        return f"""
<tr><td style="padding:14px 0;border-bottom:1px solid #E3E8EE">
  <a href="{escape(j.url, quote=True)}" style="font-size:16px;font-weight:600;color:#037A46;text-decoration:none">{escape(j.title)}</a><br>
  <span style="font-size:14px;color:#1B2A3B">{second}</span> {badges}<br>
  <span style="font-size:12px;color:#5B6B7B">{meta}</span>
</td></tr>"""

    body = "".join(row(j) for j in vagas)
    if news:
        body += ('<tr><td style="padding:22px 0 0"><h2 style="margin:0;font-size:17px;color:#0F1B2D">'
                 'Processos seletivos nas notícias</h2></td></tr>' + "".join(row(j) for j in news))
    if freelas:
        body += ('<tr><td style="padding:22px 0 0"><h2 style="margin:0;font-size:17px;color:#0F1B2D">'
                 'Freelas novos</h2></td></tr>' + "".join(
                     f'''
<tr><td style="padding:14px 0;border-bottom:1px solid #E3E8EE">
  <a href="{escape(j.url, quote=True)}" style="font-size:16px;font-weight:600;color:#037A46;text-decoration:none">{escape(j.title)}</a><br>
  <span style="font-size:13px;color:#5B6B7B">{escape(freela_line(j))}</span>
</td></tr>''' for j in freelas))
    more = f'<p style="font-size:14px;color:#5B6B7B">Mais {hidden} no painel.</p>' if hidden > 0 else ""
    button = (f'<p style="margin:22px 0 0"><a href="{escape(dashboard_url, quote=True)}" '
              'style="background:#00C060;color:#03140B;font-weight:700;padding:10px 16px;border-radius:6px;'
              'text-decoration:none;font-size:14px">Abrir o painel</a></p>') if dashboard_url else ""
    greet_row = (f'<tr><td style="padding:14px 0 0;font-size:15px;color:#1B2A3B">{escape(greeting)}</td></tr>'
                 if greeting else "")
    foot_row = (f'<tr><td style="padding:22px 0 0;font-size:12px;color:#5B6B7B;border-top:1px solid #E3E8EE">'
                f'{escape(footer)}</td></tr>' if footer else "")
    html = f"""<!doctype html><html lang="pt-BR"><body style="margin:0;background:#F3F6F8;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:8px;padding:8px 24px 24px">
<tr><td style="padding:20px 0 0"><span style="display:inline-block;padding:4px 10px;border-radius:999px;background:#00C060;color:#03140B;font-size:13px;font-weight:700;letter-spacing:-0.01em">ragas</span> <span style="font-size:12px;color:#5B6B7B">central de vagas</span></td></tr>
{greet_row}
<tr><td style="padding:12px 0 4px"><h1 style="margin:0;font-size:22px;color:#0F1B2D">{escape(headline)}</h1></td></tr>
{body}
<tr><td>{more}{button}</td></tr>
{foot_row}
</table></td></tr></table></body></html>"""
    msg.add_alternative(html, subtype="html")
    return msg


def send(msg: EmailMessage, user: str, password: str,
         host: str = "smtp.gmail.com", port: int = 465) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
        server.login(user, password)
        server.send_message(msg)


def credentials() -> tuple[str, str, str]:
    """(usuário, senha de app, destinatário) das variáveis de ambiente."""
    user = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")
    to = os.environ.get("EMAIL_TO", "") or user
    return user, password, to
