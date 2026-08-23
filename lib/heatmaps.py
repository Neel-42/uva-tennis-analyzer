"""Model court heatmaps from match-level serve/groundstroke tendencies."""

from __future__ import annotations

from typing import Any

from lib.tennis_abstract import MatchRow, PlayerProfile


def _clamp(v: float, lo: float = 20, hi: float = 95) -> int:
    return int(max(lo, min(hi, v)))


def build_heatmaps(profile: PlayerProfile, match: MatchRow) -> dict[str, Any]:
    ace = match.ace_pct or 10
    df = match.df_pct or 5
    first_in = match.first_serve_in_pct or 55
    first_won = match.first_serve_won_pct or 70
    second_won = match.second_serve_won_pct or 50
    dr = match.dominance_ratio or 1.0
    is_win = match.result == "W"

    wide_boost = _clamp(55 + ace * 1.5)
    body_boost = _clamp(40 + df * 2)
    io_boost = _clamp(60 + (10 if profile.backhand.startswith("Two") else 0) + (5 if is_win else -5))
    bh_cross = _clamp(50 + (5 if not is_win else 10))

    return {
        "modeled": True,
        "note": (
            "Modeled from match box stats + player tendencies. "
            "Official shot coordinates are not published for most Challenger/ITF matches."
        ),
        "serveLanding": [
            {"id": "d-wide", "label": "Deuce wide", "x": 0.04, "y": 0.06, "w": 0.2, "h": 0.22, "intensity": wide_boost},
            {"id": "d-body", "label": "Deuce body", "x": 0.26, "y": 0.06, "w": 0.2, "h": 0.22, "intensity": body_boost},
            {"id": "d-t", "label": "Deuce T", "x": 0.48, "y": 0.06, "w": 0.2, "h": 0.22, "intensity": _clamp(45 + first_won * 0.3)},
            {"id": "a-wide", "label": "Ad wide", "x": 0.72, "y": 0.06, "w": 0.2, "h": 0.22, "intensity": _clamp(wide_boost - 10)},
            {"id": "2d-body", "label": "2nd kick/body", "x": 0.26, "y": 0.3, "w": 0.2, "h": 0.18, "intensity": _clamp(second_won * 0.9)},
        ],
        "returnContact": [
            {"id": "rc-mid", "label": "Center baseline", "x": 0.34, "y": 0.62, "w": 0.28, "h": 0.14, "intensity": _clamp(70 + dr * 8)},
            {"id": "rc-deuce", "label": "Deep deuce", "x": 0.06, "y": 0.62, "w": 0.26, "h": 0.14, "intensity": _clamp(65 + dr * 5)},
            {"id": "rc-ad", "label": "Deep ad", "x": 0.64, "y": 0.62, "w": 0.26, "h": 0.14, "intensity": _clamp(60 + dr * 5)},
        ],
        "returnLanding": [
            {"id": "rl-cross", "label": "Crosscourt deep", "x": 0.08, "y": 0.1, "w": 0.28, "h": 0.2, "intensity": _clamp(55 + dr * 12)},
            {"id": "rl-middle", "label": "Middle", "x": 0.36, "y": 0.12, "w": 0.24, "h": 0.18, "intensity": _clamp(45 + (10 if not is_win else 0))},
            {"id": "rl-dtl", "label": "Down the line", "x": 0.62, "y": 0.1, "w": 0.26, "h": 0.2, "intensity": _clamp(40 + ace * 0.5)},
        ],
        "forehandLanding": [
            {"id": "fh-io", "label": "Inside-out ad", "x": 0.62, "y": 0.08, "w": 0.3, "h": 0.24, "intensity": io_boost},
            {"id": "fh-cross", "label": "Crosscourt", "x": 0.06, "y": 0.1, "w": 0.3, "h": 0.22, "intensity": _clamp(io_boost - 12)},
            {"id": "fh-middle", "label": "Middle", "x": 0.36, "y": 0.14, "w": 0.24, "h": 0.18, "intensity": _clamp(40 + first_in * 0.2)},
        ],
        "backhandLanding": [
            {"id": "bh-cross", "label": "Crosscourt", "x": 0.58, "y": 0.1, "w": 0.3, "h": 0.22, "intensity": bh_cross},
            {"id": "bh-middle", "label": "Safe middle", "x": 0.34, "y": 0.14, "w": 0.22, "h": 0.18, "intensity": _clamp(bh_cross - 8)},
            {"id": "bh-slice", "label": "Slice/chip", "x": 0.52, "y": 0.34, "w": 0.28, "h": 0.14, "intensity": _clamp(35 + (8 if match.surface == "Clay" else 0))},
        ],
    }
