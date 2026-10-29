# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Stage 0 (setup and fetch) and 0.5 Explore (notebooks `00-demand`, `01-reach`, `02-plan` on the slice, issues
#1-#6) done 2026-10-29: H3 res 9, candidate sites the top 30% of hexes by places count. Next is stage 1 (demand and
reach on the full area). The code is `src/catchment/` (`area.py`, `fetch.py`, `load.py`, `assumptions.py`, `demand.py`, `reach.py`, `build.py`). The repo also
holds the product brief (`docs/brief.md`), the staged roadmap with "done when" criteria (`docs/roadmap.md`), the
decision log (`docs/decisions.md`), the scope cuts (`docs/cuts.md`) and the data survey (`docs/data-sources.md`).
Read the brief and the roadmap before starting any work; record new commands here.

## Commands

```sh
uv sync          # Python 3.12+ venv (currently 3.14)
uv run pytest    # tests
uv run nbstripout --install                # once per clone: strip notebook outputs on commit
uv run jupyter nbconvert --to notebook --execute notebooks/NN-name.ipynb --output /tmp/NN-name.ipynb   # run a notebook headless; it rewrites notebooks/figures/
uv run catchment-fetch [worldpop viirs overture osm] [--force]   # fetch sources into data/ (osm clips with osmium: `brew install osmium-tool`; VIIRS needs a LAADS DAAC token as LAADS_TOKEN in .env, see .env.example)
uv run catchment-build [demand reach] [--res 9] [--x-pct 30] [--force]   # demand-r9.parquet from the fetched WorldPop and VIIRS; reach: candidates-r9-x30.parquet and table-r9-x30.parquet (builds demand if missing; builds, serves and stops OSRM itself, so Docker must run; prints sites, pairs, time, peak memory)
uv run python -m catchment.area            # rebuild area/gurugram-south-delhi.geojson from Overpass
osrm/osrm.sh build|serve|stop            # two-wheeler OSRM graph into data/osrm/ (Docker, ghcr.io/project-osrm/osrm-backend:v26.10.0-debian; needs data/osm.osm.pbf); serve on localhost:5001; env overrides OSRM_DATA (default data/), OSRM_PORT (5001), OSRM_NAME (catchment-osrm)
uv run pytest -m "not docker"            # skip the OSRM integration tests (they run when Docker is up, with the container catchment-osrm-test on port 5091)
```

## What gets built

Open data → **demand** per H3 hex → **reach** (OSRM two-wheeler travel times, candidate site × hex) →
**plan** (CP-SAT picks N stores, vs a greedy baseline) → **compare** (FastAPI `POST /plan` + MapLibre
web map with levers). Python for the pipeline and service; the web map is JavaScript.

- Stages are strictly ordered; the next starts only when the previous one's "done when" is met.
- Notebook-first, as in the sibling projects: in stage 0.5 (Explore), `00-demand`, `01-reach`,
  `02-plan` run the whole chain on a small slice with outputs committed as static PNGs; stages 1-2 move
  the clean code into `src/catchment/` and run it on the full area.
- The first cut is due **25 Nov 2026**. If a stage overruns, cut scope and log it in `docs/cuts.md`;
  don't move the date.

## Constraints that shape the code

- **Dev machine: Apple Silicon, 8 GB RAM, no GPU.** Clip OSM extracts to the area (plus a buffer) with
  `osmium` before running OSRM; keep the travel-time table sparse.
- **Never commit data.** `data/`, `outputs/`, `.osm.pbf`, OSRM graphs, rasters and parquet are
  gitignored; datasets keep their own licences. The one exception is `docs/spot-check.csv`, spot-check
  map-app times ([ADR 0002](docs/adr/0002-spot-check-times-in-repo.md)).
- **No scraping of operator apps and no stored Google Places content.** Existing stores (the operator's and
  competitors') come only from the synthetic network; record the source and date of every reported count it uses.
- **Demand is a model, not a forecast.** Every factor stays visible as a lever or labelled assumption;
  don't add ML forecasting.
- **A new plan must return in ≤ 10 s** for the default scenario; measure it when the solver changes.

## Docs conventions

- Product docs are one page each. A change to scope or the brief gets an entry in `docs/decisions.md`;
  anything removed gets a row in `docs/cuts.md`.
- In `docs/data-sources.md`, facts are marked **Verified** (with date) or left unverified. Keep that
  distinction.
- Use the terms in `CONTEXT.md` (hex, candidate site, catchment, promise, lever, scenario, plan).
- The repo is public: write about the product and its users only.
- `docs/reference/*.pdf` are reading lists with their HTML sources in `docs/reference/src/`; edit the HTML,
  then re-render with headless Chrome (`--print-to-pdf --no-pdf-header-footer`).

## Agent skills

### Issue tracker

Issues live in GitHub Issues for Dhruv-Kapri/Catchment (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root (created lazily). See `docs/agents/domain.md`.
