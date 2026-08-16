"""Backup Manager: tar.gz snapshots of a server profile's config files (and
optionally its save directory), with retention thinning and safety-snapshot restore.

Save directory discovery is a best-effort guess (see discover_save_dir) - PZ dedicated
saves conventionally live under "<data_root>/Saves/Multiplayer/<servername>/" where
<data_root> is the same root that contains "Server/". This is not hardcoded blindly:
it fails soft to None if the guessed directory doesn't exist, and callers can override
it per-profile via kv (see get_save_dir_override/set_save_dir_override).
"""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .db import audit, db, get_setting, set_setting, utcnow

DEFAULT_RETENTION = {
    "hourly": 24,
    "daily": 7,
    "weekly": 4,
    "monthly": 6,
    "always_keep_manual": True,
}


def get_retention_policy() -> dict[str, Any]:
    raw = get_setting("backup_retention")
    if not raw:
        return dict(DEFAULT_RETENTION)
    policy = dict(DEFAULT_RETENTION)
    policy.update(json.loads(raw))
    return policy


def set_retention_policy(policy: dict[str, Any]):
    merged = get_retention_policy()
    merged.update(policy)
    set_setting("backup_retention", json.dumps(merged))


def get_save_dir_override(profile_name: str) -> str | None:
    return get_setting(f"save_dir_override:{profile_name}")


def set_save_dir_override(profile_name: str, path: str):
    set_setting(f"save_dir_override:{profile_name}", path)


def discover_save_dir(profile: dict) -> Path | None:
    override = get_save_dir_override(profile["name"])
    if override:
        p = Path(override)
        return p if p.is_dir() else None

    directory = Path(profile["directory"])
    candidate = directory.parent / "Saves" / "Multiplayer" / profile["name"]
    return candidate if candidate.is_dir() else None


def _config_files(profile: dict) -> list[Path]:
    directory = Path(profile["directory"])
    prefix = profile["name"] if profile["name"] != "(unnamed)" else None

    if not prefix:
        # Fall back to the four explicitly known paths for the unnamed-profile case.
        paths = [profile.get("sandbox_vars"), profile.get("ini"),
                  profile.get("spawnpoints"), profile.get("spawnregions")]
        return [Path(p) for p in paths if p]

    files = {p for p in directory.glob(f"{prefix}_*") if p.is_file()}
    ini = directory / f"{prefix}.ini"
    if ini.exists():
        files.add(ini)
    # Floor guarantee: always include whatever discover_profiles already found.
    for key in ("sandbox_vars", "ini", "spawnpoints", "spawnregions"):
        if profile.get(key):
            files.add(Path(profile[key]))
    return sorted(files)


def create_backup(profile: dict, kind: str, include_save: bool = False, note: str = "") -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = config.BACKUP_ROOT / profile["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / f"{ts}.tar.gz"

    save_dir = discover_save_dir(profile) if include_save else None

    with tarfile.open(archive_path, "w:gz") as tar:
        for f in _config_files(profile):
            if f.exists():
                tar.add(f, arcname=f"config/{f.name}")
        if save_dir:
            tar.add(save_dir, arcname=f"save/{save_dir.name}")

    size_bytes = archive_path.stat().st_size
    with db() as c:
        cur = c.execute(
            "INSERT INTO backups(profile, created_at, kind, size_bytes, path, "
            "includes_save_data, save_dir_path, note) VALUES (?,?,?,?,?,?,?,?)",
            (profile["name"], utcnow(), kind, size_bytes, str(archive_path),
             1 if save_dir else 0, str(save_dir) if save_dir else None, note),
        )
        row_id = cur.lastrowid

    audit("backup.create", f"profile={profile['name']} kind={kind} id={row_id}")
    sweep_retention(profile["name"])
    return get_backup(row_id)


def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "profile": row[1], "created_at": row[2], "kind": row[3],
        "size_bytes": row[4], "path": row[5], "includes_save_data": bool(row[6]),
        "save_dir_path": row[7], "note": row[8],
    }


def get_backup(backup_id: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM backups WHERE id=?", (backup_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_backups(profile: str | None = None) -> list[dict]:
    with db() as c:
        if profile:
            rows = c.execute(
                "SELECT * FROM backups WHERE profile=? ORDER BY created_at DESC", (profile,)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM backups ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]


def delete_backup(backup_id: int):
    row = get_backup(backup_id)
    if not row:
        return
    Path(row["path"]).unlink(missing_ok=True)
    with db() as c:
        c.execute("DELETE FROM backups WHERE id=?", (backup_id,))
    audit("backup.delete", f"id={backup_id}")


def _iso_week(ts: str) -> str:
    d = datetime.fromisoformat(ts)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def sweep_retention(profile: str) -> dict:
    policy = get_retention_policy()
    rows = list_backups(profile)  # newest first

    keep: set[int] = set()
    if policy.get("always_keep_manual", True):
        keep |= {r["id"] for r in rows if r["kind"] == "manual"}

    safety_rows = [r for r in rows if r["kind"] == "pre-restore-safety"]
    if safety_rows:
        keep.add(safety_rows[0]["id"])  # keep only the most recent safety snapshot

    def thin(bucket_fn, count: int):
        seen: set[str] = set()
        for r in rows:
            if r["kind"] in ("manual", "pre-restore-safety"):
                continue
            bucket = bucket_fn(r["created_at"])
            if bucket not in seen and len(seen) < count:
                seen.add(bucket)
                keep.add(r["id"])

    thin(lambda ts: ts[:13], policy["hourly"])   # YYYY-MM-DDTHH
    thin(lambda ts: ts[:10], policy["daily"])    # YYYY-MM-DD
    thin(_iso_week, policy["weekly"])
    thin(lambda ts: ts[:7], policy["monthly"])   # YYYY-MM

    deleted = 0
    for r in rows:
        if r["id"] not in keep:
            delete_backup(r["id"])
            deleted += 1

    return {"kept": len(keep), "deleted": deleted}


def restore_backup(profile: dict, backup_id: int) -> dict:
    row = get_backup(backup_id)
    if not row:
        raise ValueError(f"Backup {backup_id} not found")

    safety = create_backup(profile, kind="pre-restore-safety",
                            include_save=row["includes_save_data"],
                            note=f"auto safety snapshot before restoring backup #{backup_id}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        with tarfile.open(row["path"], "r:gz") as tar:
            tar.extractall(tmp, filter="data")  # PEP 706 safe extraction

        config_dir = tmp / "config"
        if config_dir.exists():
            for f in config_dir.iterdir():
                shutil.copy2(f, Path(profile["directory"], f.name))

        save_src = tmp / "save"
        if save_src.exists() and row["save_dir_path"]:
            shutil.copytree(save_src, row["save_dir_path"], dirs_exist_ok=True)

    audit("backup.restore", f"id={backup_id} profile={profile['name']}")
    return {"ok": True, "restored_from": backup_id, "safety_backup_id": safety["id"]}
