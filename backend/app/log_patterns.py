"""Log line classification and player connect/disconnect detection, applied to lines
read from the PZ server's own server-console.txt (see console_log.py).

The PLAYER_EVENT_PATTERNS table below is a best-effort seed, NOT confirmed against
real Project Zomboid B42 console output. It's kept isolated here specifically so it's
cheap to correct once real log output has been seen - see routers/players.py, which
surfaces a permanent "this is inferred, not RCON" disclaimer in the API response
rather than presenting matches as ground truth.
"""

from __future__ import annotations

import re

CLASSIFY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ERROR", re.compile(r"error|exception|stack ?trace|traceback", re.I)),
    ("WARN", re.compile(r"\bwarn(ing)?\b", re.I)),
    ("PLAYER", re.compile(r"connected|disconnected|has joined|has left|\bchat\b", re.I)),
    ("MOD", re.compile(r"\bmods?\b|workshop", re.I)),
    ("SYSTEM", re.compile(r"server (started|starting|stopped|stopping)|saving|loaded map|initializ", re.I)),
]


def classify_line(text: str) -> str:
    for category, pattern in CLASSIFY_PATTERNS:
        if pattern.search(text):
            return category
    return "INFO"


# UNVERIFIED: real PZ dedicated server console connect/disconnect line formats were
# not confirmed against a captured log. These are best-effort seed patterns - correct
# them against real `docker logs <container>` output before trusting /api/players.
PLAYER_EVENT_PATTERNS: list[dict] = [
    {"event": "connect", "pattern": re.compile(r"'(?P<name>[^']+)'\s+connected", re.I)},
    {"event": "disconnect", "pattern": re.compile(r"'(?P<name>[^']+)'\s+disconnected", re.I)},
    {"event": "connect", "pattern": re.compile(r'"(?P<name>[^"]+)"\s+has joined', re.I)},
    {"event": "disconnect", "pattern": re.compile(r'"(?P<name>[^"]+)"\s+has left', re.I)},
]


def match_player_event(text: str) -> tuple[str, str] | None:
    for entry in PLAYER_EVENT_PATTERNS:
        m = entry["pattern"].search(text)
        if m:
            return entry["event"], m.group("name").strip()
    return None
