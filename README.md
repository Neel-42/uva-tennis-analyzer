# UVA Tennis Match Analyzer

Interactive coaching tool for **UVA men's tennis** — roster lookup, match stats, coaching notes, and deuce/ad pie charts.

GitHub Pages serves a **static build** of the app (roster, matches, and analyses are pre-fetched on each deploy). No separate API server required.

**Live site:** https://neel-42.github.io/uva-tennis-analyzer/

## What's included

- Current UVA roster from [VirginiaSports.com](https://virginiasports.com/sports/mten/roster)
- Match data from [Tennis Abstract](https://www.tennisabstract.com)
- Per-match pie charts (points won, serve/return deuce vs ad)

Not included: Dylan Dietrich's aggregated hard-court analysis lives in the separate [tennis-match-analyzer](https://github.com/Neel-42/tennis-match-analyzer) repo.

## Run locally

```bash
cd ~/Projects/uva-tennis-analyzer
python3 -m pip install -r requirements.txt
python3 app.py
```

Open **http://127.0.0.1:8787**

## GitHub Pages (frontend)

The site at `neel-42.github.io/uva-tennis-analyzer` is rebuilt on every push to `main`. The workflow scrapes Tennis Abstract and bundles roster, match, and analysis JSON into `docs/data/`.

Rebuild locally:

```bash
python scripts/build_pages.py
```

Player search on the public site is limited to the UVA roster. For live Tennis Abstract search, run the Flask app locally.

## Project structure

- `app.py` — Flask API + local dev server
- `lib/` — Tennis Abstract scraping, analysis, pie charts, UVA roster
- `templates/` — Jinja templates for local dev
- `static/` — frontend JS/CSS
- `docs/` — static site for GitHub Pages (generated)
- `scripts/build_pages.py` — builds `docs/` from templates
