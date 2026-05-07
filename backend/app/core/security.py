import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash passwords with PBKDF2 so authentication has no heavy external dependency."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    new_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return hmac.compare_digest(base64.b64encode(new_digest).decode("ascii"), digest)


def _urlsafe_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(subject: str, role: str) -> str:
    """Create a small HMAC signed token used by the Vue frontend."""
    expire_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": int(expire_at.timestamp())}
    payload_raw = _urlsafe_b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.secret_key.encode("utf-8"), payload_raw.encode("ascii"), hashlib.sha256)
    return f"{payload_raw}.{_urlsafe_b64(signature.digest())}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload_raw, signature_raw = token.split(".", 1)
    except ValueError:
        return None

    expected = hmac.new(settings.secret_key.encode("utf-8"), payload_raw.encode("ascii"), hashlib.sha256)
    if not hmac.compare_digest(_urlsafe_b64(expected.digest()), signature_raw):
        return None

    payload = json.loads(_urlsafe_b64decode(payload_raw))
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        return None
    return payload
