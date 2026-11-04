"""Encrypt a Gmail app password before it is written to Elasticsearch.

A one-way hash cannot log into Gmail later, so the password is encrypted and
only a SHA-256 fingerprint is treated as the public marker that one is saved.
"""

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from paths import ROOT


def normalize_app_password(value):
    return "".join((value or "").split()).replace("-", "")


def fingerprint(password):
    return hashlib.sha256(normalize_app_password(password).encode()).hexdigest()


def _fernet():
    raw = os.getenv("MAIL_SECRET", "").strip()
    if not raw:
        raw = _persist_secret()
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def _persist_secret():
    """Create a local encryption key once. It stays in .env, which is not committed."""
    secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
    env_path = ROOT / ".env"
    with env_path.open("a") as handle:
        handle.write(f"\nMAIL_SECRET={secret}\n")
    os.chmod(env_path, 0o600)
    os.environ["MAIL_SECRET"] = secret
    return secret


def seal(password):
    token = _fernet().encrypt(normalize_app_password(password).encode()).decode()
    return token, fingerprint(password)


def open_secret(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, AttributeError, ValueError) as exc:
        raise ValueError("The saved Gmail password could not be unlocked") from exc
