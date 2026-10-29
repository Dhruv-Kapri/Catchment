# Roadmap

Target: the first cut live by **25 November 2026**, part-time (about 6-8 hours a week). If a stage
runs over, cut scope (record it in [cuts.md](cuts.md)), don't move the date. Each stage ends in
something that runs and can be shown; the next stage does not start until the previous one is done.

Terms (hex, candidate site, catchment, promise, lever, plan, ...) are defined in [CONTEXT.md](../CONTEXT.md).

## 0. Setup (to 1 Nov)

- `uv` project, with Jupyter and `nbstripout` in the dev group; the area polygon (Gurugram + South
  Delhi, from OSM admin boundaries) committed as GeoJSON.
- Fetch scripts for WorldPop, VIIRS and Overture Places/Buildings, clipped to the area; resumable and
  idempotent, writing to `data/`.
- **Done when:** one command fetches every source for the area into `data/`.
- **Done 2026-10-29:** `uv run catchment-fetch`. VIIRS comes from NASA Black Marble, not EOG (see
  [decisions](decisions.md)). The OSM road network was missed; it is now the `osm` source (Geofabrik northern
  zone, clipped to the area plus 5 km).

## 0.5 Explore (to 8 Nov)

Notebooks before code, as in the sibling projects: the whole chain runs once on a small slice, so the
risks late in the pipeline (OSRM within 8 GB, the size of the travel-time table, CP-SAT solve time)
show up in the first week rather than the third. Each notebook works its stage inline, with outputs
saved as static PNGs in `notebooks/figures/` and embedded in markdown cells (nbstripout strips
outputs), so it reads on GitHub; the clean version goes into the package in stages 1-2.

| # | Notebook | Question it answers |
| --- | --- | --- |
| 00 | `00-demand` | the slice (about 80 km², old Gurugram to Golf Course Road; several catchments across, recorded why); the finest hex resolution whose full-area table and solve fit the budget (res 9 first, else res 8); demand per hex, each factor as its own map |
| 01 | `01-reach` | does OSRM's two-wheeler profile build and route within 8 GB; the two-wheeler profile (edited `car.lua`, every edit listed); the candidate site rule (top X% of hexes by places count); how many pairs the table holds under the longest promise |
| 02 | `02-plan` | greedy baseline and the CP-SAT model on the slice (N = 3, placeholder synthetic network inline); solve time, and what it implies for the full area's default scenario |

- Notebooks import helpers (fetch, loaders) from the `catchment` package; stage logic stays inline
  until the stage is formalised.
- No notebook for the web map (stage 3); it is JavaScript and goes straight to code.
- **Done when:** all three notebooks run top to bottom on the slice, the hex resolution and candidate
  site rule are recorded, and the expected table size and solve time for the full area are written up.
- **Done 2026-10-29:** H3 res 9; candidate sites are the top 30% of the area's hexes by places count (1,458).
  Full area extrapolated to about 1.4 M table pairs (17 MB) and a CP-SAT solve of 3.1-5.6 s at N = 10 (res 8:
  0.04 s), so the ≤ 10 s bar looks reachable at res 9; stage 1 measures it. Solve time grows with N. CP-SAT ties greedy at N = 3 on the slice and leads by 3% at
  N = 10. A capacity that binds solves slowly, an open point for the capacity lever (see
  [decisions](decisions.md)).

## 1. Demand and reach (to 13 Nov)

- `00-demand` and `01-reach` move into `src/catchment/` and run on the whole area.
- OSRM on an OSM extract clipped to the area plus a buffer (clip with `osmium` first).
- Travel-time table, candidate site × hex, kept sparse (only pairs under the longest promise considered).
- Spot check: about 20 routes compared by hand against a live map app at a stated time of day; numbers
  noted, not stored from the app. The error is reported in the notebook and later in the UI.
- **Done when:** a demand map PNG of the area is committed, the demand table and the travel-time table
  each build from one command, and the spot-check error is written up.

## 2. Plan (to 18 Nov)

- `02-plan` moves into `src/catchment/`: the greedy baseline and the CP-SAT model (maximise covered
  demand; N stores; capacity; shared catchments split by brand, see [ADR 0001](adr/0001-demand-split-by-brand.md);
  the synthetic network fixed).
- Synthetic network generator (the operator's and competitors' existing stores), with every count's
  source and date recorded.
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
