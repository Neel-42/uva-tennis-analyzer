"""Aggregate many matches into one comprehensive player report.

Mirrors the Dylan hard-court analysis approach: per-match estimates are weighted
by estimated point totals, then summed into career-level deuce/ad splits.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from lib.college_matches import is_college_tournament
from lib.pie_charts import (
    _parse_score_games,
    _side_rates,
    estimate_points_won_pct,
    estimate_total_points,
)
from lib.tennis_abstract import MatchRow, PlayerProfile

SURFACE_GROUPS = {
    "hard": ("hard",),
    "clay": ("clay",),
    "grass": ("grass",),
    "indoor": ("carpet", "indoor"),
}

FEATURED_LIMIT = 6


def _surface_key(surface: str) -> str:
    s = (surface or "").lower()
    for key, needles in SURFACE_GROUPS.items():
        if any(n in s for n in needles):
            return key
    return "other"


def _parse_date(date_str: str) -> datetime:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.min


def _weighted_avg(pairs: list[tuple[float, float]]) -> float | None:
    """pairs = [(value, weight)]"""
    usable = [(v, w) for v, w in pairs if v is not None and w > 0]
    if not usable:
        return None
    total_w = sum(w for _, w in usable)
    return sum(v * w for v, w in usable) / total_w


def _pie_cell(title: str, pct: float | None, total: int, caption: str, highlight: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "pct": int(round(max(0, min(100, pct or 0)))),
        "total": int(total),
        "caption": caption,
        "highlight": highlight,
    }


class _Totals:
    def __init__(self) -> None:
        self.serve_deuce_pts = 0.0
        self.serve_deuce_won = 0.0
        self.serve_ad_pts = 0.0
        self.serve_ad_won = 0.0
        self.serve_deuce_t = 0.0
        self.serve_ad_t = 0.0
        self.return_deuce_pts = 0.0
        self.return_deuce_won = 0.0
        self.return_ad_pts = 0.0
        self.return_ad_won = 0.0
        self.all_pts = 0.0
        self.all_won = 0.0


def _accumulate(match: MatchRow, totals: _Totals) -> None:
    total_pts = estimate_total_points(match.score)
    pct, _ = estimate_points_won_pct(match)
    rates = _side_rates(match)

    serve_pts = total_pts / 2
    return_pts = total_pts - serve_pts
    sd, sa = serve_pts / 2, serve_pts / 2
    rd, ra = return_pts / 2, return_pts / 2

    totals.all_pts += total_pts
    totals.all_won += total_pts * pct / 100

    totals.serve_deuce_pts += sd
    totals.serve_ad_pts += sa
    totals.serve_deuce_won += sd * rates["serveDeucePct"] / 100
    totals.serve_ad_won += sa * rates["serveAdPct"] / 100
    totals.serve_deuce_t += sd * rates["deuceTServePct"] / 100
    totals.serve_ad_t += sa * rates["adTServePct"] / 100

    totals.return_deuce_pts += rd
    totals.return_ad_pts += ra
    totals.return_deuce_won += rd * rates["returnDeucePct"] / 100
    totals.return_ad_won += ra * rates["returnAdPct"] / 100


def _pct(won: float, total: float) -> float | None:
    return (won / total * 100) if total > 0 else None


def _featured_matches(matches: list[MatchRow]) -> list[dict[str, Any]]:
    """Highest-signal matches: college/NCAA first, then best point shares."""

    def score(m: MatchRow) -> tuple[int, int, float]:
        college = 1 if (is_college_tournament(m.tournament) or "-college-" in m.id) else 0
        win = 1 if m.result == "W" else 0
        pct, _ = estimate_points_won_pct(m)
        return (college, win, pct)

    ranked = sorted(matches, key=score, reverse=True)[:FEATURED_LIMIT]
    ranked.sort(key=lambda m: _parse_date(m.date), reverse=True)

    out = []
    for m in ranked:
        pct, source = estimate_points_won_pct(m)
        out.append(
            {
                "id": m.id,
                "date": m.date,
                "tournament": m.tournament,
                "round": m.round,
                "surface": m.surface,
                "opponent": m.opponent,
                "opponentRank": m.opponent_rank,
                "result": m.result,
                "score": m.score,
                "pointsWonPct": pct,
                "totalPoints": estimate_total_points(m.score),
                "source": source,
                "isCollege": bool(is_college_tournament(m.tournament) or "-college-" in m.id),
            }
        )
    return out


def _build_notes(
    profile: PlayerProfile,
    matches: list[MatchRow],
    averages: dict[str, float | None],
    serve_deuce: float | None,
    serve_ad: float | None,
    return_deuce: float | None,
    return_ad: float | None,
) -> tuple[list[str], list[str], list[str]]:
    notes: list[str] = []
    strengths: list[str] = []
    development: list[str] = []

    wins = sum(1 for m in matches if m.result == "W")
    losses = len(matches) - wins
    first = profile.full_name.split()[0]

    notes.append(
        f"{len(matches)} matches in this sample: {wins}-{losses} record "
        f"({wins / len(matches) * 100:.0f}% win rate)."
    )

    if serve_ad is not None and serve_deuce is not None:
        gap = serve_ad - serve_deuce
        side = "ad" if gap >= 0 else "deuce"
        notes.append(
            f"Serving is stronger on the {side} side "
            f"({max(serve_ad, serve_deuce):.0f}% vs {min(serve_ad, serve_deuce):.0f}% points won) — "
            f"a {abs(gap):.0f}-point spread across the sample."
        )
        if abs(gap) >= 8:
            strengths.append(
                f"Reliable {side}-side serving pattern to lean on in tight games (break points, game points)."
            )

    if return_ad is not None and return_deuce is not None:
        best = "ad" if return_ad >= return_deuce else "deuce"
        notes.append(
            f"Returning is marginally better on the {best} side "
            f"({max(return_ad, return_deuce):.0f}% vs {min(return_ad, return_deuce):.0f}%)."
        )

    ace = averages.get("acePct")
    if ace is not None:
        if ace >= 12:
            strengths.append(f"Ace rate averages {ace:.1f}% — first-strike serving is a genuine weapon.")
        elif ace <= 6:
            development.append(
                f"Ace rate averages {ace:.1f}% — free points are rare, so rally tolerance carries the load."
            )

    df = averages.get("dfPct")
    if df is not None:
        if df >= 7:
            development.append(f"Double faults average {df:.1f}% — tighten second-serve targets under pressure.")
        elif df <= 3:
            strengths.append(f"Double fault rate of {df:.1f}% shows dependable second-serve mechanics.")

    fs_won = averages.get("firstServeWonPct")
    if fs_won is not None:
        if fs_won >= 74:
            strengths.append(f"Wins {fs_won:.0f}% of first-serve points across the sample.")
        else:
            development.append(
                f"First-serve points won sits at {fs_won:.0f}% — add pace or better placement on the first ball."
            )

    ss_won = averages.get("secondServeWonPct")
    if ss_won is not None and ss_won < 48:
        development.append(
            f"Second-serve points won is {ss_won:.0f}% — opponents are stepping in on the second delivery."
        )

    deciders = [m for m in matches if len(m.score.split()) >= 3]
    if deciders:
        d_wins = sum(1 for m in deciders if m.result == "W")
        notes.append(
            f"{first} is {d_wins}-{len(deciders) - d_wins} in matches that went the distance "
            f"({len(deciders)} three-setters in this sample)."
        )
        if d_wins / len(deciders) >= 0.65:
            strengths.append("Strong closing record in three-set matches — holds up physically and mentally.")

    college = [m for m in matches if is_college_tournament(m.tournament) or "-college-" in m.id]
    if college:
        c_wins = sum(1 for m in college if m.result == "W")
        notes.append(
            f"College play (duals, ITA, NCAA): {c_wins}-{len(college) - c_wins} across {len(college)} matches."
        )

    return notes, strengths, development


def _insight(kind: str, priority: float, short: str, text: str) -> dict[str, Any]:
    return {"kind": kind, "priority": priority, "short": short, "text": text}


def _build_scouting(
    pool: list[MatchRow],
    averages: dict[str, float | None],
    serve_deuce: float | None,
    serve_ad: float | None,
    return_deuce: float | None,
    return_ad: float | None,
    overall_pct: float,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Rank the biggest strengths and weaknesses, keeping a mix of both."""
    cand: list[dict[str, Any]] = []

    # The deuce/ad spread comes from charted reference rates, so it is a modeled
    # tendency rather than a measured edge. Rank it below real box-score stats and
    # never restate it as a paired weakness.
    if serve_deuce is not None and serve_ad is not None:
        gap = serve_ad - serve_deuce
        strong = "ad" if gap >= 0 else "deuce"
        weak = "deuce" if gap >= 0 else "ad"
        if abs(gap) >= 6:
            cand.append(
                _insight(
                    "strength",
                    2.5,
                    f"{strong.capitalize()}-side serve (modeled)",
                    f"The model leans on the {strong} court "
                    f"({max(serve_ad, serve_deuce):.0f}% of serve points won vs {min(serve_ad, serve_deuce):.0f}% on the {weak} side), "
                    "though this split follows charted reference rates rather than tracked data for this player.",
                )
            )

    df = averages.get("dfPct")
    if df is not None:
        if df >= 7:
            cand.append(
                _insight(
                    "weakness",
                    df,
                    f"Double faults {df:.1f}%",
                    f"Double faults average {df:.1f}% of service points — free points handed over, usually under pressure.",
                )
            )
        elif df <= 3:
            cand.append(
                _insight(
                    "strength",
                    8 - df,
                    f"Low double faults ({df:.1f}%)",
                    f"Second-serve mechanics hold up: just {df:.1f}% double faults across the sample.",
                )
            )

    ace = averages.get("acePct")
    if ace is not None:
        if ace >= 11:
            cand.append(
                _insight(
                    "strength",
                    ace,
                    f"Ace rate {ace:.1f}%",
                    f"Genuine first-strike weapon — {ace:.1f}% of service points end in an ace.",
                )
            )
        elif ace <= 5:
            cand.append(
                _insight(
                    "weakness",
                    7 - ace,
                    f"Few free points ({ace:.1f}% aces)",
                    f"Only {ace:.1f}% of serves are aces, so almost every service point has to be won in the rally.",
                )
            )

    fs_won = averages.get("firstServeWonPct")
    if fs_won is not None:
        if fs_won >= 74:
            cand.append(
                _insight(
                    "strength",
                    fs_won - 60,
                    f"1st serve won {fs_won:.0f}%",
                    f"Wins {fs_won:.0f}% of first-serve points — the first ball reliably sets up the point.",
                )
            )
        elif fs_won < 64:
            cand.append(
                _insight(
                    "weakness",
                    70 - fs_won,
                    f"1st serve won only {fs_won:.0f}%",
                    f"Just {fs_won:.0f}% of first-serve points are won — the first ball is not doing enough damage.",
                )
            )

    ss_won = averages.get("secondServeWonPct")
    if ss_won is not None:
        if ss_won < 48:
            cand.append(
                _insight(
                    "weakness",
                    52 - ss_won,
                    f"2nd serve won {ss_won:.0f}%",
                    f"Second-serve points won sits at {ss_won:.0f}% — opponents step in and attack the second delivery.",
                )
            )
        elif ss_won >= 55:
            cand.append(
                _insight(
                    "strength",
                    ss_won - 45,
                    f"2nd serve won {ss_won:.0f}%",
                    f"Holds {ss_won:.0f}% of second-serve points, so a missed first serve is not a lost point.",
                )
            )

    fs_in = averages.get("firstServeInPct")
    if fs_in is not None and fs_in < 58:
        cand.append(
            _insight(
                "weakness",
                62 - fs_in,
                f"1st serve in {fs_in:.0f}%",
                f"Lands only {fs_in:.0f}% of first serves, which means living on the second ball too often.",
            )
        )

    dr = averages.get("dominanceRatio")
    if dr is not None:
        if dr >= 1.15:
            cand.append(
                _insight(
                    "strength",
                    (dr - 1) * 25,
                    f"Return pressure (DR {dr:.2f})",
                    f"Dominance ratio of {dr:.2f} means return games create more damage than opponents manage in reply.",
                )
            )
        elif dr <= 0.95:
            cand.append(
                _insight(
                    "weakness",
                    (1 - dr) * 25 + 4,
                    f"Return pressure light (DR {dr:.2f})",
                    f"Dominance ratio of {dr:.2f} — struggles to hurt opponents on return, so holds have to carry every match.",
                )
            )

    if return_deuce is not None and return_ad is not None:
        r_gap = abs(return_ad - return_deuce)
        if r_gap >= 5:
            best = "ad" if return_ad >= return_deuce else "deuce"
            cand.append(
                _insight(
                    "strength",
                    2.0,
                    f"{best.capitalize()}-side return edge (modeled)",
                    f"Returns modeled slightly better from the {best} court "
                    f"({max(return_ad, return_deuce):.0f}% vs {min(return_ad, return_deuce):.0f}%).",
                )
            )

    deciders = [m for m in pool if len(m.score.split()) >= 3]
    if len(deciders) >= 4:
        d_wins = sum(1 for m in deciders if m.result == "W")
        rate = d_wins / len(deciders)
        if rate >= 0.65:
            cand.append(
                _insight(
                    "strength",
                    rate * 14,
                    f"Closes tight matches ({d_wins}-{len(deciders) - d_wins})",
                    f"{d_wins}-{len(deciders) - d_wins} in three-setters — holds up physically and mentally in long matches.",
                )
            )
        elif rate <= 0.42:
            cand.append(
                _insight(
                    "weakness",
                    (1 - rate) * 14,
                    f"Fades late ({d_wins}-{len(deciders) - d_wins} in 3 sets)",
                    f"Only {d_wins}-{len(deciders) - d_wins} in matches that went the distance — closing out is the clear gap.",
                )
            )

    if len(pool) >= 5:
        wins = sum(1 for m in pool if m.result == "W")
        win_rate = wins / len(pool) * 100
        if win_rate >= 70:
            cand.append(
                _insight(
                    "strength",
                    (win_rate - 55) * 0.5,
                    f"{wins}-{len(pool) - wins} record",
                    f"Winning {win_rate:.0f}% of matches in this sample ({wins}-{len(pool) - wins}).",
                )
            )
        elif win_rate <= 45:
            cand.append(
                _insight(
                    "weakness",
                    (60 - win_rate) * 0.5,
                    f"{wins}-{len(pool) - wins} record",
                    f"Winning only {win_rate:.0f}% of matches ({wins}-{len(pool) - wins}) — results are not yet matching the level.",
                )
            )

    quality = [
        m
        for m in pool
        if m.result == "W"
        and m.opponent_rank
        and m.player_rank
        and m.opponent_rank < m.player_rank
    ]
    if len(quality) >= 2:
        best = min(quality, key=lambda m: m.opponent_rank or 9999)
        cand.append(
            _insight(
                "strength",
                6 + len(quality) * 0.4,
                f"{len(quality)} wins over higher-ranked opponents",
                f"Beat {len(quality)} better-ranked opponents in this sample, best of them #{best.opponent_rank} "
                f"({best.opponent} at {best.tournament}) — the level travels up.",
            )
        )

    if overall_pct >= 53:
        cand.append(
            _insight(
                "strength",
                (overall_pct - 50) * 2,
                f"Wins {overall_pct:.0f}% of points",
                f"Takes {overall_pct:.0f}% of all points played, a margin that usually converts to comfortable wins.",
            )
        )
    elif overall_pct <= 49:
        cand.append(
            _insight(
                "weakness",
                (51 - overall_pct) * 2,
                f"Wins only {overall_pct:.0f}% of points",
                f"Wins {overall_pct:.0f}% of total points — matches are being decided on thin margins rather than control.",
            )
        )

    cand.sort(key=lambda c: c["priority"], reverse=True)
    strengths = [c for c in cand if c["kind"] == "strength"]
    weaknesses = [c for c in cand if c["kind"] == "weakness"]

    # A report with no weaknesses is not useful to a coach, so when nothing trips a
    # threshold, name the softest measured number instead of inventing a flaw.
    if not weaknesses:
        benchmarks = [
            ("acePct", averages.get("acePct"), 10.0, 1, "ace rate", "%"),
            ("dfPct", averages.get("dfPct"), 4.0, -1, "double fault rate", "%"),
            ("firstServeInPct", averages.get("firstServeInPct"), 63.0, 1, "first-serve percentage", "%"),
            ("firstServeWonPct", averages.get("firstServeWonPct"), 74.0, 1, "first-serve points won", "%"),
            ("secondServeWonPct", averages.get("secondServeWonPct"), 52.0, 1, "second-serve points won", "%"),
        ]
        gaps = [
            ((bench - val) / bench * direction, label, val, unit)
            for _, val, bench, direction, label, unit in benchmarks
            if val is not None
        ]
        gaps.sort(reverse=True)
        if gaps and gaps[0][0] > 0:
            _, label, val, unit = gaps[0]
            weaknesses.append(
                _insight(
                    "weakness",
                    1.0,
                    f"Softest area: {label} ({val:.1f}{unit})",
                    f"Nothing here reads as a real flaw — the most improvable number is the {label} "
                    f"at {val:.1f}{unit}.",
                )
            )

    if len(pool) < 5:
        cand.append(
            _insight(
                "note",
                0.5,
                f"Small sample ({len(pool)} matches)",
                f"Only {len(pool)} matches in this filter, so treat every figure above as indicative rather than settled.",
            )
        )
    notes = [c for c in cand if c["kind"] == "note"]

    picked: list[dict[str, Any]] = []
    # Guarantee the report shows both sides of the ledger before filling by rank.
    if strengths:
        picked.append(strengths.pop(0))
    if weaknesses:
        picked.append(weaknesses.pop(0))
    rest = sorted(strengths + weaknesses, key=lambda c: c["priority"], reverse=True)
    picked.extend(rest[: max(0, limit - len(picked) - len(notes))])
    picked.extend(notes)
    order = {"strength": 0, "weakness": 1, "note": 2}
    picked.sort(key=lambda c: (order[c["kind"]], -c["priority"]))
    return [{k: v for k, v in c.items() if k != "priority"} for c in picked]


def scouting_highlights(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Trim a scouting report for roster tiles, keeping at least one of each kind."""
    picked: list[dict[str, Any]] = []
    for kind in ("strength", "weakness", "note"):
        first = next((i for i in items if i["kind"] == kind and i not in picked), None)
        if first:
            picked.append(first)
    for item in items:
        if len(picked) >= limit:
            break
        if item not in picked:
            picked.append(item)
    order = {"strength": 0, "weakness": 1, "note": 2}
    picked.sort(key=lambda i: order[i["kind"]])
    return picked[:limit]


def build_player_report(
    profile: PlayerProfile,
    matches: Iterable[MatchRow],
    surface: str | None = None,
) -> dict[str, Any]:
    """Comprehensive multi-match report, optionally filtered to one surface."""
    all_matches = list(matches)
    if surface and surface != "all":
        pool = [m for m in all_matches if _surface_key(m.surface) == surface]
    else:
        pool = all_matches

    first = profile.full_name.split()[0]

    if not pool:
        return {
            "player": profile.full_name,
            "surface": surface or "all",
            "matchCount": 0,
            "empty": True,
            "note": "No matches available for this surface filter.",
        }

    totals = _Totals()
    for match in pool:
        _accumulate(match, totals)

    serve_deuce = _pct(totals.serve_deuce_won, totals.serve_deuce_pts)
    serve_ad = _pct(totals.serve_ad_won, totals.serve_ad_pts)
    return_deuce = _pct(totals.return_deuce_won, totals.return_deuce_pts)
    return_ad = _pct(totals.return_ad_won, totals.return_ad_pts)
    deuce_t = _pct(totals.serve_deuce_t, totals.serve_deuce_pts)
    ad_t = _pct(totals.serve_ad_t, totals.serve_ad_pts)
    overall = _pct(totals.all_won, totals.all_pts) or 50

    weights = [(m, estimate_total_points(m.score)) for m in pool]
    averages = {
        "acePct": _weighted_avg([(m.ace_pct, w) for m, w in weights]),
        "dfPct": _weighted_avg([(m.df_pct, w) for m, w in weights]),
        "firstServeInPct": _weighted_avg([(m.first_serve_in_pct, w) for m, w in weights]),
        "firstServeWonPct": _weighted_avg([(m.first_serve_won_pct, w) for m, w in weights]),
        "secondServeWonPct": _weighted_avg([(m.second_serve_won_pct, w) for m, w in weights]),
        "dominanceRatio": _weighted_avg([(m.dominance_ratio, w) for m, w in weights]),
    }

    wins = sum(1 for m in pool if m.result == "W")
    losses = len(pool) - wins
    games_won = sum(_parse_score_games(m.score)[0] for m in pool)
    games_lost = sum(_parse_score_games(m.score)[1] for m in pool)

    dates = sorted(_parse_date(m.date) for m in pool)
    date_range = ""
    if dates and dates[0] != datetime.min:
        date_range = f"{dates[0].strftime('%b %Y')} – {dates[-1].strftime('%b %Y')}"

    surface_counts: dict[str, int] = {}
    for m in all_matches:
        key = _surface_key(m.surface)
        surface_counts[key] = surface_counts.get(key, 0) + 1

    notes, strengths, development = _build_notes(
        profile, pool, averages, serve_deuce, serve_ad, return_deuce, return_ad
    )

    detailed = sum(1 for m in pool if m.first_serve_won_pct is not None or m.ace_pct is not None)
    if detailed == 0:
        notes.append(
            "None of these matches have published box scores, so ace and serve-percentage averages are "
            "unavailable. Scoreline-derived figures (points won, games, deuce/ad splits) still cover every match."
        )
    elif detailed < len(pool):
        notes.append(
            f"Box-score serve stats (ace %, double faults, first/second serve won) are published for "
            f"{detailed} of {len(pool)} matches — averages use those matches, while the deuce/ad splits "
            "and point totals cover all of them."
        )

    serve_ad_better = (serve_ad or 0) >= (serve_deuce or 0)
    return_ad_better = (return_ad or 0) >= (return_deuce or 0)

    return {
        "player": profile.full_name,
        "playerLabel": first,
        "profile": {
            "slug": profile.slug,
            "country": profile.country,
            "rank": profile.rank,
            "peakRank": profile.peak_rank,
            "age": profile.age,
            "hand": profile.hand,
            "backhand": profile.backhand,
            "heightCm": profile.height_cm,
        },
        "surface": surface or "all",
        "surfaceCounts": surface_counts,
        "matchCount": len(pool),
        "record": {"wins": wins, "losses": losses},
        "games": {"won": games_won, "lost": games_lost},
        "dateRange": date_range,
        "note": (
            f"Aggregated across {len(pool)} matches"
            + (f" ({date_range})" if date_range else "")
            + ". Point totals are estimated from scorelines; deuce/ad splits use charted "
            "hard-court reference rates adjusted by each match's serve and return stats. "
            "Official shot coordinates are not published for most matches."
        ),
        "pointsWon": {
            "playerPct": int(round(overall)),
            "opponentPct": 100 - int(round(overall)),
            "playerLabel": first,
            "totalPoints": int(round(totals.all_pts)),
            "source": f"Weighted across {len(pool)} matches",
            "isLoss": False,
        },
        "statAverages": {k: (round(v, 1) if v is not None else None) for k, v in averages.items()},
        "statCoverage": {"detailed": detailed, "total": len(pool)},
        "scoutingReport": _build_scouting(
            pool, averages, serve_deuce, serve_ad, return_deuce, return_ad, overall
        ),
        "serve": {
            "verdict": "Ad side" if serve_ad_better else "Deuce side",
            "cells": [
                _pie_cell("Deuce court", serve_deuce, totals.serve_deuce_won, "Serve points won", not serve_ad_better),
                _pie_cell("Ad court", serve_ad, totals.serve_ad_won, "Serve points won", serve_ad_better),
                _pie_cell("Deuce — T serve", deuce_t, totals.serve_deuce_t, "T-serve share"),
                _pie_cell("Ad — T serve", ad_t, totals.serve_ad_t, "T-serve share"),
            ],
        },
        "return": {
            "verdict": "Ad side (slight edge)" if return_ad_better else "Deuce side (slight edge)",
            "cells": [
                _pie_cell("Deuce court", return_deuce, totals.return_deuce_won, "Return points won", not return_ad_better),
                _pie_cell("Ad court", return_ad, totals.return_ad_won, "Return points won", return_ad_better),
                _pie_cell("Deuce — total", return_deuce, totals.return_deuce_pts, "Return points played"),
                _pie_cell("Ad — total", return_ad, totals.return_ad_pts, "Return points played"),
            ],
        },
        "coachingNotes": notes,
        "strengths": strengths,
        "development": development,
        "featuredMatches": _featured_matches(pool),
        "matches": [
            {
                "id": m.id,
                "date": m.date,
                "tournament": m.tournament,
                "round": m.round,
                "surface": m.surface,
                "opponent": m.opponent,
                "result": m.result,
                "score": m.score,
                "isCollege": bool(is_college_tournament(m.tournament) or "-college-" in m.id),
            }
            for m in sorted(pool, key=lambda m: _parse_date(m.date), reverse=True)
        ],
    }


def build_all_surface_reports(profile: PlayerProfile, matches: Iterable[MatchRow]) -> dict[str, Any]:
    """Reports keyed by surface filter, for static hosting."""
    pool = list(matches)
    reports: dict[str, Any] = {"all": build_player_report(profile, pool, "all")}
    present = {_surface_key(m.surface) for m in pool}
    for key in ("hard", "clay", "grass", "indoor"):
        if key in present:
            reports[key] = build_player_report(profile, pool, key)
    return reports
