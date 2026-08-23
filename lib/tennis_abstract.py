"""Fetch and parse player/match data from Tennis Abstract."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE = "https://www.tennisabstract.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TennisMatchAnalyzer/1.0; coaching research)",
    "Accept": "text/html,application/javascript,*/*",
}

# Simple in-memory cache to reduce Tennis Abstract rate limiting
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_get(key: str) -> Any | None:
    import time

    item = _CACHE.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    import time

    _CACHE[key] = (time.time(), value)


def _get(url: str) -> requests.Response:
    import time

    cached = _cache_get(url)
    if cached is not None:
        return cached
    for attempt in range(3):
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        if resp.status_code == 200:
            _cache_set(url, resp)
        return resp
    return resp


@dataclass
class PlayerProfile:
    slug: str
    full_name: str
    country: str
    rank: int | None
    peak_rank: int | None
    age: int | None
    hand: str
    backhand: str
    height_cm: int | None
    atp_id: str | None


@dataclass
class MatchRow:
    id: str
    date: str
    tournament: str
    surface: str
    round: str
    player_rank: int | None
    opponent_rank: int | None
    opponent: str
    opponent_slug: str | None
    result: str  # W or L
    score: str
    dominance_ratio: float | None
    ace_pct: float | None
    df_pct: float | None
    first_serve_in_pct: float | None
    first_serve_won_pct: float | None
    second_serve_won_pct: float | None
    bp_saved: str | None
    duration: str | None


def name_to_slug(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return "".join(p[:1].upper() + p[1:].lower() for p in parts)


def slug_variants(name: str) -> list[str]:
    """Generate slug candidates for names with particles (de la, van, etc.)."""
    base = name_to_slug(name)
    variants = [base]
    parts = name.strip().split()
    if len(parts) >= 3:
        # Drop particles sometimes omitted in slugs
        compact = name_to_slug(" ".join(p for p in parts if p.lower() not in {"de", "la", "van", "der", "del"}))
        if compact not in variants:
            variants.append(compact)
        variants.append(name_to_slug(f"{parts[-2]} {parts[-1]}"))
    if len(parts) >= 2:
        variants.append(name_to_slug(f"{parts[0]} {parts[-1]}"))
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _parse_js_var(html: str, key: str) -> str | None:
    m = re.search(rf"var {key} = '([^']*)';", html)
    if m:
        return m.group(1)
    m = re.search(rf"var {key} = (\d+);", html)
    if m:
        return m.group(1)
    return None


def _parse_pct(text: str | None) -> float | None:
    if not text:
        return None
    text = text.strip().replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def _extract_player_from_match_cell(cell_html: str, player_last: str) -> tuple[str, str, str | None]:
    """Return opponent name, W/L for focus player, opponent slug."""
    soup = BeautifulSoup(cell_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    normalized = cell_html.replace(" ", "")
    won = bool(
        re.search(rf"<b>{re.escape(player_last)}</b>d\.", normalized, re.I)
        or re.search(rf"<b>{re.escape(player_last)}</b>\s*d\.", cell_html, re.I)
    )
    if " d. " in text:
        parts = text.split(" d. ", 1)
        opp_part = parts[1] if won else parts[0]
    else:
        opp_part = text

    link = soup.find("a", href=re.compile(r"player\.cgi\?p="))
    slug = None
    if link and link.get("href"):
        m = re.search(r"p=([A-Za-z]+)", link["href"])
        if m:
            slug = m.group(1)

    opp_name = re.sub(r"\[[A-Z]{3}\]$", "", opp_part).strip()
    opp_name = re.sub(r"^\([^)]+\)\s*", "", opp_name).strip()
    opp_name = re.sub(r"^\(\d+\)\s*", "", opp_name).strip()
    return opp_name, ("W" if won else "L"), slug


def fetch_player(slug: str) -> tuple[PlayerProfile, list[MatchRow]]:
    page = _get(f"{BASE}/cgi-bin/player.cgi?p={slug}")
    if page.status_code == 404:
        raise LookupError(f"Player not found: {slug}")
    page.raise_for_status()
    html = page.text

    frag = _get(f"{BASE}/jsfrags/{slug}.js")
    if frag.status_code != 200:
        raise LookupError(f"No match data for player: {slug}")
    frag.raise_for_status()

    full_name = _parse_js_var(html, "fullname") or slug
    last_name = _parse_js_var(html, "lastname") or full_name.split()[-1]
    country = _parse_js_var(html, "country") or ""
    rank = _parse_int(_parse_js_var(html, "currentrank"))
    peak = _parse_int(_parse_js_var(html, "peakrank"))
    hand = _parse_js_var(html, "hand") or "R"
    backhand = _parse_js_var(html, "backhand") or "2"
    height = _parse_int(_parse_js_var(html, "ht"))
    atp_id = _parse_js_var(html, "atp_id")

    dob = _parse_js_var(html, "dob")
    age = None
    if dob and len(dob) == 8:
        from datetime import date

        y, m, d = int(dob[:4]), int(dob[4:6]), int(dob[6:8])
        today = date.today()
        age = today.year - y - ((today.month, today.day) < (m, d))

    profile = PlayerProfile(
        slug=slug,
        full_name=full_name,
        country=country,
        rank=rank,
        peak_rank=peak,
        age=age,
        hand="Right" if hand == "R" else "Left",
        backhand="Two-handed" if backhand == "2" else "One-handed",
        height_cm=height,
        atp_id=atp_id,
    )

    frag_html = frag.text
    m = re.search(r"var player_frag = `([\s\S]*)`;", frag_html)
    if not m:
        raise LookupError("Could not parse match table")
    table_html = m.group(1)
    soup = BeautifulSoup(table_html, "html.parser")
    tbody = soup.find("tbody")
    if not tbody:
        return profile, []

    matches: list[MatchRow] = []
    for i, tr in enumerate(tbody.find_all("tr")):
        tds = tr.find_all("td")
        if len(tds) < 10:
            continue
        match_cell = str(tds[6])
        opponent, result, opp_slug = _extract_player_from_match_cell(match_cell, last_name)
        dr_text = tds[8].get_text(strip=True) if len(tds) > 8 else None
        try:
            dr = float(dr_text) if dr_text else None
        except ValueError:
            dr = None

        row = MatchRow(
            id=f"{slug}-{i}",
            date=tds[0].get_text(strip=True),
            tournament=tds[1].get_text(strip=True),
            surface=tds[2].get_text(strip=True),
            round=tds[3].get_text(strip=True),
            player_rank=_parse_int(tds[4].get_text(strip=True)),
            opponent_rank=_parse_int(tds[5].get_text(strip=True)),
            opponent=opponent,
            opponent_slug=opp_slug,
            result=result,
            score=tds[7].get_text(strip=True),
            dominance_ratio=dr,
            ace_pct=_parse_pct(tds[9].get_text(strip=True) if len(tds) > 9 else None),
            df_pct=_parse_pct(tds[10].get_text(strip=True) if len(tds) > 10 else None),
            first_serve_in_pct=_parse_pct(tds[11].get_text(strip=True) if len(tds) > 11 else None),
            first_serve_won_pct=_parse_pct(tds[12].get_text(strip=True) if len(tds) > 12 else None),
            second_serve_won_pct=_parse_pct(tds[13].get_text(strip=True) if len(tds) > 13 else None),
            bp_saved=tds[14].get_text(strip=True) if len(tds) > 14 else None,
            duration=tds[15].get_text(strip=True) if len(tds) > 15 else None,
        )
        matches.append(row)

    return profile, matches


def search_players(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Resolve player name to Tennis Abstract slugs."""
    query = query.strip()
    if len(query) < 2:
        return []

    found: list[dict[str, Any]] = []
    for slug in slug_variants(query):
        try:
            profile, _ = fetch_player(slug)
            found.append(
                {
                    "slug": profile.slug,
                    "name": profile.full_name,
                    "country": profile.country,
                    "rank": profile.rank,
                }
            )
            if len(found) >= limit:
                break
        except (LookupError, requests.RequestException):
            continue

    # Single-token last-name search: try "Carlos Alcaraz" pattern for known stars
    if not found and " " not in query and len(query) >= 4:
        common_first = ["Carlos", "Novak", "Rafael", "Roger", "Jannik", "Daniil", "Alexander", "Stefanos"]
        for first in common_first[:4]:
            try:
                profile, _ = fetch_player(name_to_slug(f"{first} {query}"))
                if query.lower() in profile.full_name.lower():
                    found.append(
                        {
                            "slug": profile.slug,
                            "name": profile.full_name,
                            "country": profile.country,
                            "rank": profile.rank,
                        }
                    )
                    break
            except (LookupError, requests.RequestException):
                continue

    # Linkifier fallback for multi-word discovery
    if not found and " " in query:
        try:
            resp = requests.post(
                f"{BASE}/cgi-bin/linkifier.cgi",
                data={"text": query},
                headers=HEADERS,
                timeout=15,
            )
            slugs = set(re.findall(r"player\.cgi\?p=([A-Za-z]+)", resp.text))
            for slug in list(slugs)[:limit]:
                try:
                    profile, _ = fetch_player(slug)
                    if query.lower() in profile.full_name.lower():
                        found.append(
                            {
                                "slug": profile.slug,
                                "name": profile.full_name,
                                "country": profile.country,
                                "rank": profile.rank,
                            }
                        )
                except (LookupError, requests.RequestException):
                    continue
        except requests.RequestException:
            pass

    return found[:limit]


def profile_to_dict(p: PlayerProfile) -> dict[str, Any]:
    return asdict(p)


def match_to_dict(m: MatchRow) -> dict[str, Any]:
    return asdict(m)
