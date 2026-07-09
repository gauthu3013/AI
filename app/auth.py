"""Mock LTTS login.

Validates the email domain and PS Number format and issues an in-memory
session token. This is a demo stand-in for real LTTS SSO — do not use it
as-is in production.
"""

import re
import secrets

ALLOWED_DOMAIN = "@ltts.com"
PS_NUMBER_RE = re.compile(r"^\d{5,8}$")

# token -> {"email": ..., "ps_number": ...}
_sessions: dict[str, dict] = {}


def login(email: str, ps_number: str) -> str | None:
    email = (email or "").strip().lower()
    ps_number = (ps_number or "").strip()
    if not email.endswith(ALLOWED_DOMAIN):
        return None
    local_part = email[: -len(ALLOWED_DOMAIN)]
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", local_part):
        return None
    if not PS_NUMBER_RE.fullmatch(ps_number):
        return None
    token = secrets.token_urlsafe(24)
    _sessions[token] = {"email": email, "ps_number": ps_number}
    return token


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    return _sessions.get(token)


def logout(token: str) -> None:
    _sessions.pop(token, None)
