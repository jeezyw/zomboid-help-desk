"""Optional, in-process Docker control for the Zomboid container - start/stop/
restart and CPU/RAM stats via the `docker` CLI.

Ported from the old standalone control-agent container (which held
/var/run/docker.sock and was reached over an internal HTTP API). Now that
Docker control is optional (see config.DOCKER_CONTROL_ENABLED) rather than a
given, there's no reason to keep it behind a second container and an HTTP
hop - it's just direct subprocess calls, gated at the call site by the flag.
This module is pure mechanism and doesn't check the flag itself.

subprocess.run is blocking, so every public function here is wrapped in
asyncio.to_thread - all existing call sites already `await` them (carried
over from when they were httpx calls to the control-agent).
"""

import asyncio
import re
import subprocess

from fastapi import HTTPException

from . import config


def _docker_not_found_error() -> HTTPException:
    return HTTPException(
        500,
        "The 'docker' CLI is not installed in this container. This image's "
        "Dockerfile copies the static binary from Docker Inc.'s own docker:cli "
        "image - rebuild with 'docker compose build --no-cache zomboid-webui' "
        "(a stale/cached image is the usual cause).",
    )


def _run(*args: str) -> str:
    try:
        p = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise _docker_not_found_error()
    except Exception as e:
        raise HTTPException(500, f"Docker CLI failed: {e}")

    if p.returncode != 0:
        raise HTTPException(500, p.stderr.strip() or "Docker command failed")

    return p.stdout


_SIZE_UNITS = {
    "B": 1,
    "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3, "TIB": 1024**4,
    # docker stats always reports binary (Ki/Mi/Gi) units, but parse decimal ones
    # too rather than assume - cheap insurance against a future Docker version
    # changing its formatting.
    "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4,
}


def _parse_docker_size(s: str) -> int:
    m = re.match(r"^([\d.]+)\s*([A-Za-z]+)$", s.strip())
    if not m:
        return 0
    value, unit = m.groups()
    return int(float(value) * _SIZE_UNITS.get(unit.upper(), 1))


def _stats_sync() -> dict:
    # `docker stats --no-stream` blocks briefly (~1s) while it samples two points
    # to compute the delta-based CPU%, then returns one line and exits. CPUPerc is
    # a percentage of ONE core (so it can exceed 100% on a multi-core box actually
    # using >1 core) - normalizing that against total host capacity is left to the
    # caller, which already knows the host's core count via psutil.
    output = _run(
        "stats", config.ZOMBOID_CONTAINER, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}"
    ).strip()
    cpu_str, _, mem_str = output.partition("|")
    cpu_percent = float(cpu_str.strip().rstrip("%") or 0)
    used_str = mem_str.split("/")[0].strip()
    return {
        "cpu_percent_raw": cpu_percent,
        "memory_bytes": _parse_docker_size(used_str),
    }


async def stats() -> dict:
    return await asyncio.to_thread(_stats_sync)


def _action_sync(action: str) -> dict:
    _run(action, config.ZOMBOID_CONTAINER)
    return {"ok": True, "action": action, "container": config.ZOMBOID_CONTAINER}


async def start() -> dict:
    return await asyncio.to_thread(_action_sync, "start")


async def stop() -> dict:
    return await asyncio.to_thread(_action_sync, "stop")


async def restart() -> dict:
    return await asyncio.to_thread(_action_sync, "restart")
