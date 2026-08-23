#!/usr/bin/env python3
"""Build docs/ for GitHub Pages — static UI plus pre-fetched roster/match data."""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

SCRAPE_ATTEMPTS = 3

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATIC_SRC = ROOT / "static"
DATA_DIR = DOCS / "data"
PLAYERS_DIR = DATA_DIR / "players"
REPORTS_DIR = DATA_DIR / "reports"

sys.path.insert(0, str(ROOT))

from lib.aggregate import build_all_surface_reports, scouting_highlights  # noqa: E402
from lib.college_matches import fetch_player_matches  # noqa: E402
from lib.tennis_abstract import match_to_dict, profile_to_dict  # noqa: E402
from lib.uva_roster import enrich_roster_player, get_uva_roster, roster_to_dict  # noqa: E402


def export_static_data() -> None:
    """Scrape roster + matches and write JSON bundles for static hosting."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    roster = get_uva_roster(refresh=True)

    # Tennis Abstract is not always reachable from CI. Anything we cannot refetch
    # falls back to the committed build so a blocked scrape never strips the site.
    previous: dict[str, list[dict]] = {}
    roster_file = DATA_DIR / "roster.json"
    if roster_file.exists():
        try:
            for player in json.loads(roster_file.read_text()).get("players", []):
                if player.get("scouting"):
                    previous[player["name"]] = player["scouting"]
        except (json.JSONDecodeError, KeyError):
            pass

    scouting: dict[str, list[dict]] = {}

    for entry in roster:
        if not entry.slug or not entry.has_data:
            continue
        for attempt in range(1, SCRAPE_ATTEMPTS + 1):
            try:
                scouting[entry.name] = export_player(entry.name)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt < SCRAPE_ATTEMPTS:
                    print(f"  retry {entry.name} ({exc})")
                    time.sleep(2 * attempt)
                else:
                    print(f"  skip {entry.name}: {exc}")

    players = roster_to_dict(roster)
    carried = 0
    for player in players:
        bullets = scouting.get(player["name"])
        if not bullets and previous.get(player["name"]):
            bullets = previous[player["name"]]
            carried += 1
        if bullets:
            player["scouting"] = bullets

    roster_payload = {
        "team": "Virginia Cavaliers Men's Tennis",
        "season": "2026-27",
        "source": "virginiasports.com",
        "players": players,
    }
    roster_file.write_text(json.dumps(roster_payload, indent=2))
    print(
        f"Wrote roster ({len(players)} players, {len(scouting)} rebuilt, "
        f"{carried} carried over from the previous build)"
    )


def export_player(name: str) -> list[dict]:
    player = enrich_roster_player(name)
    if not player or not player.slug:
        raise LookupError("no Tennis Abstract or college-data slug resolved")

    profile, matches = fetch_player_matches(player.slug)
    payload = roster_to_dict([player])[0]
    payload["profile"] = profile_to_dict(profile)
    payload["matches"] = [match_to_dict(m) for m in matches]
    (PLAYERS_DIR / f"{player.slug}.json").write_text(json.dumps(payload, indent=2))

    reports = build_all_surface_reports(profile, matches)
    (REPORTS_DIR / f"{player.slug}.json").write_text(json.dumps(reports, indent=2))
    surfaces = ", ".join(k for k in reports if k != "all")
    print(f"  player {player.slug}: {len(matches)} matches ({surfaces or 'single surface'})")
    return scouting_highlights(reports["all"].get("scoutingReport", []))


def build_html() -> None:
    """Derive the static page from the Flask template so markup can't drift."""
    html = (ROOT / "templates" / "index.html").read_text()
    html = html.replace('href="/static/', 'href="static/')
    html = html.replace('src="/static/', 'src="static/')
    html = html.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        '  <meta name="static-mode" content="1" />',
    )

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(html)
    docs_static = DOCS / "static"
    docs_static.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "app.js"):
        shutil.copy2(STATIC_SRC / name, docs_static / name)
    print(f"Built {DOCS / 'index.html'}")


def main() -> None:
    export_static_data()
    build_html()


if __name__ == "__main__":
    main()
