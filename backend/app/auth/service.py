"""User accounts, credential verification and role administration."""
from datetime import datetime, timezone

from ..core import security
from ..core.logging_conf import get_logger
from ..storage.db import get_conn

log = get_logger(__name__)

MIN_PASSWORD_LENGTH = 8
PUBLIC_COLUMNS = (
    "u.id, u.full_name, u.phone, u.email, u.role, u.ngo_id, u.is_active,"
    " u.is_demo, u.created_at, n.name AS ngo_name"
)
JOINS = "LEFT JOIN ngos n ON n.id = u.ngo_id"


class AuthError(Exception):
    """A credential or account problem the router maps to an HTTP status."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public(row) -> dict:
    user = dict(row)
    user["is_active"] = bool(user["is_active"])
    user["is_demo"] = bool(user["is_demo"])
    return user


def validate_credentials(full_name: str, password: str, phone: str | None, email: str | None) -> tuple[str, str | None]:
    """Return (normalised phone, normalised email) or raise AuthError.

    At least one identifier is required because it is how a responder reaches a
    citizen on WhatsApp and how a citizen recovers access.
    """
    if len(full_name.strip()) < 2:
        raise AuthError("full_name must be at least 2 characters", 422)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"password must be at least {MIN_PASSWORD_LENGTH} characters", 422)

    normalized_phone = security.normalize_phone(phone) if phone else None
    if phone and len("".join(c for c in normalized_phone if c.isdigit())) < 10:
        raise AuthError("phone number looks too short", 422)

    normalized_email = email.strip().lower() if email else None
    if email and ("@" not in normalized_email or "." not in normalized_email.split("@")[-1]):
        raise AuthError("invalid email address", 422)

    if not normalized_phone and not normalized_email:
        raise AuthError("a phone number or email address is required", 422)
    return normalized_phone, normalized_email


def create_user(
    full_name: str,
    password: str,
    role: str = security.CITIZEN,
    phone: str | None = None,
    email: str | None = None,
    ngo_id: int | None = None,
    is_demo: bool = False,
) -> dict:
    if role not in security.ROLES:
        raise AuthError(f"unknown role: {role}", 422)
    if role == security.RESPONDER and not ngo_id:
        raise AuthError(
            "a responder account must be linked to an NGO/rescue organisation", 422
        )

    normalized_phone, normalized_email = validate_credentials(full_name, password, phone, email)

    with get_conn() as conn:
        if normalized_phone:
            clash = conn.execute(
                "SELECT id FROM users WHERE phone = ?", (normalized_phone,)
            ).fetchone()
            if clash:
                raise AuthError("that phone number is already registered", 409)
        if normalized_email:
            clash = conn.execute(
                "SELECT id FROM users WHERE email = ?", (normalized_email,)
            ).fetchone()
            if clash:
                raise AuthError("that email address is already registered", 409)
        if ngo_id is not None and not conn.execute(
            "SELECT id FROM ngos WHERE id = ?", (ngo_id,)
        ).fetchone():
            raise AuthError(f"unknown ngo_id: {ngo_id}", 422)

        cursor = conn.execute(
            "INSERT INTO users (full_name, phone, email, password_hash, role, ngo_id,"
            " is_active, is_demo, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (
                full_name.strip(),
                normalized_phone,
                normalized_email,
                security.hash_password(password),
                role,
                ngo_id,
                1 if is_demo else 0,
                now_iso(),
            ),
        )
        user_id = cursor.lastrowid
        row = conn.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM users u {JOINS} WHERE u.id = ?", (user_id,)
        ).fetchone()
    log.info("created %s account id=%s", role, user_id)
    return _public(row)


def find_by_id(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM users u {JOINS} WHERE u.id = ?", (user_id,)
        ).fetchone()
    return _public(row) if row else None


def find_by_identifier(identifier: str) -> dict | None:
    """Look a user up by phone (normalised) or email (case-insensitive)."""
    identifier = identifier.strip()
    candidates = {identifier.lower()}
    if any(ch.isdigit() for ch in identifier):
        candidates.add(security.normalize_phone(identifier))
    with get_conn() as conn:
        for candidate in candidates:
            row = conn.execute(
                f"SELECT {PUBLIC_COLUMNS} FROM users u {JOINS}"
                " WHERE u.phone = ? OR u.email = ? LIMIT 1",
                (candidate, candidate),
            ).fetchone()
            if row:
                return _public(row)
    return None


def _load_password_hash(user_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return row["password_hash"] if row else None


def authenticate(identifier: str, password: str) -> dict:
    """Verify credentials and return the public user record.

    The same generic error is raised for unknown identifier and wrong password
    so the endpoint cannot be used to enumerate registered accounts.
    """
    invalid = AuthError("invalid identifier or password", 401)
    user = find_by_identifier(identifier)
    if user is None:
        raise invalid
    stored = _load_password_hash(user["id"])
    if stored is None or not security.verify_password(password, stored):
        raise invalid
    if not user["is_active"]:
        raise AuthError("this account is deactivated", 403)
    return user


def list_users(role: str | None = None, limit: int = 200) -> list[dict]:
    query = f"SELECT {PUBLIC_COLUMNS} FROM users u {JOINS}"
    params: list = []
    if role:
        query += " WHERE u.role = ?"
        params.append(role)
    query += " ORDER BY u.id LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [_public(row) for row in conn.execute(query, params)]


def update_user(user_id: int, *, full_name: str | None = None, phone: str | None = None,
                email: str | None = None, role: str | None = None, ngo_id: int | None = None,
                is_active: bool | None = None) -> dict:
    fields: list[str] = []
    params: list = []
    if full_name is not None:
        if len(full_name.strip()) < 2:
            raise AuthError("full_name must be at least 2 characters", 422)
        fields.append("full_name = ?")
        params.append(full_name.strip())
    if phone is not None:
        normalized = security.normalize_phone(phone)
        with get_conn() as conn:
            clash = conn.execute(
                "SELECT id FROM users WHERE phone = ? AND id != ?", (normalized, user_id)
            ).fetchone()
        if clash:
            raise AuthError("that phone number is already in use", 409)
        fields.append("phone = ?")
        params.append(normalized)
    if email is not None:
        normalized = email.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise AuthError("invalid email address", 422)
        fields.append("email = ?")
        params.append(normalized)
    if role is not None:
        if role not in security.ROLES:
            raise AuthError(f"unknown role: {role}", 422)
        fields.append("role = ?")
        params.append(role)
    if ngo_id is not None:
        fields.append("ngo_id = ?")
        params.append(ngo_id)
    if is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if is_active else 0)

    if not fields:
        raise AuthError("no fields to update", 422)

    with get_conn() as conn:
        current = conn.execute(
            "SELECT role, ngo_id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if current is None:
            raise AuthError(f"unknown user: {user_id}", 404)
        if ngo_id is not None and not conn.execute(
            "SELECT id FROM ngos WHERE id = ?", (ngo_id,)
        ).fetchone():
            raise AuthError(f"unknown ngo_id: {ngo_id}", 422)
        effective_role = role if role is not None else current["role"]
        effective_ngo_id = ngo_id if ngo_id is not None else current["ngo_id"]
        if effective_role == security.RESPONDER and not effective_ngo_id:
            raise AuthError(
                "a responder account must be linked to an NGO/rescue organisation", 422
            )

    params.append(user_id)
    with get_conn() as conn:
        updated = conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params
        ).rowcount
        if not updated:
            raise AuthError(f"unknown user: {user_id}", 404)
        row = conn.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM users u {JOINS} WHERE u.id = ?", (user_id,)
        ).fetchone()
    return _public(row)


def count_by_role() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, COUNT(*) AS n FROM users GROUP BY role"
        ).fetchall()
    counts = {role: 0 for role in security.ROLES}
    counts.update({row["role"]: row["n"] for row in rows})
    return counts
