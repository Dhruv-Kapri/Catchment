# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Stages 0, 0.5, 1, 2 and 3 are done (stage 1 on 2026-10-31, stage 2 on 2026-11-03: the `04-plan` benchmark, CP-SAT from greedy
served; stage 3 on 2026-11-07: the FastAPI service, the web map and the static demo at https://dhruv-kapri.github.io/Catchment/).
The first cut is due 25 Nov 2026; what comes after is under "Later" in the roadmap. Results and "done when" notes are in
`docs/roadmap.md`, the decisions behind them in `docs/decisions.md`. The code is `src/catchment/` (`area.py`,
`fetch.py`, `load.py`, `assumptions.py`, `demand.py`, `reach.py`, `build.py`, `spotcheck.py`, `explore.py`, `planning.py`, `serialize.py`, `service.py`, `bundle.py`); `planning.plan()` is the stage 2 entry point, and `explore.py` keeps the
notebooks' placeholder plan model. The repo also holds the
product brief (`docs/brief.md`), the staged roadmap with "done when" criteria (`docs/roadmap.md`), the decision log
(`docs/decisions.md`), the scope cuts (`docs/cuts.md`) and the data survey (`docs/data-sources.md`). Read the brief
and the roadmap before starting any work; record new commands here.

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
uv run pytest -m "not docker"            # skip the OSRM integration tests (they run when Docker is up, with the containers catchment-osrm-test on port 5091 and catchment-osrm-test-ro on 5092)
uv run pytest -m "not browser"           # skip the Playwright smoke test (headless Chromium, and network for the CDN libraries)
uv run catchment-serve [--port 8000]     # the live service: loads the inputs once, POST /plan, GET /levers (ranges, steps, defaults), and the web map at / (also --res, --x-pct, --host)
uv run catchment-bundle [--out outputs/site] [--res 9] [--x-pct 30]   # the static demo site (ADR 0003): solves the 61-plan sweep at 8 workers, writes the plans, read-only data, ODbL notice and metadata, and copies web/ (run on an idle machine; the load is recorded)
scripts/deploy-pages.sh                  # builds the site with catchment-bundle, then force-pushes it as an orphan gh-pages branch to origin
uv run python scripts/time-service.py [--url http://127.0.0.1:8000]   # POST /plan over HTTP for the 04-plan grid and the 64 lever corners against a running catchment-serve; CSV with each request's seconds and load in outputs/; exits 1 if any takes over 10 s
uv run python scripts/check-public.py [--url https://dhruv-kapri.github.io/Catchment/]   # the public static site end to end in a fresh headless Chromium (notice, plan A, plan B with N + 5, B − A table, drawer, no failed request); PASS/FAIL per step to outputs/check-public.log; exits 1 on any FAIL
uv run python scripts/record-demo.py [--url http://127.0.0.1:8000]    # the ~90 s recording and screenshot of the main flow against a running catchment-serve (Playwright, ffmpeg); writes outputs/demo/, copy to docs/media/ by hand
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
  map-app times ([ADR 0002](docs/adr/0002-spot-check-times-in-repo.md)). The README's recording and screenshot in `docs/media/` are
  product media, not data.
- **No scraping of operator apps and no stored Google Places content.** Existing stores (the operator's and
  competitors') come only from the synthetic network; record the source and date of every reported count it uses.
- **Demand is a model, not a forecast.** Every factor stays visible as a lever or labelled assumption;
  don't add ML forecasting.
- **A new plan must return in ≤ 10 s for any scenario in the lever ranges**, every metric included and its gap stated;
  measure it on 04-plan's benchmark grid, on an idle machine, when the solver or a range changes.
- **Type hints on every function**, tests and notebook `def`s included, and wherever a type isn't obvious
  (module constants, class attributes, empty containers). `uvx ruff check --select ANN src tests` stays clean.

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
