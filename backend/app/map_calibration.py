"""Maps live player world coordinates (from live_map.py's ZHDPositionTracker
JSON) onto pixel positions in the Base Map (base_map.py's tiled static
image), so LiveMap.tsx can plot a marker at the right spot.

There's no known formula for this: the base map image's origin/scale/
rotation aren't documented anywhere (its source tool is unknown - see the
conversation that led here), unlike pzmap2dzi's own isometric renders, whose
projection math is in its own source. So instead of guessing, this stores an
admin-supplied calibration: 3 (world_x, world_y) <-> (pixel_x, pixel_y) point
pairs, picked by clicking known landmarks on the map and reading a player's
live coordinates standing there, from which a general 2D affine transform is
solved exactly. Elevation (z) is deliberately not handled - every player
renders as if at ground level, a known simplification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import get_setting, set_setting

CALIBRATION_KEY = "map_calibration_v1"

# Real calibration for the maintainer-supplied default Base Map image
# (backend/app/map/b42_map.jpg / base_tiles/), computed against a live B42
# deployment via the Live Map tab's own calibration flow - not fabricated.
# Only used when no kv override exists yet, same pattern as live_map.py's
# LIVE_MAP_ENABLED_KEY/is_enabled(). A deployment using a different base map
# image needs its own calibration - this default only applies to the one
# shipped with the app.
DEFAULT_CALIBRATION_PATH = Path(__file__).resolve().parent / "map" / "default_calibration.json"

Point = dict[str, float]  # {"world_x", "world_y", "pixel_x", "pixel_y"}


def _det3(m: list[list[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _solve3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Exact solve of a 3x3 linear system via Cramer's rule - no numpy
    dependency needed for exactly 3 calibration points."""
    d = _det3(matrix)
    if abs(d) < 1e-9:
        raise ValueError(
            "Those 3 points are collinear (or nearly so) in-game - pick 3 "
            "points that aren't roughly in a straight line."
        )
    result = []
    for col in range(3):
        m_i = [row[:] for row in matrix]
        for r in range(3):
            m_i[r][col] = rhs[r]
        result.append(_det3(m_i) / d)
    return result


def compute_affine(points: list[Point]) -> dict[str, float]:
    """pixel_x = a*world_x + b*world_y + c
    pixel_y = d*world_x + e*world_y + f"""
    if len(points) != 3:
        raise ValueError("Calibration needs exactly 3 points.")
    matrix = [[p["world_x"], p["world_y"], 1.0] for p in points]
    a, b, c = _solve3(matrix, [p["pixel_x"] for p in points])
    d, e, f = _solve3(matrix, [p["pixel_y"] for p in points])
    return {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f}


def _load_default_calibration() -> dict[str, Any]:
    if not DEFAULT_CALIBRATION_PATH.is_file():
        return {"points": [], "transform": None}
    return json.loads(DEFAULT_CALIBRATION_PATH.read_text(encoding="utf-8"))


def get_calibration() -> dict[str, Any]:
    """A kv override - once set, even to "cleared" - always wins over the
    baked-in default; the default only applies when no override has ever
    been set at all (see DEFAULT_CALIBRATION_PATH above)."""
    raw = get_setting(CALIBRATION_KEY)
    if raw is None:
        return _load_default_calibration()
    return json.loads(raw)


def set_calibration(points: list[Point]) -> dict[str, Any]:
    transform = compute_affine(points)  # raises ValueError if degenerate
    data = {"points": points, "transform": transform}
    set_setting(CALIBRATION_KEY, json.dumps(data))
    return data


def clear_calibration() -> None:
    set_setting(CALIBRATION_KEY, json.dumps({"points": [], "transform": None}))
