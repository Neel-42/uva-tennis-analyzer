"""Fetch and resolve the current UVA men's tennis roster."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup

from lib.college_matches import has_college_data, is_college_only
from lib.tennis_abstract import HEADERS, fetch_player, slug_variants

ROSTER_URL = "https://virginiasports.com/sports/mten/roster"
CACHE_TTL = 3600

# Pre-mapped Tennis Abstract slugs for the current UVA roster.
# Updated when roster changes; auto-resolution fills gaps on first player load.
ROSTER_SLUGS: dict[str, str] = {
    "Stiles Brockett": "StilesBrockett",
    "Dylan Dietrich": "DylanDietrich",
    "Roy Horovitz": "RoyHorovitz",
    "Jack Kennedy": "JackKennedy",
    "Jangjun Kim": "JangjunKim",
    "Luca Preda": "LucaPreda",
    "Keegan Rice": "KeeganRice",
    "Andres Santamarta Roig": "AndresSantamartaRoig",
    "Andres Santamarta Roig": "AndresSantamartaRoig",
}

# Players with no data from any source. Anyone with curated college results in
# data/college_matches.json is covered even without a Tennis Abstract page.
NO_MATCH_DATA: set[str] = set()

_roster_cache: tuple[float, list["RosterPlayer"]] | None = None


@dataclass
class RosterPlayer:
    name: str
    class_year: str
    hometown: str
    slug: str | None
    has_data: bool
    rank: int | None = None
    country: str | None = None
    match_count: int = 0
    college_only: bool = False


def _normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", name.strip())


def _canonical_key(name: str) -> str:
    return _normalize_name(name).lower()


def _parse_class_year(text: str) -> str:
    mapping = {
        "1st Year": "Freshman",
        "2nd Year": "Sophomore",
        "3rd Year": "Junior",
        "4th Year": "Senior",
        "5th Year": "Graduate Student",
    }
    text = text.strip()
    for key, label in mapping.items():
        if key in text:
            return label
    return text


def fetch_roster_html() -> str:
    resp = requests.get(ROSTER_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_roster(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    players: list[dict[str, str]] = []

    for item in soup.select(".roster-card-item"):
        link = item.select_one('a[href*="/roster/player/"]')
        if not link:
            continue

        name_el = item.select_one(".roster-card-item__title-link") or item.select_one("h3")
        if not name_el:
            continue
        name = _normalize_name(name_el.get_text(strip=True))
        if not name:
            continue

        values = [
            v.get_text(strip=True)
            for v in item.select(".roster-player-card-profile-field__value")
            if v.get_text(strip=True)
        ]

        class_year = ""
        hometown = ""
        for value in values:
            if re.search(r"(Year|Freshman|Sophomore|Junior|Senior|Graduate)", value):
                class_year = _parse_class_year(value)
            elif "," in value or value.endswith("Switzerland") or value.endswith("Canada"):
                hometown = value
            elif not class_year and re.fullmatch(r"\d+′?\d*″?", value):
                continue
            elif not hometown and len(value) > 3 and not class_year:
                hometown = value

        players.append({"name": name, "class_year": class_year, "hometown": hometown})

    return players


def _is_no_match_data(name: str) -> bool:
    key = _canonical_key(name)
    return any(_canonical_key(n) == key for n in NO_MATCH_DATA)


def lookup_slug(name: str) -> str | None:
    key = _canonical_key(name)
    for roster_name, slug in ROSTER_SLUGS.items():
        if _canonical_key(roster_name) == key:
            return slug
    for slug in slug_variants(name):
        return slug
    return None


def _names_match(roster_name: str, ta_name: str) -> bool:
    roster_parts = _normalize_name(roster_name).lower().split()
    ta_parts = _normalize_name(ta_name).lower().split()
    if not roster_parts or not ta_parts:
        return False
    if roster_parts[-1] != ta_parts[-1]:
        return False
    return roster_parts[0] == ta_parts[0] or roster_parts[0][0] == ta_parts[0][0]


def resolve_player_slug(name: str) -> tuple[str | None, bool, dict[str, Any]]:
    """Resolve slug and verify Tennis Abstract has match data."""
    candidates: list[str] = []
    mapped = lookup_slug(name)
    if mapped:
        candidates.append(mapped)
    candidates.extend(slug_variants(name))

    seen: set[str] = set()
    for slug in candidates:
        if slug in seen:
            continue
        seen.add(slug)
        try:
            profile, matches = fetch_player(slug)
            if _names_match(name, profile.full_name):
                ROSTER_SLUGS[name] = profile.slug
                return (
                    profile.slug,
                    bool(matches),
                    {
                        "rank": profile.rank,
                        "country": profile.country,
                        "match_count": len(matches),
                    },
                )
        except Exception:
            continue

    try:
        resp = requests.post(
            "https://www.tennisabstract.com/cgi-bin/linkifier.cgi",
            data={"text": name},
            headers=HEADERS,
            timeout=15,
        )
        for slug in re.findall(r"player\.cgi\?p=([A-Za-z]+)", resp.text)[:6]:
            if slug in seen:
                continue
            try:
                profile, matches = fetch_player(slug)
                if _names_match(name, profile.full_name):
                    ROSTER_SLUGS[name] = profile.slug
                    return (
                        profile.slug,
                        bool(matches),
                        {
                            "rank": profile.rank,
                            "country": profile.country,
                            "match_count": len(matches),
                        },
                    )
            except Exception:
                continue
    except requests.RequestException:
        pass

    return None, False, {}


def get_uva_roster(refresh: bool = False) -> list[RosterPlayer]:
    global _roster_cache

    if not refresh and _roster_cache:
        ts, cached = _roster_cache
        if time.time() - ts < CACHE_TTL:
            return cached

    html = fetch_roster_html()
    raw = parse_roster(html)
    roster: list[RosterPlayer] = []

    for entry in raw:
        slug = lookup_slug(entry["name"])
        college = bool(slug) and has_college_data(slug)
        has_data = bool(slug) and (college or not _is_no_match_data(entry["name"]))
        roster.append(
            RosterPlayer(
                name=entry["name"],
                class_year=entry.get("class_year", ""),
                hometown=entry.get("hometown", ""),
                slug=slug,
                has_data=has_data,
                rank=None,
                country=None,
                match_count=0,
                college_only=bool(slug) and is_college_only(slug),
            )
        )

    roster.sort(key=lambda p: p.name)
    _roster_cache = (time.time(), roster)
    return roster


def enrich_roster_player(name: str) -> RosterPlayer | None:
    roster = get_uva_roster()
    entry = next((p for p in roster if _canonical_key(p.name) == _canonical_key(name)), None)
    if not entry:
        return None
    slug, has_data, meta = resolve_player_slug(entry.name)
    if _is_no_match_data(entry.name):
        has_data = False

    # College-only players have no Tennis Abstract page, so fall back to the
    # curated results keyed off the roster-derived slug.
    fallback_slug = slug or lookup_slug(entry.name)
    if not has_data and fallback_slug and has_college_data(fallback_slug):
        slug, has_data = fallback_slug, True

    return RosterPlayer(
        name=entry.name,
        class_year=entry.class_year,
        hometown=entry.hometown,
        slug=slug,
        has_data=has_data,
        rank=meta.get("rank"),
        country=meta.get("country"),
        match_count=meta.get("match_count", 0),
        college_only=bool(slug) and is_college_only(slug),
    )


def roster_to_dict(players: list[RosterPlayer]) -> list[dict[str, Any]]:
    return [asdict(p) for p in players]
