#!/usr/bin/env python3
"""UVA Men's Tennis Match Analyzer — roster lookup and match analysis."""

from __future__ import annotations

import os
import sys

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(__file__))

from lib.analysis import build_match_analysis
from lib.pie_charts import build_pie_charts
from lib.tennis_abstract import (
    fetch_player,
    match_to_dict,
    profile_to_dict,
    search_players,
)
from lib.uva_roster import enrich_roster_player, get_uva_roster, roster_to_dict

app = Flask(__name__)

PAGES_ORIGINS = (
    "https://neel-42.github.io",
    "http://127.0.0.1:8787",
    "http://localhost:8787",
)


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin.startswith("https://neel-42.github.io") or origin in PAGES_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Vary"] = "Origin"
    return response


@app.route("/api/<path:_path>", methods=["OPTIONS"])
def api_options(_path: str):
    return ("", 204)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/uva-roster")
def api_uva_roster():
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    try:
        players = get_uva_roster(refresh=refresh)
        return jsonify(
            {
                "team": "Virginia Cavaliers Men's Tennis",
                "season": "2026-27",
                "source": "virginiasports.com",
                "players": roster_to_dict(players),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "players": []}), 500


@app.get("/api/uva-roster/<path:player_name>")
def api_uva_roster_player(player_name: str):
    try:
        player = enrich_roster_player(player_name)
        if not player:
            return jsonify({"error": f"Player not on UVA roster: {player_name}"}), 404
        payload = roster_to_dict([player])[0]
        if player.slug and player.has_data:
            profile, matches = fetch_player(player.slug)
            payload["profile"] = profile_to_dict(profile)
            payload["matches"] = [match_to_dict(m) for m in matches]
        return jsonify(payload)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.get("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    try:
        results = search_players(q)
        return jsonify({"results": results})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "results": []}), 500


@app.get("/api/player/<slug>")
def api_player(slug: str):
    tournament = request.args.get("tournament", "").strip().lower()
    try:
        profile, matches = fetch_player(slug)
        if tournament:
            matches = [m for m in matches if tournament in m.tournament.lower()]
        return jsonify(
            {
                "profile": profile_to_dict(profile),
                "matches": [match_to_dict(m) for m in matches],
            }
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.get("/api/analyze/<slug>/<match_id>")
def api_analyze(slug: str, match_id: str):
    try:
        profile, matches = fetch_player(slug)
        match = next((m for m in matches if m.id == match_id), None)
        if not match:
            return jsonify({"error": "Match not found"}), 404
        analysis = build_match_analysis(profile, match)
        analysis["pieCharts"] = build_pie_charts(profile, match)
        analysis["profile"] = profile_to_dict(profile)
        return jsonify(analysis)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8787))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    debug = not os.environ.get("PORT")
    print(f"UVA Tennis Match Analyzer running at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
