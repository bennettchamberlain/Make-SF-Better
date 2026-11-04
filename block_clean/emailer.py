import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests

from paths import OUTBOX_PATH, ROOT, ensure_dirs


def mail_mode():
    if os.getenv("RESEND_API_KEY", "").strip():
        return "resend"
    if os.getenv("SMTP_HOST", "").strip():
        return "smtp"
    return "outbox"


def cleanup_note(volunteer, case, before_url, after_url, shop_name=""):
    where = (case.get("address") or "a nearby sidewalk").split(",")[0].title()
    shop = shop_name or "your shop"
    subject = f"I cleaned the sidewalk near {shop}"
    text = (
        f"I cleaned up a sidewalk mess near {shop}.\n\n"
        f"What: {case.get('detail_label') or 'Street and sidewalk cleaning'}\n"
        f"Where: {where}\n"
        f"Neighborhood: {case.get('neighborhood') or 'San Francisco'}\n\n"
        "I was able to clear it and noticed it was right around your business. "
        "The before and after photos are attached. "
        "If that helped, a coffee, some supplies, or a hand on the next block "
        "would make it worth doing again.\n\n"
        f"— {volunteer['display_name']}\n"
        f"{volunteer['email']}\n\n"
        f"After photo: {after_url}\n"
        f"Before photo: {before_url}\n\n"
        "This note does not close the official city 311 case."
    )
    return subject, text


def notify_shops(shops, volunteer, case, before_url, after_url, after_file, before_file=None, gmail=None):
    results = []
    note = {"subject": "", "text": "", "reply_to": volunteer["email"]}
    for shop in shops:
        subject, text = cleanup_note(volunteer, case, before_url, after_url, shop.get("name") or "")
        note = {"subject": subject, "text": text, "reply_to": volunteer["email"]}
        try:
            delivery = _deliver(
                to_email=shop["email"],
                to_name=shop.get("name") or shop["email"],
                reply_to=volunteer["email"],
                subject=subject,
                text=text,
                attachments=[path for path in (before_file, after_file) if path],
                gmail=gmail,
            )
            results.append({
                "name": shop.get("name") or "",
                "email": shop["email"],
                "distance_m": shop.get("distance_m"),
                "delivery": delivery,
            })
        except Exception as exc:
            results.append({
                "name": shop.get("name") or "",
                "email": shop["email"],
                "distance_m": shop.get("distance_m"),
                "delivery": "failed",
                "error": _public_mail_error(exc),
            })
    if not note["subject"]:
        note["subject"], note["text"] = cleanup_note(volunteer, case, before_url, after_url)
    return {"subject": note["subject"], "text": note["text"], "reply_to": note["reply_to"], "shops": results}


def _deliver(to_email, to_name, reply_to, subject, text, attachments, gmail=None):
    if gmail and gmail.get("app_password"):
        _send_gmail(gmail, to_email, subject, text, attachments)
        return "gmail"
    sender = os.getenv("EMAIL_FROM", "Block Clean <cleanup@localhost>")
    mode = mail_mode()
    if mode == "resend":
        _send_resend(sender, to_email, reply_to, subject, text, attachments[-1] if attachments else None)
        return mode
    if mode == "smtp":
        _send_smtp(sender, to_email, reply_to, subject, text, attachments[-1] if attachments else None)
        return mode
    _write_outbox({
        "to": to_email,
        "to_name": to_name,
        "from": sender,
        "reply_to": reply_to,
        "subject": subject,
        "text": text,
        "attachments": [str(path) for path in attachments],
    })
    return "outbox"


def check_gmail(email, app_password):
    """Confirm Google will accept this app password before we keep it."""
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(email, app_password)


def _send_gmail(gmail, to_email, subject, text, attachments):
    message = EmailMessage()
    message["Subject"] = subject.replace("\n", " ").replace("\r", " ")
    message["From"] = f"{gmail.get('display_name') or 'A neighbor'} <{gmail['email']}>"
    message["To"] = to_email
    message["Reply-To"] = gmail["email"]
    message.set_content(text)
    for path in attachments:
        _attach(message, path)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(gmail["email"], gmail["app_password"])
        smtp.send_message(message)


def _attach(message, path):
    file_path = Path(path)
    if not file_path.exists():
        return
    subtype = "jpeg" if file_path.suffix.lower() in {".jpg", ".jpeg"} else file_path.suffix.lower().lstrip(".") or "octet-stream"
    message.add_attachment(file_path.read_bytes(), maintype="image", subtype=subtype, filename=file_path.name)


def _public_mail_error(exc):
    text = str(exc).lower()
    if "auth" in text or "username" in text or "password" in text:
        return "Gmail refused that app password"
    return "The email could not be sent"


def _send_resend(sender, to_email, reply_to, subject, text, attachment):
    payload = {
        "from": sender,
        "to": [to_email],
        "reply_to": reply_to,
        "subject": subject,
        "text": text,
    }
    if attachment and Path(attachment).exists():
        import base64
        path = Path(attachment)
        payload["attachments"] = [{
            "filename": path.name,
            "content": base64.b64encode(path.read_bytes()).decode(),
        }]
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def _send_smtp(sender, to_email, reply_to, subject, text, attachment):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    message["Reply-To"] = reply_to
    message.set_content(text)
    if attachment and Path(attachment).exists():
        path = Path(attachment)
        subtype = "jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else path.suffix.lower().lstrip(".") or "octet-stream"
        message.add_attachment(path.read_bytes(), maintype="image", subtype=subtype, filename=path.name)
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        user = os.getenv("SMTP_USER", "").strip()
        password = os.getenv("SMTP_PASSWORD", "")
        if user:
            smtp.login(user, password)
        smtp.send_message(message)


def _write_outbox(record):
    ensure_dirs()
    with OUTBOX_PATH.open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def public_url(path):
    base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base + path


def upload_file(url_path):
    """Map a /uploads/ name back to the file on disk, for the email attachment."""
    if not url_path or not url_path.startswith("/uploads/"):
        return None
    path = ROOT / url_path.lstrip("/")
    return path if path.exists() else None
