# UVA Tennis Match Analyzer

Interactive coaching tool for **UVA men's tennis** — roster lookup, match stats, coaching notes, and deuce/ad pie charts.

**Live site:** https://neel-42.github.io/uva-tennis-analyzer/

## What's included

- Current UVA roster from [VirginiaSports.com](https://virginiasports.com/sports/mten/roster)
- Match data from [Tennis Abstract](https://www.tennisabstract.com)
- Per-match pie charts (points won, serve/return deuce vs ad)
- Dylan Dietrich hard-court aggregate analysis on the main page

## Run locally

```bash
cd ~/Projects/uva-tennis-analyzer
python3 -m pip install -r requirements.txt
python3 app.py
```

Open **http://127.0.0.1:8787**

## GitHub Pages (frontend)

The site at `neel-42.github.io/uva-tennis-analyzer` is built from `docs/` on every push to `main`. Rebuild locally:

```bash
python scripts/build_pages.py
```

## API backend (for GitHub Pages)

GitHub Pages serves static files only. The interactive roster and match analysis call a small Flask API hosted on [Render](https://render.com):

1. Connect this repo on Render
2. Use the included `render.yaml` (service name: `uva-tennis-analyzer`)
3. Once live, the Pages site calls `https://uva-tennis-analyzer.onrender.com`

Free Render tiers spin down after inactivity — the first load may take ~30 seconds.

## Project structure

- `app.py` — Flask API + local dev server
- `lib/` — Tennis Abstract scraping, analysis, pie charts, UVA roster
- `templates/` — Jinja templates for local dev
- `static/` — frontend JS/CSS
- `docs/` — static site for GitHub Pages (generated)
- `scripts/build_pages.py` — builds `docs/` from templates
