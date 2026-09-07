"""Authentication primitives: password hashing, JWT issue/verify, roles."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from . import config

CITIZEN = "citizen"
RESPONDER = "responder"
ADMIN = "admin"
ROLES = {CITIZEN, RESPONDER, ADMIN}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, config.PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${config.PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_access_token(user_id: int, role: str, organisation: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_EXPIRES_MINUTES),
    }
    if organisation:
        payload["org"] = organisation
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return the verified payload, or None when the token is invalid/expired."""
    try:
        return jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None


def normalize_phone(raw: str) -> str:
    """E.164-ish normalisation used for WhatsApp dispatch and login identity."""
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        return digits
    if digits.startswith("0"):
        return "+92" + digits[1:]
    return "+" + digits


def mask_phone(phone: str) -> str:
    """Hide the middle of a number when echoing it back to non-owner roles."""
    if len(phone) < 6:
        return phone
    return f"{phone[:4]}•••{phone[-3:]}"
