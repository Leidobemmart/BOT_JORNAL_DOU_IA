from __future__ import annotations
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from .models import AppConfig
from .publication import Publication

logger = logging.getLogger(__name__)


# =========================
#  EMAIL BASE / ENVIO
# =========================

def send_email(subject: str, html_body: str, text_body: str, cfg: AppConfig) -> None:
    """Envia email usando configurações de SMTP e email do AppConfig."""

    if not cfg.email.all_recipients:
        raise ValueError("Nenhum destinatário configurado.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.email.from_addr
    msg["To"] = ", ".join(cfg.email.to)
    if cfg.email.cc:
        msg["Cc"] = ", ".join(cfg.email.cc)
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = cfg.email.all_recipients

    context = ssl.create_default_context()

    logger.info(
        "Enviando email: %s -> %d destinatário(s)",
        subject,
        len(recipients),
    )

    with smtplib.SMTP(cfg.smtp.host, cfg.smtp.port, timeout=30) as server:
        server.ehlo()
        if cfg.smtp.use_tls:
            server.starttls(context=context)
            server.ehlo()
        server.login(cfg.smtp.user, cfg.smtp.password)
        server.sendmail(cfg.email.from_addr, recipients, msg.as_string())

    logger.info("Email enviado com sucesso.")


# =========================
#  EMAIL DE TESTE
# =========================

def _build_test_email_bodies(cfg: AppConfig) -> tuple[str, str, str]:
    """Cria subject, html e text para email de teste."""

    subject = "DOU Bot - Teste de configuração"
    text_body = (
        "Este é um email de teste enviado pelo DOU Bot.\n\n"
        f"SMTP: {cfg.smtp.host}:{cfg.smtp.port}\n"
        f"Remetente: {cfg.email.from_addr}\n"
        f"Destinatários: {', '.join(cfg.email.to)}\n"
    )

    html_body = f"""
    <html>
      <body>
        <h2>DOU Bot - Teste de configuração</h2>
        <p>Este é um email de teste enviado pelo DOU Bot.</p>
        <ul>
          <li><b>SMTP:</b> {cfg.smtp.host}:{cfg.smtp.port}</li>
          <li><b>Remetente:</b> {cfg.email.from_addr}</li>
          <li><b>Destinatários:</b> {", ".join(cfg.email.to)}</li>
        </ul>
        <p>Se você recebeu este email, a configuração básica está funcionando ✅.</p>
      </body>
    </html>
    """

    return subject, html_body.strip(), text_body


def send_test_email(cfg: AppConfig) -> None:
    subject, html_body, text_body = _build_test_email_bodies(cfg)
    send_email(subject, html_body, text_body, cfg)


# =========================
#  EMAIL COM PUBLICAÇÕES
# =========================

def build_publications_email(
    publications: list[Publication],
    cfg: AppConfig,
) -> tuple[str, str, str]:
    """
    Monta subject, html e text para um email com lista de publicações.
    """

    count = len(publications)
    subject = f"DOU Bot - {count} publicação(ões) encontrada(s)"

    # Texto plano
    lines = [
        f"Encontradas {count} publicação(ões) no DOU.",
        "",
    ]
    for i, pub in enumerate(publications, 1):
        lines.append(f"{i}. {pub.as_line()}")
    text_body = "\n".join(lines)

    # HTML
    items_html = []
    for pub in publications:
        items_html.append(
            f"<li><a href='{pub.url}'>{pub.title}</a>"
            f"{f' – {pub.section}' if pub.section else ''}"
            "</li>"
        )

    html_body = f"""
    <html>
      <body>
        <h2>DOU Bot - Resultado da busca</h2>
        <p>Encontradas <b>{count}</b> publicação(ões) no DOU.</p>
        <ol>
          {''.join(items_html)}
        </ol>
      </body>
    </html>
    """

    return subject, html_body.strip(), text_body
