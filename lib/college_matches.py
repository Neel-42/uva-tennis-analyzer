"""Supplemental college / NCAA match data merged with Tennis Abstract results."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.tennis_abstract import MatchRow

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "college_matches.json"

_COLLEGE_KEYWORDS = re.compile(
    r"NCAA|ACC|Dual|ITA|Boar|SEC|Big Ten|Columbia|Championship",
    re.I,
)


def _load_data() -> dict[str, list[dict[str, Any]]]:
    if not DATA_PATH.is_file():
        return {}
    return json.loads(DATA_PATH.read_text())


def _format_ta_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d-%b-%Y")
    except ValueError:
        return iso_date


def _pct_to_dr(pct: float | None) -> float | None:
    if pct is None or pct <= 0 or pct >= 100:
        return None
    return round(pct / (100 - pct), 2)


def _clean_opponent(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*", "", name).strip()


def college_row_to_match(slug: str, raw: dict[str, Any]) -> MatchRow:
    pct = raw.get("pointsWonPct")
    return MatchRow(
        id=f"{slug}-college-{raw['id']}",
        date=_format_ta_date(raw["date"]),
        tournament=raw["tournament"],
        surface=raw.get("surface", "Hard"),
        round=raw.get("round", "Match"),
        player_rank=raw.get("playerRank"),
        opponent_rank=raw.get("opponentRank"),
        opponent=_clean_opponent(raw["opponent"]),
        opponent_slug=raw.get("opponentSlug"),
        result=raw["result"],
        score=raw["score"].replace(",", " "),
        dominance_ratio=_pct_to_dr(pct),
        ace_pct=raw.get("acePct"),
        df_pct=raw.get("dfPct"),
        first_serve_in_pct=raw.get("firstServeInPct"),
        first_serve_won_pct=raw.get("firstServeWonPct"),
        second_serve_won_pct=raw.get("secondServeWonPct"),
        bp_saved=raw.get("bpSaved"),
        duration=raw.get("duration"),
    )


def get_college_matches(slug: str) -> list[MatchRow]:
    rows = []
    for raw in _load_data().get(slug, []):
        rows.append(college_row_to_match(slug, raw))
    return rows


def _parse_date_key(date_str: str) -> datetime:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.min


def merge_matches(ta_matches: list[MatchRow], college_matches: list[MatchRow]) -> list[MatchRow]:
    """College matches first, then TA; dedupe by date + opponent name."""
    seen: set[tuple[str, str]] = set()
    merged: list[MatchRow] = []

    for match in college_matches + ta_matches:
        key = (match.date, match.opponent.lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(match)

    merged.sort(key=lambda m: _parse_date_key(m.date), reverse=True)
    return merged


def fetch_player_matches(slug: str) -> tuple[Any, list[MatchRow]]:
    from lib.tennis_abstract import fetch_player

    profile, ta_matches = fetch_player(slug)
    college = get_college_matches(slug)
    return profile, merge_matches(ta_matches, college)


def is_college_tournament(name: str) -> bool:
    return bool(_COLLEGE_KEYWORDS.search(name))
