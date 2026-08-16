import sqlite3
from datetime import datetime, timezone

from . import config


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    config.DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS config_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            changed_at TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('sandbox','ini')),
            profile TEXT NOT NULL,
            key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT NOT NULL,
            created_at TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('manual','scheduled','pre-change','pre-restore-safety')),
            size_bytes INTEGER NOT NULL,
            path TEXT NOT NULL,
            includes_save_data INTEGER NOT NULL DEFAULT 0,
            save_dir_path TEXT,
            note TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS scheduled_restarts (
            id INTEGER PRIMARY KEY,
            mode TEXT NOT NULL CHECK(mode IN ('off','daily_at','interval_hours','when_empty')) DEFAULT 'off',
            time_of_day TEXT,
            interval_hours REAL,
            last_run_at TEXT,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS player_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            connected_at TEXT NOT NULL,
            disconnected_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sandbox_field_overrides (
            key TEXT PRIMARY KEY,
            favorite INTEGER NOT NULL DEFAULT 0,
            category_override TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sandbox_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            profile TEXT NOT NULL,
            settings TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    return conn


def get_setting(key: str) -> str | None:
    with db() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None


def set_setting(key: str, value: str):
    with db() as c:
        c.execute(
            "INSERT INTO kv(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def audit(action: str, detail: str = ""):
    with db() as c:
        c.execute(
            "INSERT INTO audit(created_at, action, detail) VALUES(?,?,?)",
            (utcnow(), action, detail),
        )
