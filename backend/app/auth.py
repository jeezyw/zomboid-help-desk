"""Optional secure mode - a single shared admin login gating the whole API.

Off by default (config.SECURE_MODE). Credentials are a plain username/password
pair set via env vars (WEBUI_USERNAME/WEBUI_PASSWORD in docker-compose.yml) -
there's no per-user account system here, just one operator-controlled secret,
matching the trust model this app already uses elsewhere (e.g. the old
CONTROL_AGENT_TOKEN) - so a password-hashing dependency would buy nothing.

Sessions are opaque random tokens stored in the `sessions` table (see db.py),
not signed/stateless cookies - persisting them to sqlite (rather than an
in-memory dict) means a container restart doesn't force every open browser tab
to re-login, consistent with "everything except todos.json lives in webui.db."
"""

from __future__ import annotations

import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from . import config
from .db import db

COOKIE_NAME = "session"
SESSION_TTL_DAYS = 30

# In-memory failed-login throttle, keyed by client IP. Deliberately not
# persisted - it only needs to survive within one process's uptime to blunt
# trivial brute-force attempts against the single shared password.
MAX_FAILURES = 5
LOCKOUT_SECONDS = 60
_failures: dict[str, dict[str, float]] = {}


def seconds_until_unlocked(ip: str) -> float:
    """0 if not locked out, else seconds remaining."""
    entry = _failures.get(ip)
    if not entry:
        return 0.0
    remaining = entry["locked_until"] - time.monotonic()
    return remaining if remaining > 0 else 0.0


def record_failure(ip: str) -> None:
    entry = _failures.setdefault(ip, {"count": 0.0, "locked_until": 0.0})
    entry["count"] += 1
    if entry["count"] >= MAX_FAILURES:
        entry["locked_until"] = time.monotonic() + LOCKOUT_SECONDS
        entry["count"] = 0


def record_success(ip: str) -> None:
    _failures.pop(ip, None)


def verify_credentials(username: str, password: str) -> bool:
    # compare_digest requires equal-length-independent constant time comparison
    # for BOTH fields - checking with `and` short-circuits on length/content but
    # each individual compare_digest call is itself constant-time, which is what
    # actually matters against a timing attack on the password.
    return (
        hmac.compare_digest(username, config.AUTH_USERNAME)
        and hmac.compare_digest(password, config.AUTH_PASSWORD)
    )


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_TTL_DAYS)
    with db() as c:
        c.execute(
            "INSERT INTO sessions(token, created_at, expires_at) VALUES(?,?,?)",
            (token, now.isoformat(), expires_at.isoformat()),
        )
    return token


def validate_session(token: str | None) -> bool:
    if not token:
        return False
    now = datetime.now(timezone.utc)
    with db() as c:
        row = c.execute("SELECT expires_at FROM sessions WHERE token=?", (token,)).fetchone()
        if not row:
            return False
        if datetime.fromisoformat(row[0]) < now:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))
            return False
        # Sliding expiry - an active session shouldn't expire out from under a
        # user who's actively using the app.
        new_expires = now + timedelta(days=SESSION_TTL_DAYS)
        c.execute("UPDATE sessions SET expires_at=? WHERE token=?", (new_expires.isoformat(), token))
    return True


def delete_session(token: str) -> None:
    with db() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))
