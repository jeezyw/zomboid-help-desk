"""Minimal Source RCON protocol client (PZ uses this protocol unmodified - the same
one Source engine games and Minecraft use). Connect-per-call: opens a TCP connection,
authenticates, sends one command, drains the response, and closes - no persistent
connection/pool. That's cheap enough given how infrequently this is called (a handful
of times per player-list poll interval) and trivially resilient to the game server
restarting or hiccuping mid-session.

Two behaviors below are NOT verified against a live PZ server yet - flagged inline
exactly like log_patterns.py flags its own best-effort regexes. Confirm both the
first time this runs against a real server:

1. Some Source-protocol servers send an empty SERVERDATA_RESPONSE_VALUE packet before
   the real SERVERDATA_AUTH_RESPONSE during auth. _auth() reads in a loop and only
   accepts the packet typed AUTH_RESPONSE, but this exact sequencing hasn't been
   confirmed against PZ specifically.
2. The protocol has no explicit end-of-response marker, so multi-packet responses are
   drained via an idle-timeout heuristic. Confirm with a response long enough to span
   packets (e.g. `help`, or `players` with many people online).
"""

from __future__ import annotations

import asyncio
import socket
import struct

SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2  # same numeric value as AUTH_RESPONSE; direction disambiguates
SERVERDATA_RESPONSE_VALUE = 0

_HEADER = struct.Struct("<ii")  # id, type (both little-endian int32)


class RconError(Exception):
    """Base for all RCON failures."""


class RconDnsError(RconError):
    """Host name could not be resolved."""


class RconConnectError(RconError):
    """TCP connection could not be established (refused, unreachable, or timed out)."""


class RconTimeoutError(RconError):
    """Connected, but no response arrived in time during auth or command execution."""


class RconAuthError(RconError):
    """Connected, but the RCON password was rejected."""


class RconProtocolError(RconError):
    """A packet could not be parsed (bad size header or truncated body)."""


async def _send_packet(writer: asyncio.StreamWriter, pkt_id: int, pkt_type: int, body: str) -> None:
    payload = body.encode("utf-8", errors="replace") + b"\x00\x00"
    header = _HEADER.pack(pkt_id, pkt_type)
    size = len(header) + len(payload)
    writer.write(struct.pack("<i", size) + header + payload)
    await writer.drain()


async def _read_packet(reader: asyncio.StreamReader, timeout: float) -> tuple[int, int, str]:
    try:
        size_bytes = await asyncio.wait_for(reader.readexactly(4), timeout)
        (size,) = struct.unpack("<i", size_bytes)
        if size < 10 or size > 1 << 20:
            raise RconProtocolError(f"Implausible packet size: {size}")
        rest = await asyncio.wait_for(reader.readexactly(size), timeout)
    except asyncio.IncompleteReadError as e:
        raise RconProtocolError(f"Connection closed mid-packet: {e}")
    except struct.error as e:
        raise RconProtocolError(f"Malformed packet header: {e}")

    pkt_id, pkt_type = _HEADER.unpack(rest[:8])
    body = rest[8:-2].decode("utf-8", errors="replace")
    return pkt_id, pkt_type, body


async def _open(host: str, port: int, connect_timeout: float) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    try:
        return await asyncio.wait_for(asyncio.open_connection(host, port), connect_timeout)
    except socket.gaierror as e:
        raise RconDnsError(f"Could not resolve '{host}': {e}")
    except asyncio.TimeoutError:
        raise RconConnectError(f"Timed out connecting to {host}:{port}")
    except OSError as e:
        raise RconConnectError(f"Could not connect to {host}:{port}: {e}")


async def _auth(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, password: str, timeout: float) -> None:
    await _send_packet(writer, 1, SERVERDATA_AUTH, password)

    # Some servers send an empty SERVERDATA_RESPONSE_VALUE before the real
    # SERVERDATA_AUTH_RESPONSE - keep reading until we see the auth-typed packet.
    for _ in range(5):
        try:
            pkt_id, pkt_type, _body = await _read_packet(reader, timeout)
        except (asyncio.TimeoutError, RconProtocolError) as e:
            raise RconTimeoutError(f"No auth response from server: {e}")
        if pkt_type == SERVERDATA_AUTH_RESPONSE:
            if pkt_id == -1:
                raise RconAuthError("Authentication failed - check RCONPassword.")
            return
    raise RconProtocolError("Did not receive a SERVERDATA_AUTH_RESPONSE packet.")


async def _drain_response(
    reader: asyncio.StreamReader, expected_id: int, idle_timeout: float, max_wait: float
) -> str:
    chunks: list[str] = []
    loop = asyncio.get_event_loop()
    deadline = loop.time() + max_wait

    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            pkt_id, pkt_type, body = await _read_packet(reader, min(idle_timeout, remaining))
        except asyncio.TimeoutError:
            break  # idle gap = no more packets coming, as long as we already have some
        if pkt_type == SERVERDATA_RESPONSE_VALUE and pkt_id == expected_id:
            chunks.append(body)

    if not chunks:
        raise RconTimeoutError("No response received from the server.")
    return "".join(chunks)


async def rcon_execute(
    host: str,
    port: int,
    password: str,
    command: str,
    *,
    connect_timeout: float = 3.0,
    idle_timeout: float = 0.5,
    max_wait: float = 3.0,
) -> str:
    """Open a connection, authenticate, run one command, and return its response text.
    Raises an RconError subclass on any failure - never returns partial/garbage data."""
    reader, writer = await _open(host, port, connect_timeout)
    try:
        await _auth(reader, writer, password, connect_timeout)
        cmd_id = 2
        await _send_packet(writer, cmd_id, SERVERDATA_EXECCOMMAND, command)
        return await _drain_response(reader, cmd_id, idle_timeout, max_wait)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
