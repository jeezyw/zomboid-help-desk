"""Tails the Project Zomboid dedicated server's own console log directly from disk,
instead of going through `docker logs`. Many PZ server setups never write meaningful
output to the container's stdout/stderr at all - the server writes its live console
output to a file instead, conventionally "server-console.txt" sitting alongside the
Server/ config directory in the same Zomboid data root this app already has direct
filesystem access to via ZOMBOID_DATA. No Docker control/docker.sock involvement
needed for this - it's a plain file read.

UNVERIFIED assumption: "<ZOMBOID_DATA>/server-console.txt" is a best-effort guess
based on common PZ admin documentation, not confirmed against every possible server
layout. find_console_log() also checks a Logs/ subdirectory as a fallback and picks
whichever candidate was modified most recently.
"""

from __future__ import annotations

from pathlib import Path

from . import config

CANDIDATE_NAMES = ["server-console.txt", "console.txt"]


def find_console_log() -> Path | None:
    candidates: list[Path] = []

    for name in CANDIDATE_NAMES:
        p = config.DATA / name
        if p.is_file():
            candidates.append(p)

    logs_dir = config.DATA / "Logs"
    if logs_dir.is_dir():
        candidates.extend(p for p in logs_dir.glob("*.txt") if p.is_file())

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_since(path: Path, offset: int | None, tail: int = 300, chunk_bytes: int = 200_000) -> tuple[list[str], int]:
    """Reads new lines since a byte `offset`. On a cold start (offset is None, or
    stale/past the current size - e.g. the file was rotated/truncated since), reads
    only the last `chunk_bytes` instead of the whole file and returns at most `tail`
    lines, to bound the very first read on a long-lived log rather than loading
    potentially many MB into memory at once.

    Offset-based reads are exact and non-overlapping by construction, so callers
    don't need to de-duplicate a boundary line between polls the way `docker logs
    --since` (inclusive on both ends) requires.
    """
    size = path.stat().st_size
    cold_start = offset is None or offset > size
    start = max(0, size - chunk_bytes) if cold_start else offset

    with path.open("rb") as f:
        f.seek(start)
        raw = f.read()

    lines = raw.decode("utf-8", errors="replace").splitlines()

    if cold_start:
        if start > 0 and lines:
            lines = lines[1:]  # drop the likely-truncated fragment from landing mid-file
        lines = lines[-tail:] if tail else []

    return lines, size
