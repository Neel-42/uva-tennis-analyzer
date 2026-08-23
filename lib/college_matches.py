"""Supplemental college / NCAA match data merged with Tennis Abstract results.

Source data is curated from virginiasports.com player bios. Bios document
highlights, so the match lists are a cited subset of each season rather than a
complete log — hence the officialRecord metadata and the highlightsOnly flag.
Matches whose score the bio does not publish carry an empty score and are
excluded from any point-based estimate.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from lib.tennis_abstract import MatchRow, PlayerProfile

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "college_matches.json"

_COLLEGE_KEYWORDS = re.compile(
    r"NCAA|ACC|Dual|ITA|Boar|SEC|Big Ten|Columbia|Championship|Classic|Invite|Tournament|Regional",
    re.I,
)


@lru_cache(maxsize=1)
def _load_data() -> dict[str, Any]:
    if not DATA_PATH.is_file():
        return {"players": {}}
    data = json.loads(DATA_PATH.read_text())
    if "players" not in data:  # legacy {slug: [matches]} layout
        return {"players": {k: {"matches": v} for k, v in data.items() if not k.startswith("_")}}
    return data


def _player_entry(slug: str) -> dict[str, Any]:
    return _load_data().get("players", {}).get(slug, {})


def get_player_meta(slug: str) -> dict[str, Any]:
    """Official records and provenance for a player's college data."""
    entry = _player_entry(slug)
    if not entry:
        return {}
    return {
        "displayName": entry.get("displayName"),
        "collegeOnly": bool(entry.get("collegeOnly")),
        "highlightsOnly": bool(entry.get("highlightsOnly")),
        "officialRecord": entry.get("officialRecord"),
        "profile": entry.get("profile"),
        "matchCount": len(entry.get("matches", [])),
        "sourceNote": _load_data().get("_meta", {}).get("caveat"),
    }


def has_college_data(slug: str) -> bool:
    return bool(_player_entry(slug).get("matches"))


def is_college_only(slug: str) -> bool:
    return bool(_player_entry(slug).get("collegeOnly"))


def _format_ta_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d-%b-%Y")
    except ValueError:
        return iso_date


def _clean_opponent(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*", "", name).strip() or name


def college_row_to_match(slug: str, raw: dict[str, Any]) -> MatchRow:
    score = raw.get("score")
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
        score=score.replace(",", " ") if score else "",
        dominance_ratio=None,
        ace_pct=None,
        df_pct=None,
        first_serve_in_pct=None,
        first_serve_won_pct=None,
        second_serve_won_pct=None,
        bp_saved=None,
        duration=None,
    )


def get_college_matches(slug: str) -> list[MatchRow]:
    return [college_row_to_match(slug, raw) for raw in _player_entry(slug).get("matches", [])]


def college_only_profile(slug: str) -> PlayerProfile:
    """Synthesise a profile for players with no Tennis Abstract page."""
    entry = _player_entry(slug)
    profile = entry.get("profile", {})
    height = profile.get("height", "")
    height_cm = None
    if match := re.match(r"(\d+)-(\d+)", height):
        height_cm = round((int(match.group(1)) * 12 + int(match.group(2))) * 2.54)
    return PlayerProfile(
        slug=slug,
        full_name=entry.get("displayName", slug),
        country="USA",
        rank=None,
        peak_rank=None,
        age=None,
        hand="Unknown",
        backhand="",
        height_cm=height_cm,
        atp_id=None,
    )


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


def fetch_player_matches(slug: str) -> tuple[PlayerProfile, list[MatchRow]]:
    from lib.tennis_abstract import fetch_player

    college = get_college_matches(slug)
    if is_college_only(slug):
        return college_only_profile(slug), merge_matches([], college)

    profile, ta_matches = fetch_player(slug)
    return profile, merge_matches(ta_matches, college)


def is_college_tournament(name: str) -> bool:
    return bool(_COLLEGE_KEYWORDS.search(name))
