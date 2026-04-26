"""Email plugin — send emails via SMTP.

Configuration (set as environment variables or in a .env file):
    JARVIS_EMAIL         — your sender email address
    JARVIS_EMAIL_PASS    — your email app password (Gmail app password recommended)
    JARVIS_SMTP_HOST     — SMTP host (default: smtp.gmail.com)
    JARVIS_SMTP_PORT     — SMTP port (default: 587)
"""

import os
import smtplib
from email.mime.text import MIMEText
from openjarvis.plugins import plugin

_SMTP_HOST = os.environ.get("JARVIS_SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.environ.get("JARVIS_SMTP_PORT", "587"))


def _send(to: str, subject: str, body: str) -> None:
    sender = os.environ.get("JARVIS_EMAIL", "")
    password = os.environ.get("JARVIS_EMAIL_PASS", "")
    if not sender or not password:
        raise EnvironmentError(
            "Set JARVIS_EMAIL and JARVIS_EMAIL_PASS environment variables to use the email plugin."
        )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)


@plugin("send email")
def send_email(jarvis, s):
    """Send an email. Usage: send email"""
    to = s.strip()
    if not to:
        jarvis.say("Who should I send the email to? Enter the recipient's email address:")
        to = jarvis.input("> ").strip()
    if not to:
        jarvis.say("No recipient provided. Cancelling.")
        return

    jarvis.say("What is the subject?")
    subject = jarvis.input("> ").strip() or "(no subject)"

    jarvis.say("What should the message say?")
    body = jarvis.input("> ").strip()
    if not body:
        jarvis.say("Empty message. Cancelling.")
        return

    try:
        _send(to, subject, body)
        jarvis.say(f"Email sent to {to} successfully.")
    except EnvironmentError as exc:
        jarvis.say(str(exc))
    except Exception as exc:
        jarvis.say(f"Failed to send email: {exc}")


@plugin("email")
def email_alias(jarvis, s):
    """Send an email"""
    send_email(jarvis, s)
