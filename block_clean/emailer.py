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


def cleanup_note(volunteer, case, before_url, after_url):
    where = (case.get("address") or "a nearby sidewalk").split(",")[0].title()
    subject = "A neighbor cleaned the sidewalk near your shop"
    text = (
        f"{volunteer['display_name']} ({volunteer['email']}) picked up a 311 "
        f"street-cleaning request near your shop.\n\n"
        f"What: {case.get('detail_label') or 'Street and sidewalk cleaning'}\n"
        f"Where: {where}\n"
        f"Neighborhood: {case.get('neighborhood') or 'San Francisco'}\n\n"
        f"After photo: {after_url}\n"
        f"Before photo: {before_url}\n\n"
        "This note is so you can thank them or help with the next one: "
        "supplies, a coffee, a hand on the following block. "
        "Reply to this email and it goes to them.\n\n"
        "Submitting the photo here does not close the official city 311 case."
    )
    return subject, text


def notify_shops(shops, volunteer, case, before_url, after_url, after_file):
    subject, text = cleanup_note(volunteer, case, before_url, after_url)
    results = []
    for shop in shops:
        try:
            _deliver(
                to_email=shop["email"],
                to_name=shop.get("name") or shop["email"],
                reply_to=volunteer["email"],
                subject=subject,
                text=text,
                attachment=after_file,
            )
            results.append({
                "name": shop.get("name") or "",
                "email": shop["email"],
                "distance_m": shop.get("distance_m"),
                "delivery": mail_mode(),
            })
        except Exception as exc:
            results.append({
                "name": shop.get("name") or "",
                "email": shop["email"],
                "distance_m": shop.get("distance_m"),
                "delivery": "failed",
                "error": str(exc),
            })
    return {"subject": subject, "text": text, "reply_to": volunteer["email"], "shops": results}


def _deliver(to_email, to_name, reply_to, subject, text, attachment):
    mode = mail_mode()
    sender = os.getenv("EMAIL_FROM", "Block Clean <cleanup@localhost>")
    if mode == "resend":
        _send_resend(sender, to_email, reply_to, subject, text, attachment)
        return
    if mode == "smtp":
        _send_smtp(sender, to_email, reply_to, subject, text, attachment)
        return
    _write_outbox({
        "to": to_email,
        "to_name": to_name,
        "from": sender,
        "reply_to": reply_to,
        "subject": subject,
        "text": text,
        "attachment": str(attachment) if attachment else None,
    })


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
        data = Path(attachment).read_bytes()
        payload["attachments"] = [{
            "filename": Path(attachment).name,
            "content": base64.b64encode(data).decode(),
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
