"""Configuration History: records old/new values whenever sandbox or ini settings
change, so past edits can be reviewed and reverted. See routers/config_history.py."""

import json
from typing import Any

from .db import db, utcnow


def record_changes(source: str, profile: str, current: dict[str, Any], changes: dict[str, Any]):
    with db() as c:
        for key, new_value in changes.items():
            old_value = current.get(key)
            # str(...) fallback: ini scalar coercion can flip a purely-numeric list
            # field (e.g. WorkshopItems with one entry) between int and str across
            # writes with no actual content change - don't log that as a "change".
            if old_value == new_value or str(old_value) == str(new_value):
                continue
            c.execute(
                "INSERT INTO config_changes(changed_at, source, profile, key, old_value, new_value) "
                "VALUES (?,?,?,?,?,?)",
                (utcnow(), source, profile, key, json.dumps(old_value), json.dumps(new_value)),
            )
