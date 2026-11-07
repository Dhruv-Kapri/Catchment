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
- **Done 2026-10-29:** H3 res 9; candidate sites are the top 30% of the area's hexes by places count (1,458). Full
  area extrapolated to about 1.4 M table pairs (17 MB) and a CP-SAT solve of 3.1-5.6 s at N = 10 (res 8: 0.04 s), so
  the ≤ 10 s bar looks reachable at res 9; stage 1 measures it. Solve time grows with N. CP-SAT ties greedy at N = 3
  on the slice and leads by 3% at N = 10. A capacity that binds solves slowly, an open point for the capacity lever
  (see [decisions](decisions.md)).

## 1. Demand and reach (to 13 Nov)

- `00-demand` and `01-reach` move into `src/catchment/` and run on the whole area.
- OSRM on an OSM extract clipped to the area plus a buffer (clip with `osmium` first).
- Travel-time table, candidate site × hex, kept sparse (only pairs under the longest promise considered).
- Spot check: about 20 routes compared against a live map app at a stated time of day; the
  app times go in `docs/spot-check.csv` ([ADR 0002](adr/0002-spot-check-times-in-repo.md)). The
  error is reported in the notebook and later in the UI.
- **Done when:** a demand map PNG of the area is committed, the demand table and the travel-time table
  each build from one command, and the spot-check error is written up.
- **Done 2026-10-31:** `03-area` on the full area (4,859 hexes, 1,458 candidate sites; res 9 and X = 30 stand), the
  demand map in `notebooks/figures/03-demand.png`, `uv run catchment-build` for the demand and travel-time tables.
  Spot check (20 routes, Google Maps two-wheeler, Fri 30 Oct, 19:00-19:07, live estimates): the app took a median 1.28×
  free-flow × 1.4 (25th-75th percentile 1.17-1.54); the implied multiplier is about 1.8. Changing the 1.4 default is
  left to a decision. The default scenario returns a plan within 10 s with a tighter capacity row, gap stated (see
  [decisions](decisions.md)).

## 2. Plan (to 18 Nov)

Scope set in the stage 2 grill, 2026-11-01 (see [decisions](decisions.md)).

- `02-plan` moves into `src/catchment/`: the greedy baseline and the CP-SAT model (maximise covered
  demand; N stores; capacity; shared catchments split by brand, see [ADR 0001](adr/0001-demand-split-by-brand.md)).
  The CP-SAT model is the tighter one in `03-area` (#15, the tighter capacity row), not `02-plan`'s 0.5 model, with a
  build-plus-solve budget. Two CP-SAT variants: on its own, and starting from the greedy plan. `02-plan` stays frozen
  as the 0.5 record; the stage 2 notebook is `04-plan`. Align the "≤ 10 s" wording in CLAUDE.md and the brief with
  the rule below.
- Synthetic network generator: 57 existing stores (computed from the calibration), the operator and one competitor,
  split by two verified reported store counts (the operator takes the market leader's, the competitor the next
  largest brand's), with source and date recorded. Brands stay generic in the UI.
- Levers and ranges: N 1-20 (default 10); promise 8-20 min (10; narrowed to 8-16 by the benchmark); congestion multiplier 1.0-2.5 (default **1.8**, the
  spot check); capacity 0.5×-2× the default 2,364; capture share 0.5×-1.5× the default; competitor density 0×-2× the
  competitor's count, step 0.25 (1×).
- Plan metrics, all inside the 10 s: demand and households covered, new vs cannibalised demand per new store, lost
  demand (over capacity, unreached), slow-traffic coverage (the same stores at 1.25× the scenario's multiplier).
- Benchmark, three-way (greedy, CP-SAT on its own, CP-SAT from greedy) on an idle machine: each lever swept across its
  range at the default, the hardest corners, and 5 network seeds at the default. The service runs CP-SAT from greedy
  unless CP-SAT on its own is never worse on demand covered and is faster.
- Stage 1 follow-ups: #22 whole. #23 is done: the notebooks' plan model is `catchment.explore` (typed
  `SolveResult`); the planning module builds its own and copies nothing from the notebooks.
- **Done when:** any scenario in the lever ranges returns a plan with every metric within 10 s, its gap stated,
  measured on the benchmark grid; the three-way table is committed in `04-plan` with a decision-log summary; the
  generator places the 57 stores by verified counts, with the density lever; the default multiplier is 1.8. A range
  whose scenarios miss 10 s or return a plan worse than greedy is narrowed and logged in [cuts](cuts.md), not a
  blocker.
- **If it overruns, cut in this order:** the #23 extras; the density lever (fixed at 1×, to Later); network seeds
  5 → 2.
- **Done 2026-11-03:** `planning.plan()` (greedy, CP-SAT on its own, CP-SAT from greedy) with every metric, the 57-store
  two-brand network with the density lever, default multiplier 1.8. `04-plan` benchmarks 31 scenarios × 3 methods on the full
  area: every plan within 10 s with its gap stated (slowest 8.46 s), CP-SAT from greedy never below greedy and optimal in 25 of
  31, gain over greedy up to 4.7% where capacity binds or the market is largest. Six combinations off the grid, the box's worst
  corner included, also return within 10 s (at most 8.63 s) with a gap (#33's model size cap; a capacity bound when CP-SAT has
  none). All 64 corners of the box return within 10 s (slowest 8.60 s) with a gap stated. #34 lowered `PLAN_BUDGET` from 9 to 8 s
  so the bar keeps 2 s for the metrics and CP-SAT's overshoot (the earlier run had one 11.3 s corner); the re-run was under heavy
  load from other sessions (median 18 on the grid, up to 64 on the corners), not on an idle machine. CP-SAT from greedy is served.
  The promise range is narrowed to 8-16 ([cuts](cuts.md)); see [decisions](decisions.md).

## 3. Compare and ship (week 4, to 25 Nov)

Scope set in the stage 3 grill, 2026-11-05; spec #41, tickets #35 and #42-#51 (see [decisions](decisions.md), [ADR 0003](adr/0003-static-demo-on-gh-pages.md)).

- `plan()` also returns the hex-to-store assignment, each store's catchment and greedy's demand covered; #35 runs in parallel.
- FastAPI service, run locally from one command: `POST /plan` takes a scenario and returns the plan and its metrics,
  plus read-only endpoints for the assumptions, the lever ranges and demand. Travel times and demand are loaded at start-up.
  One plan at a time, with a small cache by scenario.
- Web map (MapLibre, plain JavaScript with no build step, OpenFreeMap basemap):
  - a demand layer (market demand);
  - existing and new stores;
  - service areas, and the selected store's catchment as an outline;
  - a lever panel with a Plan button;
  - two linked maps, A and B, with a B − A metrics table;
  - each plan's gap and its result against greedy;
  - an assumptions drawer with the spot-check error.
- Static demo on GitHub Pages (`gh-pages` branch, ODbL): the same map reading about 61 plans solved on the dev machine
  (the default, and each lever's UI steps with the others at the default).
- A ~90 s screen recording of the main flow, made locally against the live service.
- **Done when:** the service runs locally from one command and returns any scenario within 10 s; the static site on
  GitHub Pages works end to end on a fresh browser; the README shows a screenshot, the link and the recording.
- **If it overruns, cut in this order:** the catchment outline; the sweep coarsened to 04-plan's 31 scenarios; two maps
  replaced by one map with an A/B toggle.
- **Done 2026-11-07:** nothing cut. The service runs from `uv run catchment-serve`; `scripts/time-service.py` sent the 04-plan grid
  (seed rows dropped: the seed is not a lever) and all 64 corners, 91 scenarios, to it over HTTP. Every one returned within 10 s in each of four runs. The first two:
  slowest 9.48 s (multiplier 1.0, FEASIBLE, 17.0% gap) at load 12.5, median load 15.9, in the first run; slowest 8.38 s (N 20, promise 16,
  multiplier 2.5, capacity 0.5×, capture 1.5×, density 0) with a median load of 12.1 in the second (8 CPUs; CP-SAT's own 8 workers are about 8
  of it). Other sessions ran tests alongside both. A third run started on a quiet machine (load 2.4, no other test runs): all 91 within 10 s,
  slowest 8.37 s (the same corner as the second run), multiplier 1.0 at 7.15 s (OPTIMAL); the load during it (median 11.8) is mostly the
  service's own CP-SAT workers. A fourth run waited for 3 minutes under load 2 (15:50 IST), then sent the 91 and 200 random
  scenarios (each lever at a random step, `--random 200 --seed 51`): all 291 within 10 s. The 91 ran on an idle machine (load before each
  request median 6.5, max 8.7, about CP-SAT's own 8 workers), slowest 8.46 s; the random 200 slowest 8.60 s (median 0.39 s; other sessions
  returned during it, load up to 36). The lever box holds about 900 k scenarios; no random scenario was slower than the grid and corners by
  more than 0.14 s, so they stand in for "any scenario", as in 04-plan. The random sample found wider gaps than the grid: 22 of 200 above 10%,
  up to 52%, all from the capacity bound (the map labels them, #52). `catchment-bundle` solved the 61 plans in 89 s at 8 workers, load 8.9
  before and 15.6 after; the slowest plan was 8.93 s. The site is on GitHub Pages at <https://dhruv-kapri.github.io/Catchment/>. In a fresh
  headless Chromium context (2026-11-07, 14:44 IST) it plans the default, plans B with a lever moved, fills the B − A table and opens the drawer, with no failed request; `scripts/check-public.py` repeats the check (5 of 5 steps passed,
  2026-11-07 10:12 UTC, Chromium 156).
  The README shows the screenshot, the link and the 90 s recording (`docs/media/`, made with `scripts/record-demo.py` against the live
  service). The B − A table's stale state and bound source (#53), the shared number formatter and server-side plan note (#54), the one lever spec (#55)
  and the page's declared data source (#56) landed after the site was published. It was re-published with them (`scripts/deploy-pages.sh`, 61 plans in 83 s, load 5.9 before and
  16.6 after; `scripts/check-public.py` 5 of 5, 2026-11-07 11:26 UTC), and the recording and screenshot were re-made against the live service.

## Later (after 25 Nov)

- **Scale:** all of Delhi NCR; measure what breaks (table size, solve time, memory) and fix it.
- **Ops simulator:** event-driven orders → picking → rider batching and routing, to stress-test a plan
  at the evening peak.
- **Heuristic benchmark:** the facility-location heuristic of arXiv 2312.11494 as a second baseline.
- **Three competitor brands** in the synthetic network, each sized by a verified store count (the first cut has one).
- **Capture share by urban or rural hex**, for the NCR scale-up where rural areas come in (the first cut uses one
  value for every hex; the affluence multiplier carries the difference).
- **A live public host** running `POST /plan` (needs paid compute, about 8 cores, to keep plan quality; see
  [ADR 0003](adr/0003-static-demo-on-gh-pages.md)), and **pairs of levers** in the static demo.
- **A real user:** a small NCR operator (pharmacy or grocery chain, D2C brand) using it on their own
  question.
