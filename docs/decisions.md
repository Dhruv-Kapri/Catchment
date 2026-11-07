# Decision log

Newest first. One entry per decision: what was decided, why, and what it rules out. Big or
hard-to-reverse decisions also get an ADR in `docs/adr/` (created when the first one is needed).

## 2026-11-07: Compare and ship (stage 3) closed (#51)

- **Stage 3 is done with nothing cut** (roadmap, "Done 2026-11-07"). The live service returned all 91 scenarios it was sent (the 04-plan grid
  and the 64 lever corners) within 10 s over HTTP, in four runs: slowest 9.48 s and 8.38 s with other work running on the machine (1-minute loads of 12.5 and 13.0 just before those requests), 8.37 s in a run that started on a quiet machine (load 2.4), and 8.46 s on an idle machine, where 200 random scenarios also returned within 10 s
  (slowest 8.60 s). The grid and the corners stand in for the box's ~900 k scenarios: no random one was slower by more than 0.14 s.
  The static demo is published on GitHub Pages from the 61-plan sweep (89 s at 8 workers, load 8.9-15.6).
  - Why it holds: `PLAN_BUDGET` is 8 s, which leaves 2 s for the metrics and CP-SAT running past its limit. The slowest request ran 1.48 s past the budget under load; on an idle machine, 0.46 s. That margin is thin under load. A change to the solver,
    a range or the plan's metrics re-runs `scripts/time-service.py` before it lands.
  - The timing and recording scripts live in `scripts/`, not the package: they drive a running service from the outside and are not part of
    the product.
  - The recording (90 s) and screenshot are committed under `docs/media/` (2.2 MB and 0.6 MB). They show the product, not data, and the README
    links them. Re-record with `scripts/record-demo.py` when the UI changes.
  - Rules out: nothing new. A live public host stays under Later (ADR 0003).

## 2026-11-05: The assumptions drawer names brands only in its sources (#44, #48)

- **The assumptions table's inputs and values say Operator and Competitor; the Source column keeps the filing it cites, by name and URL.**
  "Blinkit orders, Q2 FY27" and "Blinkit stores" became "Operator orders, Q2 FY27" and "Operator stores", and the split's value says
  "operator 2,751". The drawer (#48) shows the table as served, so it was the one part of the UI naming a real brand (spec #41: Operator and
  Competitor are the only brand names shown).
  - Why: a citation is provenance, not a brand label; dropping it would break "record the source and date of every reported count".
  - Rules out: renaming the sources. The constants in `assumptions.py` (`BLINKIT_ORDERS_Q2`, `BLINKIT_STORES`) and `explore.py`'s
    notebook table keep their names: neither reaches the UI.

## 2026-11-05: A plan states where its bound came from (#52)

- **A plan carries `bound_source`: "solver" (CP-SAT's own bound) or "capacity" (`capacity_bound`), None when there is no bound.** The source
  is whichever gave the lower of the two (the solver on a tie); the clamp to the objective does not change it.
  - Why: the 04-plan re-run (4bd0611) found the widest gap at 62.5% (N 1, promise 8, multiplier 1.0, capacity 2x, capture 1.5x, density 0), and 9 of
    the 64 corners above 10%, 8 of them at capacity 0.5x. Those gaps come from the cheap capacity bound, not the solver. The web map shows each
    plan's gap (spec #41, story 23), so a planner would read a capacity-bound gap as a solver gap.
  - Rules out: nothing yet. Tightening the bound (shared hexes, an LP relaxation) is not done: each candidate must re-measure the 64 corners
    against the 10 s bar. The label costs no solve time.
  - The web map's gap reads "12.5% (from the capacity bound, which can be loose)" when `bound_source` is "capacity"; the panel's label is
    "Gap to the bound". The B − A table's Gap row does not say the source yet (#53).

## 2026-11-05: Compare and ship (stage 3) scope (spec #41; tickets #35, #42-#51)

Set in the stage 3 grill.

- **The live service runs locally; the public URL is a static site** ([ADR 0003](adr/0003-static-demo-on-gh-pages.md)).
  - FastAPI `POST /plan` takes any scenario in the lever ranges; the read-only endpoints serve the assumptions, the lever
    ranges and demand. It starts from one command and runs one plan at a time, with a small cache by scenario. Nothing is precomputed at start-up.
  - The public site is the same web map on GitHub Pages, reading about 61 plans solved on the dev machine at 8 workers:
    the default plus every UI step of each lever with the others at the default (N 1-20; promise 8-16 by 1; multiplier
    1.0-2.5 by 0.1; capacity, capture and density by 0.25). On the static site, moving one lever resets the others.
  - The ~90 s recording is made locally, against the live service.
  - Rules out: a live public host. Free compute is too thin: Hugging Face Docker Spaces need a paid plan (verified
    2026-11-05), and Render's free tier has 0.1 CPU. Paid compute was declined for a demo.
- **The 10 s bar stays measured on the dev machine.** With fewer workers, plans still return within the budget, but
  quality drops.
  - Measured 2026-11-05, cpsat-from-greedy, one run each, load about 5-6 from other work on the machine:
    - Every run, at 1, 2, 4 or 8 workers, returned within 8.1 s.
    - The default scenario proved optimal in 0.26 s at 8 workers. At 1-4 workers it stopped at the limit: the same
      plan, with a 48% stated gap.
    - At capacity 0.5× and N 20, the plan covered 45,693 orders a day with a 1.0% gap at 8 workers. At 1-4 workers it
      covered 43,406-45,148 with gaps of 23-28%; greedy covered 43,266.
  - Peak memory was 349 MB, and `load_inputs` took 0.85 s.
- **Every lever has a step; `GET /levers` publishes them (2026-11-05).**
  - `Scenario` refuses an off-step value, as it already refused an off-step density (e.g. multiplier 1.45, which `plan()`
    accepted before). Steps: N 1, promise 1, multiplier 0.1, capacity, capture and density 0.25.
  - `GET /levers` returns each lever's range, step and default, so the JS no longer hard-codes them. A range, step or type
    error is a 422 naming the lever and its range.
- **Web map: plain JavaScript and ES modules, no build step.**
  - MapLibre with the OpenFreeMap basemap, served by FastAPI locally and from gh-pages publicly.
  - Two maps with linked pan and zoom: A starts at the default, B starts as a copy of A. A metrics table shows B − A.
  - A Plan button runs a plan; it does not re-run on every lever change.
- **What the map shows:**
  - The demand layer is market demand at the scenario's capture share, before the split between brands; the metrics
    are the operator's and are labelled so.
  - Existing stores of both brands, brands generic.
  - Each operator store's **service area** (new term in CONTEXT.md) as fill, and the selected store's catchment as an outline.
  - Each plan's gap and its demand covered against greedy's. Where the model is over the size cap (wide reach, e.g.
    promise 16), the plan is greedy's and the UI says why the gain is 0.
  - An assumptions drawer generated from `assumptions.table()`, with the spot-check error next to the congestion
    lever, and the network seed stated (2026, not a control).
- **`plan()` also returns the hex-to-store assignment, each store's catchment and greedy's demand covered.** Issue #35's
  cleanup runs in parallel.
- **Tests:**
  - API contract tests: request validation and the response shape.
  - One test that the static bundle uses the API's serializer.
  - One Playwright smoke test in the browser.
  - No JS unit tests.
- **If it overruns, cut in this order:** the catchment outline on a selected store; the sweep coarsened to 04-plan's
  31 scenarios; two maps replaced by one map with an A/B toggle.

## 2026-11-03: PLAN_BUDGET 9 → 8 s: the 10 s bar keeps 2 s for the metrics and for CP-SAT running past its time limit (#34)

- **Decided:** `assumptions.PLAN_BUDGET` is 8 s (was 9 s). It covers network, shares, reach, greedy, model and solve; the metrics run
  after it, so a plan's total is the budget plus whatever the solver overshoots plus the metrics.
- **Why:** #30's corner sweep had one 11.28 s plan (N 1, promise 8, multiplier 1.0, capacity 0.5×, capture 1.5×, density 2; load 7.7):
  CP-SAT ran about 2.3 s past its time limit. A re-run of that corner under load 15-36 measured the build at 3-4.7 s (0.65 s on a quiet
  machine), CP-SAT about 1 s past its limit, and the metrics up to 1.3 s (0.03 s quiet), totals 10.0-11.7 s. A 9 s budget left 1 s, which
  none of that fits in; stage 3's service will answer requests on a machine that is not idle.
- **Ruled out:** 4 solver workers instead of 8 (no clear difference in the overshoot at load 31-36); keeping 9 s and re-running only on an
  idle machine (it would have hidden the overshoot, not removed it).
- **Result (`04-plan` re-run, 2026-11-03 10:43-10:50 IST, not on an idle machine: load 2.4 at the start, then 16.7-64.0 before each plan
  from other work on the machine).** All 64 corners return within 10 s, slowest 8.60 s, every gap stated; the 11.28 s corner took 8.11 s. The grid
  passes too (slowest 8.46 s). The bar held under load, not only on a quiet machine. A lower budget leaves CP-SAT less time, so
  more time-limited plans end on a gap; see the #30 entry for the numbers.

## 2026-11-03: Plan (stage 2) benchmark: CP-SAT from greedy is served, promise narrowed to 8-16, a capacity bound for every CP-SAT plan (#30)

- **Benchmark (`04-plan`, re-run 2026-11-03 10:43-10:50 IST, with #33 merged and `PLAN_BUDGET` 8 s from #34).** 31 scenarios on the full area (each lever swept with the
  others at the default, the two hardest corners, 5 network seeds) × greedy, CP-SAT on its own and CP-SAT from greedy, through
  `plan()`. Every plan returned within 10 s with its gap stated (slowest 8.46 s; CP-SAT from greedy at most 8.46 s, on its own at most 8.23 s; greedy
  0.03-0.19 s); none ended UNKNOWN. CP-SAT from greedy was never below greedy and proved optimality in 25 of 31 (CP-SAT on its own: 25);
  the other 6 (promise 16, multiplier 1.0, capacity 0.5×, capture 1.5×, and the two corners) stopped at the budget with gaps of 0.3-2.7%.
  Its gain over greedy: median 0.14%, 0 in 11 scenarios, 3.9-4.7% where capacity binds or the market is largest. Load: not an idle
  machine. It was 2.4 at the start, then other work loaded it: median 18.0 and maximum 20.8 before each plan (8 CPUs), and the bar
  held anyway. Slow-traffic coverage never exceeded demand covered (0 of 93 plans before #33's clamp, too).
- **CP-SAT from greedy is the served variant.** The stage 2 rule serves CP-SAT on its own only if it is never worse on demand
  covered and is faster. In this run it is below greedy in 2 scenarios (promise 16 by 1,493 orders a day, capacity 0.5× by 1,269) and
  below CP-SAT from greedy in all 6 time-limited ones (by up to 2,723 orders a day, capacity 0.5×), though faster at the median (0.95 s vs
  1.13 s). So the rule picks CP-SAT from greedy, by real margins. Earlier runs agreed with smaller margins (07:28, before #33, its CSV in
  commit e13b3d6: behind by 31 and 336 orders a day; 08:51: rounding-level ties), and CP-SAT on its own can return no plan (UNKNOWN)
  where CP-SAT from greedy keeps greedy's.
- **Every CP-SAT plan with an objective states a bound** (`planning.capacity_bound`): the lower of the demand any open site
  reaches and what the existing stores plus the N best candidate sites can serve, each at most min(capacity, the share it reaches).
  It is valid for any choice of sites and any assignment, so it bounds demand covered too. The plan's bound is the lower of it and
  CP-SAT's, never under the objective; where CP-SAT's is the lower, it bounds the solver's objective on rounded shares, and a
  FEASIBLE plan's demand covered can sit slightly above it (see the `Plan` docstring). This gives a gap where #33 left a kept greedy plan or an unbuilt model with none, and caps a
  runaway solver bound (seen: 1.65 M orders a day against the area's 89.7 k). It is loose where CP-SAT finds nothing better than
  greedy on a binding-capacity model (17-19% in the combinations below); the gap is honest, not tight.
- **The promise range narrows from 8-20 to 8-16** (`assumptions.PROMISE_RANGE`; cuts.md), measured before #33's size cap and the
  capacity bound: at 19 and 20, CP-SAT found no solution in the budget in every run, so the plan carried no gap; at 18 one run took
  10.46 s and 3 of 6 reported a 2,957% gap; 16 gave a usable gap in every run. Both failure modes are now addressed (the size cap,
  the capacity bound), so 17-20 may pass a re-measure; re-widening is left to that. The travel-time table still keeps pairs to
  17 free-flow min; nothing is rebuilt.
- **Combinations off the grid pass too.** 04-plan runs six in-range combinations that widen the free-flow reach, (promise − 3) /
  multiplier, or bind capacity at a wide reach, including the box's worst corner (promise 16, multiplier 1.0, N 20, capacity 0.5×,
  capture 1.5×, density 0). Before #33 and the capacity bound, promise 16 × multiplier 1.0 took 12.2 s (10.3 s of build) and five
  of them stated no gap. Now all six return within 10 s (at most 8.63 s) with a gap, all as greedy's plan (HEURISTIC): the wide-reach models are over the size
  cap, so greedy's plan returns in under 2 s with gaps of 0.6-1.3%; the binding-capacity ones keep greedy's plan with gaps of 17-19%
  (the build alone took up to 7.2 s under load).
- **Every corner of the narrowed box** (64 scenarios, each lever at its low or high end, CP-SAT from greedy, load 16.7-64.0) states a
  gap: 37 OPTIMAL, 21 HEURISTIC (gaps up to 62.5%), 6 FEASIBLE (0.07-47.4%). All 64 returned within 10 s, slowest 8.60 s. The 11.28 s
  corner of the previous run (N 1 × promise 8 × multiplier 1.0 × capacity 0.5× × capture 1.5× × density 2) took 8.11 s. Some kept-greedy
  gaps are wide because the capacity bound is loose, not because greedy's plan is poor: the widest, 62.5%, is N 1 × promise 8 ×
  multiplier 1.0 × capacity 2× × capture 1.5× × density 0, where nothing binds. 9 corners are above 10%, 8 of them at capacity 0.5×.
  The earlier run (budget 9 s) had 42 OPTIMAL, 16 HEURISTIC and 6 FEASIBLE and one 11.28 s plan; why more corners now end
  HEURISTIC (lower budget, heavier load, or both) was not isolated.
- **The brief's and CLAUDE.md's ≤ 10 s wording** now says what is measured: any scenario in the lever ranges, every metric
  included, its gap stated, measured on 04-plan's grid with the load printed (the last run was under load). It was "a new plan returns in ≤ 10 s" (brief) and
  "for the default scenario" (CLAUDE.md).
- **Ruled out:** serving CP-SAT on its own (not reliably never worse, can return UNKNOWN); keeping promise 18 before the fixes
  (not repeatable within 10 s with a meaningful gap); a joint promise × multiplier limit on the scenario (the size cap covers it);
  a tighter bound from a second solve (no time left in the budget).

## 2026-11-02: plan() edge contract: slow traffic clamped, an oversized model not built, HEURISTIC for greedy's plan, no infinite gap (#33)

- **Slow-traffic coverage is `min(slow-traffic walk, demand covered)` for every method.** A time-limited (FEASIBLE) CP-SAT plan
  can cover less than the nearest-first walk of its stores does (seen: covered 17,880, slow-traffic 17,899), which read as
  coverage rising when traffic slows. Greedy and OPTIMAL plans already satisfied it, so the clamp changes only plans that broke it.
  Ruled out: evaluating both figures with one assignment policy, and leaving the exception documented.
- **A CP-SAT model with more than `MODEL_PAIR_CAP` = 200,000 capacity-bound pairs is not built.** The build is a Python loop
  outside the solver's time limit. Measured on the full area: 21-23 microseconds a pair (14,256 pairs 0.4 s; 247,000 5.5 s;
  264,753 5.7 s; 624,601 14.5 s), so the cap is about 4.5 s of the then 9 s budget (8 s since #34); the default scenario has 20 pairs. The pairs are
  counted vectorised after greedy, before the loop. Over the cap, `cpsat-from-greedy` returns greedy's plan (status
  `HEURISTIC`, bound and gap None) and `cpsat` returns the UNKNOWN plan of the entry below. Ruled out: narrowing the lever ranges
  to dodge the corner (the ranges stay as decided).
- **`status` `HEURISTIC` means greedy's plan, whichever method returned it.** `cpsat-from-greedy` keeps greedy's plan when the
  solver finds nothing, finds less, or the model is over the cap; the method stays `cpsat-from-greedy` and the bound is the
  solver's if it found a solution. `FEASIBLE` now means only CP-SAT's own plan, stopped early, so the service can tell the two apart.
- **`gap` is None, not infinite, for a zero objective under a positive bound** (JSON has no infinity).
- **`Scenario` coerces numeric levers in one place.** Float levers must be real numbers (no bool, `np.bool_` or string) and are
  stored as plain floats with -0.0 as 0.0; whole levers keep the whole-number rule.
- **CP-SAT keeps 8 workers.** Under a wall-clock limit a FEASIBLE plan can differ run to run; OPTIMAL plans are the same.
  The benchmark (#30) notes this in its table. Ruled out: 1 worker, which would be reproducible but solve far less in the budget.
- **`spotcheck` keeps its own copy of the frozen 1.4 multiplier** (pinned equal to `explore.MULTIPLIER` by a test), so importing
  it no longer loads `explore` and ortools.

## 2026-11-02: CP-SAT on its own with no plan in the budget returns an UNKNOWN plan (#27, #33)

- **`plan(..., "cpsat")` returns a plan with status `UNKNOWN` when CP-SAT finds no solution in the budget.** The plan has no
  new sites, and its metrics are the existing network's alone; objective, bound and gap are None. Before, it raised
  `RuntimeError`. Every method now returns a plan, as #27 asks. The benchmark (#30) and the stage 3 service read the failure
  from the status instead of catching an exception. CP-SAT from greedy is unchanged: with no solution it keeps greedy's plan.
- **Ruled out:** falling back to greedy's plan for CP-SAT on its own, because the benchmark could then not tell "CP-SAT alone
  found nothing" from "CP-SAT matched greedy".
- **Left open (#33):** a FEASIBLE CP-SAT plan can show slow-traffic coverage above demand covered. Settled in the entry above.

## 2026-11-01: Competitor density moves demand covered one way only while capacity is slack (#29)

- **A denser competitor never raises demand covered while no store is at capacity; when capacity binds, it can.**
  A hex goes wholly to one store and a store cannot exceed its capacity. A hex the competitor reaches gives the operator
  half its demand (ADR 0001), and half a hex can fit in a store's spare capacity where the whole did not (two hexes of
  0.6 × capacity: one served alone; 0.6 + 0.3 once the competitor halves one). This is a property of the model, not of
  greedy: an exact solve has it too. The tests check the one-way move with capacity slack and pin the exception with a
  hand-sized case.
- On the full area, demand covered falls at every density step for N 1, 10 and 20 at capacity 0.5× and 1×
  (default scenario: 44,698 orders a day at 0×, 39,360 at 1×, 34,802 at 2×), so the lever reads one way in practice.
- Qualifies "so the lever moves results monotonically" in the stage 2 scope entry below. Rules out splitting a hex across
  stores to restore monotonicity (a model change, not this lever's).

## 2026-11-01: Plan (stage 2) scope

- **The default congestion multiplier becomes 1.8** (the spot check's implied median, 20 routes, 30 Oct evening,
  labelled with that caveat); the range widens to 1.0-2.5. 1.4 was an unmeasured guess, and a promise is judged at the
  peak. The travel-time table already keeps pairs to 17 free-flow min, so nothing is rebuilt. Rules out keeping 1.4
  as the default.
- **The synthetic network is 57 stores, the operator and one competitor.** 57 is the area's demand over the orders per
  store per day, which equals the NCR store count times the area's population share (the capture share is calibrated
  on the same figures); it is computed, not hard-coded. The split follows two verified reported store counts: the
  operator takes the market leader's, the competitor the next largest brand's. Three competitors move to Later.
- **Competitor density scales the competitor's store count, 0×-2×**, with the operator fixed and placement nested
  (a denser network keeps the sparser one's stores), so the lever moves results monotonically.
- **The ≤ 10 s rule covers every scenario in the lever ranges**, the plan's gap stated, not only the default. Ranges:
  N 1-20, capacity 0.5×-2× the default, capture share 0.5×-1.5×, promise 8-20. A range that misses (over 10 s, or a
  plan worse than greedy) is narrowed and logged, not a blocker.
- **Every plan metric is computed inside the 10 s**, adding households covered and slow-traffic coverage (the same
  stores at 1.25× the scenario's multiplier: relative, so it means the same at every setting). The CP-SAT plan's
  metrics come from its own assignment, not a second exact solve (today's `evaluate` takes 92 s).
- **Greedy is a benchmark, not served. Three methods are benchmarked** (greedy, CP-SAT on its own, CP-SAT from the
  greedy plan), which separates greedy's quality from what CP-SAT adds. The service runs CP-SAT from greedy unless
  CP-SAT on its own is never worse on demand covered and is faster.
- **Capture share stays one value for every hex**; urban or rural variation goes to Later. No ADR: each of these is a
  lever or a configuration, cheap to reverse.

## 2026-10-31: Demand and reach (stage 1) results: spot-check error and stage close (#18)

- **Res 9 and X = 30 stand.** The full area has 4,859 hexes and 1,458 candidate sites, with 59,855 default-scenario
  pairs. Both tables build with `catchment-build`.
- **Solve time.** The default scenario (N = 10) returns a plan within 10 s using the tighter capacity row, with its gap
  stated. On a loaded machine the median was 9.6 s with a 16.8% gap on the placeholder network. A network sized to the
  area (57 stores) is proven optimal in 5.3 s. Details are in the entry below.
- **Spot-check error** (`03-area`, 20 routes from `docs/spot-check.csv`). The routes were looked up in Google Maps'
  two-wheeler mode with "Leave now" on Friday 30 October 2026, 19:00-19:07, so the times are live evening-peak
  estimates, not a typical range.
  - The app took a median of 1.28× the modelled time (free-flow × 1.4): 25th-75th percentile 1.17-1.54, range 0.97 to
    2.65. It was slower than the model on 19 of 20 routes, by a median of 3.7 min.
  - The worst routes are the two shortest (2.65 and 2.20). Whole-minute app times weigh most on them.
- **Implied multiplier: about 1.8 (median 1.79; 25th-75th percentile 1.64-2.16) against the 1.4 default.** It is
  proportional, not a fixed overhead on short trips (fit: app ≈ 0.75 + 1.82 × free-flow min). At 1.8, the default
  promise reaches 3.9 free-flow minutes instead of 5.0.
  - **Not changed here:** whether the evening-peak figure should become the default, or a labelled peak setting of the
    lever, is the planner's decision.
  - One evening's live estimates are thin evidence for either. 1.8 is already inside the lever's 1.0-2.0 range.
- **The former bad snaps no longer stand out as a group.** Their median ratio is 1.33, against 1.28 for the other 15
  routes, and they rank 1, 7, 9, 14 and 16 of 20.
  - Route 1 (2.97 free-flow min, 11 in the app) is the worst route, so one snap may still be wrong.
  - One route does not justify a new snapping rule. The second-road rule stands (#20).
  - The draw is stratified by free-flow band, not by place, so it did not test outskirts hexes. The 200 m reach
    for hex centres (#20) stays open.

## 2026-10-30: Full-area solve time measured (#15)

**The default scenario (promise 10, multiplier 1.4, capacity 2,364, N = 10) returns a plan within 10 s on the full area
with a tighter capacity row, its gap to the bound stated. Res 9 and X = 30 stand.** Measured on the real full-area
tables (4,859 hexes, 1,458 candidate sites, 59,855 default-scenario pairs). The per-run tables, the X cuts, res 8 and
the load of each run are in `notebooks/03-area.ipynb`.

- **The 10 s bar (the planner, 2026-10-30):** a plan is returned within 10 s with its proven gap to the bound stated;
  proven optimality is not required.
- **The tighter capacity row.** For each constrained new site the row becomes `Σ_h share_h x_{s,h} ≤ cap · y_s`
  (existing operator stores keep `≤ cap`). It is valid (the optimum is unchanged) and moves the root bound on the
  placeholder network from 33,432 to 28,292. The 0.5 model as written missed the bar there at every setting the ticket
  allows (60 s, unproven, 18.3% gap; X = 20, 10, 5 and res 8 too): capacity binds on the area (largest catchment 5,266
  orders a day against 2,364), which the slice did not show.
- **The time limit is a build-plus-solve budget:** CP-SAT gets `SOLVE_LIMIT_S` (9 s) minus the build time. A fixed 9 s
  solver limit took up to 10.10 s in total at a load of 38 to 54, once the build grew to about 1 s.
- **Measured:** all nine default-scenario runs returned in at most 9.7 s. The sized network (57 stores) and res 8 were
  proven optimal (5.3 s and 2.2 s). The placeholder network (3/4/3) ended 16.8% from its bound (median; 16.3% to 23.9%),
  FEASIBLE. That gap is load-sensitive (10% to 17% over four executions, 72% at a load of 26 to 48) and should be
  re-measured on a quiet machine; the time did not vary that way. Nothing was measured on an idle machine.
- **Open, for stage 2:** binding capacity below the default (a capacity of 1,000 gets no usable plan in 9 s), the slow
  `evaluate` (92 s for a good plan's stores), and moving the tighter model into the package. Stage 2's network
  generator should size store counts to the area's orders (about 57 stores): that alone was proven optimal in 5.3 s.

## 2026-10-29: Second-road rule kept after classifying the residual out-and-back (#20)

- **Kept as it is:** nearest hit within 100 m lying more than 5 m across the first (`SECOND_ROAD_MAX_M`,
  `SECOND_ROAD_GAP_M`). No threshold changes.
- **Why** (`03-area`, the same 200 short slice pairs, seed 42; road class and one-way from the OSM ways under each
  snap): of the 19 pairs still riding more than 300 m out and back at an end, none lacks a second road. 11 snap to a
  two-way road (10 a residential or service lane), not a divided road: in 9 the other snap loops too (the lane network
  round a block), and in 2 it does not loop but is slower. No second-road rule reaches them. 4 are paired one-way
  roads where both carriageways loop; 4 took a second road that is not the far carriageway. The largest cause (11) is
  out of a second-road rule's reach; of the 8 it could reach, neither cause dominates.
- **The two cheap fixes, measured:** preferring a hit with the first road's name gives 18 of 200 (9.0%); it changes
  one pair's route (Mehrauli-Gurgaon Road, where the rule took a one-way slip at 8 m over the far carriageway at 9 m).
  A 200 m reach for hex centres changes no pair: 98.2% of sample hexes already have a second road within 100 m. Over
  the area, 781 of the 1,595 hex centres without one would gain one; they are probably on the outskirts (not checked),
  outside this sample, so their effect is unmeasured. One pair in 200 does not justify a rule change, and no table
  was rebuilt, so there is no table-size change to report.
- **What decides whether 9.5% matters** is the spot check (#16-#18), not more snapping rules. Neither variant is
  adopted on this evidence; the 200 m reach could be revisited if the spot check finds outskirts hexes wrong. A fix
  for the lane-network loops would need something other than a second road (more snaps per point, or road class from
  OSM in the build); not tried.

## 2026-10-29: Fastest-of-four snapping, measured (#14)

- **"Second road" is defined by geometry, not by OSRM's two nearest hits.** `/nearest?number=2` returns two segments
  of the same carriageway, and OSRM reports one-way segments' nodes as `[x, x]`, so grouping hits by name and shared
  node fails on exactly the divided roads at issue. The second road is the nearest of 20 hits within 100 m that lies
  more than 5 m from the first snap along the line from the point to that snap (a parallel carriageway lies along it,
  the next segment of the same one across it); with none, the nearest road repeats. Both numbers are labelled
  assumptions. 96.7% of candidate sites and 67.2% of hex centres get a distinct second road.
- **Effect on the slice** (`03-area`, like-for-like one-snap build in the same session): no pair got slower;
  three quarters moved, but by a median of 0.25 min (90th percentile 1.18, max 11.2). 3,711 pairs newly fall within
  the default scenario's 5.0 free-flow minutes. On 200 short pairs (seed 42), out-and-back at an endpoint (over 300 m)
  drops from 14.5% to 9.5%, mostly at the candidate end (14 to 6); the hex end barely moves (16 to 13). The fix halves
  the problem rather than removing it; the spot check will show whether the rest matters.
- **Effect on the area** (res 9, X 30): 1,137,695 → 1,187,469 pairs within 17 min (+4.4%; 3.69 → 3.82 MB on disk),
  default-scenario pairs +19%. `build_reach` 59 → 159 s with OSRM already serving; `catchment-build reach` 179 s wall,
  peak RSS 505 MB, `osrm-routed` peak 410 MB, so the build fits 8 GB with a wide margin. Rules out leaving
  far-carriageway snaps as a measured caveat only.

## 2026-10-29: NCR population is WUP 2025's 30.2 M, not WUP2018's 34.7 M

- **Adopted, verified at source:** UN DESA, World Urbanization Prospects: The 2025 Revision, File 21
  (`WUP2025-F21-DEGURBA-Cities_Pop.xlsx`, POP/DB/WUP/Rev.2025/F21), India, City_Code 8364 "New Delhi", 2025 column:
  30,222.405 thousand. Downloaded from https://population.un.org/wup/assets/Download/Cities/ on 2026-10-29. File 19
  (100 largest cities by time) gives the same figure. WUP2018 is superseded, so its 34.7 M goes.
- **The definition changed.** WUP2018 counted the urban agglomeration (its footnote: including Faridabad, Gurgaon and
  Ghaziabad). WUP 2025 counts the Degree of Urbanisation city: contiguous 1 km² cells of at least 1,500 people per km²,
  2,101 km² of land in 2025 (File 19). Gurgaon, Faridabad, Ghaziabad and Noida have no separate entry in File 21, so they fall
  inside "New Delhi". Greater Noida (0.33 M), Rasoi (0.70 M, north of Delhi) and Bhondsi (55 k, south of Gurugram) are
  separate cities. This is an inference from the file; the UN publishes no boundary per city here. So the two figures
  cover about the same towns, counted by a different rule.
- **Effect: the calibration target, the default capture share and the default demand all rise by 34.7 / 30.2,
  about 15%.** Calibration target 0.082 → 0.094 orders per household per day; default capture share
  0.070 → 0.080; area demand at res 9 78,092 → 89,728 orders a day (`catchment-build demand --force`, re-run
  2026-10-29). The area's households and `ORDERS_PER_STORE_DAY` don't change, so the default capacity (2,364) doesn't
  either. A default catchment's demand rises from 889-1,411 to about 1,020-1,620 orders a day, and the largest on the
  slice from 1,981 to about 2,276. That is still under capacity, so "capacity never binds at the default" stands, but
  only by about 4%: a small further rise in demand would make capacity bind, and binding capacity is the slow CP-SAT
  case.
- Rules out keeping WUP2018 as the default. The `00-demand` notebook stays frozen at 34.7 M as the 0.5 record.

## 2026-10-29: Demand and reach (stage 1) design

- **One command, `catchment-build [demand reach] [--res 9] [--x-pct 30] [--force]`**, like `catchment-fetch`.
  Outputs are named by what they depend on: `data/demand-r9.parquet`, `data/candidates-r9-x30.parquet`,
  `data/table-r9-x30.parquet`. The defaults are the 0.5 results; the flags exist for the fallback (cut X, then res).
- **The demand table stores the factors and the default demand**: population, households, affluence multiplier, and
  demand at the default capture share, with that share stored alongside so a plan can rescale when the lever moves.
- **Labelled assumptions live in one module** (household size, multiplier bounds, the four calibration inputs,
  pick-and-pack, the 17 min cap), each with source, date and status, so notebooks and later the UI show the same table.
- **The demand build runs natively at `--res`** (pixels binned, radiance sampled and ranked, capture share calibrated at
  that resolution), not as 00-demand's sum of res-9 children. Res 9 reproduces 00-demand exactly; res 8 drops the
  population of res-8 hexes whose centre is outside the area (941,794 households against 955,163), so res-8 and res-9
  totals are not comparable. Res 8 is only the solve-time fallback.
- **The assumptions module also holds 02-plan's table** (default scenario, N, capacity, placeholder network, solver),
  copied as the 0.5 values; stage 2 reads them from there.
- **OSRM moves to a top-level `osrm/`** (`osrm.sh`, `two-wheeler.lua`); `catchment-build reach` builds the graph if
  missing, serves it and stops it.
- **Far-carriageway snaps are fixed, not just measured:** candidate sites and hex centres each snap to their two
  nearest roads, and a pair keeps the fastest of the four times (about 4× the OSRM queries). Measured before and after
  on the slice.
- **The write-up is one notebook, `03-area`:** the committed area demand map, the snapping before and after, the
  spot check, and the full-area CP-SAT solve time against the ≤ 10 s bar (the 0.5 model, run once; a miss cuts X).
- **Spot check:** about 20 routes from the table across 2-17 min, some with known bad snaps, timed in Google Maps'
  two-wheeler mode on a weekday at 7-8 pm and compared with free-flow × 1.4; the multiplier the app implies is reported.
  The per-route times are committed in `docs/spot-check.csv` ([ADR 0002](adr/0002-spot-check-times-in-repo.md)).
- **`00-demand` and `01-reach` stay frozen** as the 0.5 record; they are not rewritten against the package.
- **No GUI before stage 3.** Inputs are flags and the assumptions module; the web map with levers stays in stage 3.
- **Tests:** the pure steps are unit-tested; OSRM sits behind a small client that tests replace with a fake, plus one
  integration test against real OSRM that skips when Docker is down.
- **One time-boxed try at the WUP 2025 population** at source before the area demand map is committed; if not found,
  34.7 M and its caveat stand.

## 2026-10-29: Explore (stage 0.5) results: hex resolution and candidate site rule

The three notebooks ran the chain on the slice (`00-demand`, `01-reach`, `02-plan`); numbers below are from those
runs, on the placeholder network, at the default scenario (promise 10, multiplier 1.4, capacity 2,364 orders a day).

- **Hex resolution: H3 res 9.** It is the finest tried, and it fits the budget. Res 8 is cheaper but its candidate sites
  reach only 96.0% of the slice's demand at the default scenario; a res-8 hex (about 0.74 km²) is too coarse for a
  catchment of about 5 free-flow minutes. Res 9, full area, extrapolated from the slice: about 1.40 M table pairs within
  17 min (17 MB in memory) and about 54 k default-scenario pairs; CP-SAT at N = 10 is extrapolated to 3.1-5.6 s (other
  runs 1.9-11.3 s; the fit is noisy) and the slice copied three times, at the full area's pair count, solved in 1.2 s.
  Res 8 would take about 0.04 s. The time grows with N: three slice copies at N = 30 took 19 s. The ≤ 10 s bar looks
  reachable but is not proven until stage 1 builds the full-area table (measured: the 0.5 model misses on the
  placeholder network at every X and at res 8, and a tighter capacity row returns a plan within 10 s with the gap
  stated; see "Full-area solve time measured (#15)" above). Rules out res 8 unless that measurement misses the bar even
  after cutting X; the 0.5 model did, so res 8 was tried and missed too, and the tighter model makes it unnecessary.
- **Candidate sites: one per hex, the top 30% of the area's hexes by Overture places count**, the hex centre snapped
  to the nearest road (ties by demand; hexes with no places never qualify). 1,458 sites in the area, 554 in the slice.
  X = 30% is the smallest value in the grid whose slice candidates reach ≥ 99% of the slice's demand (99.3%). It was
  not cut for the solve budget, since the budget holds at 30%. If stage 1's measured solve misses 10 s, cut X before
  the resolution: X = 10% reaches 96.0% with a third of the pairs (extrapolated 1.5-1.8 s).
- **CP-SAT formulation: assignment variables only for sites whose catchment can exceed capacity.** The plain model
  (a variable per site × hex pair) stalls with the trivial bound (9-22% below the optimum after 20 s). The used model
  has the same optimum (checked where capacity binds: res 8 at 800 orders a day, both models proven optimal at the same
  value) and solves the slice to proven optimality in 0.4 s (N = 3) and 1.3 s (N = 10). At the default
  capacity no site binds (largest catchment demand 1,981 against 2,364), so the default scenario is maximum coverage.
  **Capacity that binds is slow**: at 1,000 orders a day, CP-SAT is still 38% from its bound after 20 s. The capacity
  lever's range, or a faster model for that case, needs a decision before stage 3.
- **CP-SAT against greedy:** they tie on the main network at N = 3 (5,599 orders a day against 1,090 for the existing
  stores alone). Across ten network placements CP-SAT wins 2 and ties 8 (mean +0.7%, best +4.6%), and on the slice it
  gains 0.6% at N = 5 and 3.2% at N = 10. Greedy is a strong baseline for a few stores; the gap grows with N.
- **Correction: a default-scenario catchment is 4.4-6.2 km²** (40-57 res-9 hexes, 889-1,411 orders a day of demand),
  not the ~17 km² the slice entry below assumed: the promise leaves 5 free-flow minutes after the multiplier and the
  pick-and-pack allowance. The slice still holds many catchments, so the slice stands.
- **Open, carried into stages 1-2:** about one short pair in seven is inflated by snapping onto the wrong
  carriageway (`01-reach`). Sized by orders, the placeholder network leaves 11,105 of the slice's 16,523 orders a day on
  hexes no brand reaches; the stage 2 generator must choose whether store counts follow orders or reach.
- **The defaults rest on four verified figures, with caveats.** The capture share, `ORDERS_PER_STORE_DAY` (about
  1,576) and so the default capacity come from the Blinkit order and store counts, the NCR dark-store count and the
  NCR population. All four were verified against primary sources on 2026-10-29 with no change in value, so the numbers
  and "capacity never binds at the default" stand. Caveats remain: the population was a WUP2018 projection, since
  replaced by WUP 2025's 30.2 M (see the population entry above; the numbers in this entry are at 34.7 M); Savills'
  count is a best-effort estimate as of Oct 2025; Blinkit's orders per store stand in for every brand.

## 2026-10-29: Explore (stage 0.5) model and slice

- **Slice: about 80 km², old Gurugram (sectors 4-14, Sadar) to Golf Course Road / Sohna Road.** A 10-min catchment
  is about 17 km² (wrong: 4.4-6.2 km², see the results entry above), so "a few km²" would make every site reach
  every hex and give nothing to extrapolate from. Rules out a slice smaller than several catchments.
- **Demand = households × affluence multiplier × capture share.** Households = population ÷ one
  stated household size, since capture share is per household and the brief reports households
  covered. The affluence multiplier is VIIRS radiance ranked within the area and mapped to labelled
  bounds (about 0.5-1.5); Overture places feed candidate sites, not demand, so commercial brightness
  isn't counted twice. Calibration to reported orders per store per day sets only the *default*
  capture share; the lever moves from there.
- **The synthetic network holds every brand, the operator included.** The operator's existing stores
  are one synthetic brand; planner-supplied stores move to Later ([cuts](cuts.md)).
- **Shared catchments split equally by brand; the solver assigns each hex to one own store within
  capacity** ([ADR 0001](adr/0001-demand-split-by-brand.md)).
- **Lever ranges:** promise 8-20 min (default 10), pick-and-pack allowance 3 min fixed, congestion
  multiplier 1.0-2.0 (default 1.4), so travel-time pairs are kept up to 17 min free-flow. Default
  capacity is 1.5 × the calibrated average orders per store per day. The default scenario for the
  ≤ 10 s bar is the full area with N = 10 new stores; the slice uses N = 3.
- **Reach:** OSRM in Docker (arm64) with an edited `car.lua` (two-wheeler speeds, `motorcycle=*`
  access; every edit listed as an assumption), since OSRM has no two-wheeler profile. The OSM extract is
  the Geofabrik northern zone, clipped with osmium-tool to the area plus 5 km; hexes and candidate
  sites stay inside the area.
- **Hex resolution:** the finest whose full-area table and solve fit the budget; res 9 first, res 8
  as fallback. **Candidate sites:** one per hex, top X% of hexes by Overture places count, X tuned to
  the same budget.
- **In 0.5, the synthetic network is placed inline in `02-plan`** (demand-weighted, fixed seed, counts
  labelled placeholders); the generator stays in stage 2.

## 2026-10-29: Area boundary and data products (stage 0)

- **The area is the Gurgaon tehsil (OSM rel 10398244) plus South Delhi district (rel 21181223)**,
  528 km², committed as `area/gurugram-south-delhi.geojson`. Gurugram district (1,253 km²) is mostly
  rural and would grow the travel-time table and the solve for little demand. Rules out Sohna, Manesar,
  Pataudi and Farrukhnagar until the NCR scaling stage.
- **Population: WorldPop 2025 constrained 100 m (R2025A)**, the most current estimate, over the 2020
  product.
- **Night lights: NASA Black Marble VNP46A4 (annual, 2025) instead of EOG annual VNL.** EOG made
  scripted downloads paid-only in June 2026; Black Marble is the same VIIRS sensor, free with a LAADS
  token. Rules out the EOG VNL product unless a subscription is bought.
- **Overture release pinned** (2026-10-21.0) so a re-fetch gives the same features.

## 2026-10-28: Explore on a slice before the pipeline

- **A "0.5 Explore" step, to 8 Nov:** notebooks `00-demand`, `01-reach` and `02-plan` run end to end
  on a small slice of Gurugram before any stage is formalised, as in the sibling projects. The risky
  parts are late in the chain (OSRM within 8 GB, travel-time table size, CP-SAT ≤ 10 s), and the hex
  resolution and candidate site rule should be chosen with the solver's limits in view.
- **Stage 0 shrinks to setup and fetch; demand and reach are formalised together** in stage 1 (to
  13 Nov). Stages 2 and 3 keep their dates. Rules out formalising one stage before the next has been
  tried; the 25 Nov date does not move.

## 2026-10-28: Initial scope

- **The core is a planning tool, not an ops simulator.** The user is a network planner deciding where
  stores go; the simulator (dispatch, batching, routing) is a later stage that stress-tests a plan.
- **First area: Gurugram + South Delhi.** Mixes a dense old city with high-rise sectors, so the
  trade-offs show; small enough to iterate fast. All of NCR is a later scaling stage.
- **Open data only; competitors are synthetic.** OSM and Overture barely have dark stores (5 and 11
  named features in the NCR box, see [data-sources.md](data-sources.md)); Google Places content can't
  be stored; scraping operator apps breaks their terms.
- **Demand is a transparent model**, not a forecast: population × affluence proxy × capture share,
  scaled to publicly reported orders per store per day. No ML forecasting without real order data
  to validate it against.
- **Travel times: OSRM two-wheeler profile, precomputed**, with a congestion multiplier as a lever and
  a hand spot-check of ~20 routes whose error is reported. OSRM is not hosted.
- **Plans are solved on request** (FastAPI + CP-SAT, ≤ 10 s), not precomputed, because changing a
  lever and getting a new plan is the product.
- **Benchmark against a greedy baseline** in the first cut; the arXiv 2312.11494 heuristic moves to
  Later (time budget, see [cuts.md](cuts.md)).
