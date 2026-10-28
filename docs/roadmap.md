# Roadmap

Target: the first cut live by **25 November 2026**, part-time (about 6-8 hours a week). If a stage
runs over, cut scope (record it in [cuts.md](cuts.md)), don't move the date. Each stage ends in
something that runs and can be shown; the next stage does not start until the previous one is done.

Terms (hex, candidate site, catchment, promise, lever, plan, ...) are defined in [CONTEXT.md](../CONTEXT.md).

## 0. Setup and demand (week 1, to 4 Nov)

- `uv` project; the area polygon (Gurugram + South Delhi, from OSM admin boundaries) committed as GeoJSON.
- Fetch scripts for WorldPop, VIIRS and Overture Places/Buildings, clipped to the area; resumable and
  idempotent, writing to `data/`.
- Notebook `00-demand`: hexes at the working resolution (choose it here, and record why), demand per
  hex with each factor shown as its own map.
- **Done when:** a demand map PNG of the area is committed and the demand table is reproducible from
  one command.

## 1. Reach (week 2, to 11 Nov)

- OSRM with a two-wheeler profile on an OSM extract clipped to the area plus a buffer (clip with
  `osmium` first; the dev machine has 8 GB RAM).
- Candidate sites: rule decided and recorded in notebook `01-reach`.
- Travel-time table, candidate site × hex, kept sparse (only pairs under the longest promise considered).
- Spot check: about 20 routes compared by hand against a live map app at a stated time of day; numbers
  noted, not stored from the app. The error is reported in the notebook and later in the UI.
- **Done when:** the travel-time table builds from one command and the spot-check error is written up.

## 2. Plan (week 3, to 18 Nov)

- Notebook `02-plan`: the greedy baseline, then the CP-SAT model (maximise covered demand; N stores;
  capacity; shared catchments split; competitor layer and existing stores fixed).
- Competitor layer generator, with every count's source and date recorded.
- Benchmark over a grid of scenarios: covered demand CP-SAT vs greedy, solve time.
- **Done when:** CP-SAT returns a plan in ≤ 10 s for the default scenario, and the comparison table
  with greedy is committed (whichever wins).

## 3. Compare and ship (week 4, to 25 Nov)

- FastAPI service: `POST /plan` takes a scenario and returns the plan and its metrics; travel times and
  demand loaded at start-up.
- Web map (MapLibre): demand layer, catchments, chosen stores, a lever panel, two scenarios side by side.
- Deployed to one small VM or Fly.io; a ~90 s screen recording of the main flow.
- **Done when:** the public URL works end to end on a fresh browser, and the README shows a screenshot
  and the link.

## Later (after 25 Nov)

- **Scale:** all of Delhi NCR; measure what breaks (table size, solve time, memory) and fix it.
- **Ops simulator:** event-driven orders → picking → rider batching and routing, to stress-test a plan
  at the evening peak.
- **Heuristic benchmark:** the facility-location heuristic of arXiv 2312.11494 as a second baseline.
- **A real user:** a small NCR operator (pharmacy or grocery chain, D2C brand) using it on their own
  question.
