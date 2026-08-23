#!/usr/bin/env python3
"""Build docs/ for GitHub Pages — static UI plus pre-fetched roster/match data."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATIC_SRC = ROOT / "static"
DATA_DIR = DOCS / "data"
PLAYERS_DIR = DATA_DIR / "players"
ANALYSES_DIR = DATA_DIR / "analyses"

sys.path.insert(0, str(ROOT))

from lib.analysis import build_match_analysis  # noqa: E402
from lib.pie_charts import build_pie_charts  # noqa: E402
from lib.college_matches import fetch_player_matches
from lib.tennis_abstract import match_to_dict, profile_to_dict  # noqa: E402
from lib.uva_roster import enrich_roster_player, get_uva_roster, roster_to_dict  # noqa: E402


def export_static_data() -> None:
    """Scrape roster + matches and write JSON bundles for static hosting."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

    roster = get_uva_roster(refresh=True)
    roster_payload = {
        "team": "Virginia Cavaliers Men's Tennis",
        "season": "2026-27",
        "source": "virginiasports.com",
        "players": roster_to_dict(roster),
    }
    (DATA_DIR / "roster.json").write_text(json.dumps(roster_payload, indent=2))
    print(f"Wrote roster ({len(roster_payload['players'])} players)")

    for entry in roster:
        if not entry.slug or not entry.has_data:
            continue
        try:
            player = enrich_roster_player(entry.name)
            if not player or not player.slug:
                continue
            profile, matches = fetch_player_matches(player.slug)
            payload = roster_to_dict([player])[0]
            payload["profile"] = profile_to_dict(profile)
            payload["matches"] = [match_to_dict(m) for m in matches]
            slug_path = PLAYERS_DIR / f"{player.slug}.json"
            slug_path.write_text(json.dumps(payload, indent=2))
            print(f"  player {player.slug}: {len(matches)} matches")

            slug_analysis_dir = ANALYSES_DIR / player.slug
            slug_analysis_dir.mkdir(parents=True, exist_ok=True)
            for match in matches:
                analysis = build_match_analysis(profile, match)
                analysis["pieCharts"] = build_pie_charts(profile, match)
                analysis["profile"] = profile_to_dict(profile)
                (slug_analysis_dir / f"{match.id}.json").write_text(json.dumps(analysis, indent=2))
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {entry.name}: {exc}")


def build_html() -> None:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="static-mode" content="1" />
  <title>UVA Tennis Match Analyzer</title>
  <link rel="stylesheet" href="static/style.css" />
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <p class="eyebrow">Virginia Cavaliers · Coaching analysis tool</p>
      <h1>UVA Men's Tennis Match Analyzer</h1>
      <p class="subtitle">Click a player below, choose a match, then analyze — stats, coaching notes, and deuce/ad pie charts</p>
    </div>
  </header>

  <main class="container">
    <section class="search-panel card">
      <label class="label" for="roster-query">UVA roster — click a player</label>
      <div class="search-row">
        <input id="roster-query" type="text" placeholder="Search roster (e.g. Dietrich, Switzer, Rice)" autocomplete="off" />
        <button id="roster-refresh-btn" type="button" class="secondary-btn">Refresh</button>
      </div>

      <div id="roster-grid" class="roster-grid"></div>
      <p class="roster-hint">Select a player card to load their matches (includes college duals &amp; NCAA when available).</p>

      <details class="advanced-search">
      <summary class="divider-label">Search any Tennis Abstract player</summary>

      <label class="label" for="player-query">Player name</label>
      <div class="search-row">
        <input id="player-query" type="text" placeholder="Any Tennis Abstract player" autocomplete="off" />
        <button id="search-btn" type="button">Search</button>
      </div>

      <div id="search-results" class="search-results hidden"></div>
      </details>

      <div id="player-card" class="player-card hidden"></div>

      <label class="label" for="tournament-filter">Filter by tournament (optional)</label>
      <input id="tournament-filter" type="text" placeholder="e.g. Zug, ACC, NCAA" />

      <label class="label" for="match-select">Select match</label>
      <select id="match-select" disabled>
        <option value="">Select a roster player above…</option>
      </select>

      <button id="analyze-btn" class="primary-btn" type="button" disabled>Analyze match</button>
      <p id="status" class="status"></p>
    </section>

    <section id="analysis" class="analysis hidden"></section>

    <section id="empty-state" class="empty-state card">
      <h2>How it works</h2>
      <ol>
        <li>Pick any player from the current UVA men's tennis roster</li>
        <li>Optionally filter matches by tournament</li>
        <li>Select a match and click <strong>Analyze match</strong></li>
      </ol>
      <p class="empty-note">Stats, coaching notes, key moments, and deuce/ad pie charts for each match you select.</p>
    </section>
  </main>

  <footer class="footer">
    Roster from <a href="https://virginiasports.com/sports/mten/roster" target="_blank" rel="noopener">VirginiaSports.com</a>
    · Match data from <a href="https://www.tennisabstract.com" target="_blank" rel="noopener">Tennis Abstract</a>
    · Pie charts modeled when shot-tracking unavailable
  </footer>

  <script src="static/app.js"></script>
</body>
</html>
"""
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
