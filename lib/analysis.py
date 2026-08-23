"""Generate coaching analysis from match statistics."""

from __future__ import annotations

from typing import Any

from lib.college_matches import is_college_tournament


def _parse_sets(score: str) -> list[tuple[int, int]]:
    sets: list[tuple[int, int]] = []
    for part in score.split():
        if "-" not in part:
            continue
        left, _, right = part.partition("-")
        left = left.split("(")[0]
        right = right.split("(")[0]
        try:
            sets.append((int(left), int(right)))
        except ValueError:
            continue
    return sets


def _pct_label(v: float | None) -> str:
    return f"{v:.1f}%" if v is not None else "—"


def build_match_analysis(profile: PlayerProfile, match: MatchRow) -> dict[str, Any]:
    sets = _parse_sets(match.score)
    sets_won = sum(1 for a, b in sets if a > b)
    sets_lost = sum(1 for a, b in sets if a < b)
    is_win = match.result == "W"

    coaching: list[str] = []
    key_moments: list[str] = []

    if match.ace_pct is not None:
        if match.ace_pct >= 15:
            coaching.append(
                f"Ace rate {_pct_label(match.ace_pct)} — power serving was a major weapon in this match."
            )
        elif match.ace_pct <= 5:
            coaching.append(
                f"Low ace rate {_pct_label(match.ace_pct)} — won primarily through rally tolerance and placement."
            )

    if match.df_pct is not None:
        if match.df_pct >= 10:
            coaching.append(
                f"Double fault rate {_pct_label(match.df_pct)} is elevated — free points donated under pressure."
            )
        elif match.df_pct <= 2:
            coaching.append(
                f"Excellent double fault control ({_pct_label(match.df_pct)}) — reliable second serve patterns."
            )

    if match.first_serve_won_pct is not None and match.first_serve_in_pct is not None:
        coaching.append(
            f"First serve: { _pct_label(match.first_serve_in_pct)} in, "
            f"{_pct_label(match.first_serve_won_pct)} won — "
            + (
                "elite efficiency when the first ball goes in."
                if (match.first_serve_won_pct or 0) >= 75
                else "room to improve first-serve damage or consistency."
            )
        )

    if match.second_serve_won_pct is not None:
        coaching.append(
            f"Second serve points won: {_pct_label(match.second_serve_won_pct)} — "
            + (
                "strong kick/body patterns protected the service games."
                if (match.second_serve_won_pct or 0) >= 55
                else "second serve became attackable; opponent gained return momentum."
            )
        )

    if match.dominance_ratio is not None:
        coaching.append(
            f"Dominance ratio {match.dominance_ratio:.2f} "
            + ("(controlled more of the match)" if match.dominance_ratio >= 1.0 else "(outplayed on key points)")
        )

    if match.opponent_rank and profile.rank:
        diff = match.opponent_rank - profile.rank
        if is_win and diff < -50:
            coaching.append(
                f"Quality win vs #{match.opponent_rank} while ranked #{profile.rank} — beat a higher-ranked opponent."
            )
        if not is_win and diff > 50:
            coaching.append(
                f"Lost to lower-ranked #{match.opponent_rank} — investigate execution dip vs expectation."
            )

    if sets:
        if len(sets) >= 3 and not is_win and sets[1][0] < sets[1][1]:
            key_moments.append(
                f"Middle set lost {sets[1][0]}-{sets[1][1]} — review momentum shift after Set 1."
            )
        if is_win and len(sets) >= 3 and sets[1][0] < sets[1][1]:
            key_moments.append(
                f"Bounced back after dropping Set 2 ({sets[1][0]}-{sets[1][1]}) to win the decider {sets[2][0]}-{sets[2][1]}."
            )
        key_moments.append(f"Final scoreline: {match.score} ({sets_won}-{sets_lost} in sets).")

    if match.bp_saved:
        key_moments.append(f"Break points saved: {match.bp_saved}.")

    tactical = (
        f"{'Victory' if is_win else 'Loss'} on {match.surface.lower()} vs {match.opponent} "
        f"({match.round}, {match.tournament}). "
    )
    if match.ace_pct and match.ace_pct >= 12:
        tactical += "Match shaped by first-strike serving and early point control."
    elif match.dominance_ratio and match.dominance_ratio >= 1.2:
        tactical += "Return pressure and baseline consistency drove the outcome."
    else:
        tactical += "Outcome likely decided by serve reliability and break-point conversion."

    strengths: list[str] = []
    development: list[str] = []

    if is_win:
        if (match.first_serve_won_pct or 0) >= 78:
            strengths.append("First-serve points won rate was elite.")
        if (match.second_serve_won_pct or 0) >= 55:
            strengths.append("Second serve held up under pressure.")
        if (match.dominance_ratio or 0) >= 1.2:
            strengths.append("Dominance ratio shows control of rally equity.")
    else:
        if (match.df_pct or 0) >= 8:
            development.append("Cut double faults — too many free points given away.")
        if (match.first_serve_in_pct or 0) < 55:
            development.append("Raise first-serve percentage without sacrificing pace.")
        if (match.second_serve_won_pct or 0) < 45:
            development.append("Rebuild second-serve patterns (kick wide/body) when behind in games.")

    return {
        "player": profile.full_name,
        "opponent": match.opponent,
        "tournament": match.tournament,
        "surface": match.surface,
        "round": match.round,
        "date": match.date,
        "score": match.score,
        "result": match.result,
        "sets": [{"player": a, "opponent": b} for a, b in sets],
        "stats": {
            "dominanceRatio": match.dominance_ratio,
            "acePct": match.ace_pct,
            "dfPct": match.df_pct,
            "firstServeInPct": match.first_serve_in_pct,
            "firstServeWonPct": match.first_serve_won_pct,
            "secondServeWonPct": match.second_serve_won_pct,
            "bpSaved": match.bp_saved,
            "duration": match.duration,
            "playerRank": match.player_rank,
            "opponentRank": match.opponent_rank,
        },
        "coachingNotes": coaching,
        "keyMoments": key_moments,
        "tacticalProfile": tactical,
        "strengths": strengths,
        "development": development,
        "source": "College match + UVA data"
        if is_college_tournament(match.tournament) or "-college-" in match.id
        else "Tennis Abstract",
    }
