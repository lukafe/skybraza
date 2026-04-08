"""
Envio opcional de email com link público do resultado (POST /scope).

Requer: SMTP_HOST, SMTP_FROM, PUBLIC_APP_URL (base HTTPS da app, sem barra final).
Opcional: SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_USE_SSL=1 (porta 465).
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


def notify_email_configured() -> bool:
    return bool(
        (os.environ.get("SMTP_HOST") or "").strip()
        and (os.environ.get("SMTP_FROM") or "").strip()
        and (os.environ.get("PUBLIC_APP_URL") or "").strip()
    )


def is_plausible_email(addr: str) -> bool:
    s = (addr or "").strip()
    if not s or len(s) > 254:
        return False
    return bool(_EMAIL_RE.match(s))


def _build_result_url(sub_id: str) -> str:
    base = (os.environ.get("PUBLIC_APP_URL") or "").strip().rstrip("/")
    return f"{base}/resultado/{sub_id}"


def send_submission_result_email(
    to_addr: str,
    sub_id: str,
    institution: str,
    lang: str,
) -> None:
    if not notify_email_configured():
        return
    to_addr = (to_addr or "").strip()
    if not to_addr or not is_plausible_email(to_addr):
        return

    host = (os.environ.get("SMTP_HOST") or "").strip()
    port = int((os.environ.get("SMTP_PORT") or "587").strip() or "587")
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    from_addr = (os.environ.get("SMTP_FROM") or "").strip()
    use_ssl = (os.environ.get("SMTP_USE_SSL") or "").strip().lower() in ("1", "true", "yes")

    url = _build_result_url(sub_id)
    inst = (institution or "").strip() or ("—" if lang != "en" else "—")
    en = lang == "en"

    if en:
        subject = f"CertiK — IN 701 scope result ({inst})"
        body = (
            f"Your scope assessment is ready.\n\n"
            f"Institution: {inst}\n"
            f"Open your result (saved link):\n{url}\n\n"
            f"If you did not request this, you can ignore this message.\n"
        )
    else:
        subject = f"CertiK — Resultado do escopo IN 701 ({inst})"
        body = (
            f"O resultado da sua delimitação de escopo está disponível.\n\n"
            f"Instituição: {inst}\n"
            f"Consulte o resultado (link guardado):\n{url}\n\n"
            f"Se não pediu este email, pode ignorá-lo.\n"
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
    except Exception:
        logger.debug("SMTP send failed for submission %s", sub_id, exc_info=True)


__all__ = [
    "is_plausible_email",
    "notify_email_configured",
    "send_submission_result_email",
]
