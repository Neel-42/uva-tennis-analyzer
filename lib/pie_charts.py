"""Build hard-court-style pie chart data from match statistics."""

from __future__ import annotations

import re
from typing import Any

from lib.tennis_abstract import MatchRow, PlayerProfile

POINTS_PER_GAME = 4.2

# Default deuce/ad splits when charting unavailable (from Dylan Svajda 2024 charted match).
DEFAULT_SERVE_DEUCE = 69.2
DEFAULT_SERVE_AD = 81.8
DEFAULT_RETURN_DEUCE = 41.9
DEFAULT_RETURN_AD = 44.8
DEFAULT_DEUCE_T = 29.8
DEFAULT_AD_T = 33.3


def _parse_score_games(score: str) -> tuple[int, int]:
    player, opp = 0, 0
    for a, b in re.findall(r"(\d+)-(\d+)", score):
        player += int(a)
        opp += int(b)
    return player, opp


def estimate_total_points(score: str) -> int:
    dg, og = _parse_score_games(score)
    return max(round((dg + og) * POINTS_PER_GAME), 1)


def estimate_points_won_pct(match: MatchRow) -> tuple[int, str]:
    """Return (player points won %, source label)."""
    if match.dominance_ratio is not None and match.dominance_ratio > 0:
        pct = round(match.dominance_ratio / (1 + match.dominance_ratio) * 100)
        return max(1, min(99, pct)), "Dominance ratio"

    dg, og = _parse_score_games(match.score)
    total_games = dg + og
    if total_games > 0:
        pct = round(dg / total_games * 100)
        return max(1, min(99, pct)), "Games-won estimate"

    if match.first_serve_won_pct is not None and match.second_serve_won_pct is not None:
        blended = (match.first_serve_won_pct * 0.55) + (match.second_serve_won_pct * 0.45)
        return max(1, min(99, round(blended))), "Serve stats estimate"

    return 50, "Unavailable — using 50/50"


def _side_rates(match: MatchRow) -> dict[str, float]:
    """Estimate deuce/ad win rates from match serve/return performance."""
    ace = match.ace_pct or 8
    first_won = match.first_serve_won_pct or 68
    second_won = match.second_serve_won_pct or 48

    serve_boost = (first_won - 65) * 0.15 + (ace - 8) * 0.2
    return_boost = max(-5, min(5, ((match.dominance_ratio or 1.0) - 1.0) * 8))

    serve_deuce = max(45, min(90, DEFAULT_SERVE_DEUCE + serve_boost))
    serve_ad = max(45, min(92, DEFAULT_SERVE_AD + serve_boost + 3))
    return_deuce = max(25, min(60, DEFAULT_RETURN_DEUCE + return_boost))
    return_ad = max(25, min(62, DEFAULT_RETURN_AD + return_boost + 1))

    # Wide/kick tendency: higher ace rate → more ad-side wide effectiveness
    ad_wide_boost = max(-8, min(8, (ace - 8) * 0.5))
    serve_ad = min(92, serve_ad + ad_wide_boost)

    return {
        "serveDeucePct": serve_deuce,
        "serveAdPct": serve_ad,
        "returnDeucePct": return_deuce,
        "returnAdPct": return_ad,
        "deuceTServePct": DEFAULT_DEUCE_T,
        "adTServePct": DEFAULT_AD_T + min(5, ace * 0.2),
    }


def _pie_cell(title: str, pct: float, total: int, caption: str, highlight: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "pct": int(round(max(0, min(100, pct)))),
        "total": total,
        "caption": caption,
        "highlight": highlight,
    }


def build_pie_charts(profile: PlayerProfile, match: MatchRow) -> dict[str, Any]:
    player_pct, source = estimate_points_won_pct(match)
    total_pts = estimate_total_points(match.score)
    serve_pts = total_pts // 2
    return_pts = total_pts - serve_pts

    sd_opp = serve_pts // 2
    sa_opp = serve_pts - sd_opp
    rd_opp = return_pts // 2
    ra_opp = return_pts - rd_opp

    rates = _side_rates(match)

    serve_deuce_won = round(sd_opp * rates["serveDeucePct"] / 100)
    serve_ad_won = round(sa_opp * rates["serveAdPct"] / 100)
    return_deuce_won = round(rd_opp * rates["returnDeucePct"] / 100)
    return_ad_won = round(ra_opp * rates["returnAdPct"] / 100)

    serve_deuce_t = round(sd_opp * rates["deuceTServePct"] / 100)
    serve_ad_t = round(sa_opp * rates["adTServePct"] / 100)

    serve_ad_better = rates["serveAdPct"] >= rates["serveDeucePct"]
    return_ad_better = rates["returnAdPct"] >= rates["returnDeucePct"]

    first_name = profile.full_name.split()[0]

    return {
        "modeled": True,
        "note": (
            "Pie charts modeled from match box stats (dominance ratio, serve/return %). "
            "Deuce/ad splits use charted hard-court defaults adjusted for this match. "
            "Official shot coordinates are not published for most matches."
        ),
        "pointsWon": {
            "playerPct": player_pct,
            "opponentPct": 100 - player_pct,
            "playerLabel": first_name,
            "totalPoints": total_pts,
            "source": source,
            "isLoss": match.result == "L",
        },
        "serve": {
            "verdict": "Ad side" if serve_ad_better else "Deuce side",
            "cells": [
                _pie_cell("Deuce court", rates["serveDeucePct"], serve_deuce_won, "Serve points won", not serve_ad_better),
                _pie_cell("Ad court", rates["serveAdPct"], serve_ad_won, "Serve points won", serve_ad_better),
                _pie_cell("Deuce — T serve", rates["deuceTServePct"], serve_deuce_t, "T-serve share"),
                _pie_cell("Ad — T serve", rates["adTServePct"], serve_ad_t, "T-serve share"),
            ],
        },
        "return": {
            "verdict": "Ad side (slight edge)" if return_ad_better else "Deuce side (slight edge)",
            "cells": [
                _pie_cell("Deuce court", rates["returnDeucePct"], return_deuce_won, "Return points won", not return_ad_better),
                _pie_cell("Ad court", rates["returnAdPct"], return_ad_won, "Return points won", return_ad_better),
                _pie_cell("Deuce — total", rates["returnDeucePct"], rd_opp, "Return points played"),
                _pie_cell("Ad — total", rates["returnAdPct"], ra_opp, "Return points played"),
            ],
        },
    }
