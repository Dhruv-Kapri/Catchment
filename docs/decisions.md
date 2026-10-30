# Decision log

Newest first. One entry per decision: what was decided, why, and what it rules out. Big or
hard-to-reverse decisions also get an ADR in `docs/adr/` (created when the first one is needed).

## 2026-10-30: Full-area solve time measured (#15)

**The default scenario (promise 10, multiplier 1.4, capacity 2,364, N = 10) returns a plan within 10 s on the full area
with a tighter capacity row, gap stated.** The 0.5 model as written misses on the placeholder network at every setting
the ticket allows, measured below. Res 9 and X = 30 stand. Measured in `03-area` on the real full-area tables (4,859
hexes, 1,458 candidate sites, 59,855 default-scenario pairs).

- **Decision (the planner, 2026-10-30): the 10 s bar means a plan is returned within 10 s with its proven gap to the
  bound stated; proven optimality is not required.** The model stays inline in `03-area`; stage 2 still moves it into
  the package.
- **The tighter model.** For each constrained new site the capacity row becomes `Σ_h share_h x_{s,h} ≤ cap · y_s`;
  existing operator stores keep `≤ cap` and `x ≤ y` stays. It is valid (a closed site serves nothing, so the optimum is
  unchanged) and it moves the root bound on the main network from 33,432 to 28,292, within 0.1% of the best plans found.
  With a fixed 9 s solver limit all nine default-scenario runs returned in at most 9.7 s: the placeholder network at res
  9 in a median of 9.6 s (9.5 to 9.7), FEASIBLE, plan 24,329 against a bound of 28,292, a gap of 16.8% (16.3% to 23.9%
  over three runs); the area-sized network (57 stores) in 5.3 s (4.3 to 5.6) and res 8 in 2.2 s (1.8 to 2.2), both
  OPTIMAL (gap 0) with objectives equal to the 0.5 model's (30,401.05 and 26,619.37, asserted). **The placeholder
  network's gap is loose and load-sensitive.** The runs were on a loaded machine (another job held about three cores;
  load average 6 to 17). A separate experiment at a 10 s limit and a load of 12 to 14 got 28,283 against the same bound
  (0.03%), and the 0.5 model's 60 s plan (28,266) beats this 9 s one. Four executions of the cells gave median gaps of
  10% to 17%. The likely cause is CPU contention: in a diagnostic run (2026-10-30) with another project's job holding
  four of the eight cores (load 10 to 17), the tighter model did not even reach its root bound in 9 s (bound 34,478, not
  28,292; plans 21,161 to 23,895, 30% to 60% from the bound), and 4 workers did no better than 8. The plan's quality in
  9 s depends on the CPU free; the gap should be re-measured on a quiet machine.
- **The time limit became a budget.** A run at a load of 38 to 54 (2026-10-30) with the fixed 9 s solver limit took up
  to 10.10 s in total (the build grew to about 1 s), over the bar. The solver now gets `SOLVE_LIMIT_S` (9 s) minus the
  build time, so build plus solve stays under 10 s by construction: at a load of 26 to 48 all nine default-scenario runs
  took at most 9.10 s. The runs quoted above used the fixed limit and were not repeated on a quiet machine. At that load
  the plans were poor (placeholder network median gap 72%, the sized network 0.4%, res 8 proven optimal), and the
  capacity-1,000 stress case found no plan at all.
- **`evaluate` check:** run 1's chosen stores score 24,388.22 with a 120 s limit, proven optimal in 5.3 s, 58.86 orders
  a day (0.24%) above the solver's objective of 24,329.36. It is consistent (the objective is one feasible assignment)
  but not equal: the objective of a plan cut off at 9 s understates what its stores serve. `evaluate` took 92 s for the
  0.5 model's best stores in the experiment.
- **Stress case, not a default scenario:** the main network at a capacity of 1,000 orders a day gets no usable plan in
  9 s (objective 10,632 against a bound of 60,320, 10.65 s in total).

The 0.5 model's measurements follow, as the record of the miss.

- **0.5 model, main run, the placeholder network** (3 operator, 4 Competitor A, 3 Competitor B, seed 2026, X = 30):
  median 60.3 s of three (60.3 to 60.6), build 0.2 s plus solve 60.1 s. Status FEASIBLE: it stopped at the 60 s limit,
  with the best plan 28,266 orders a day against a bound of 33,432 (18.3% gap). Over the bar by a factor of six or more.
  Its first run started at a load of 3.3 and took as long as the others, so the load does not explain the miss.
- **0.5 model, sensitivity, a network sized to the area** (57 stores, 17/23/17, same seed): OPTIMAL, median 6.1 s (5.8
  to 6.4) at a load of 11 to 13, objective 30,401.05, checked equal to `evaluate`'s score for the chosen stores (0.4 s).
  **Within the bar**, but it depends on the load: the same cell took 14 to 42 s at loads of 17 to 40 in earlier runs
  (medians 14.3, 21.0 and 34.8 s). So the bar is met with an area-sized network when the machine is not heavily loaded.
- **Cause: capacity binds on the area at the default.** The largest catchment holds 5,266 orders a day against a
  capacity of 2,364, and sites above it need assignment variables: 123 with the placeholder network, 22 with the sized
  one. 0.5's slice had its largest catchment at 1,981, no constrained site, and maximum coverage; its 3.1-5.6 s
  extrapolation (1.2 s for three slice copies) was right for that case and does not carry to the area. The same network
  with capacity effectively infinite solves to optimality in 0.8 s (diagnostic row). This is the 0.5 open point
  "capacity that binds is slow", now at the default scenario. `evaluate` is slow for the same reason: for the main run's
  stores its first solve did not prove optimality in 30 s, so that check was skipped there and for the X cuts (it took
  0.4 s on the sized network's stores and 0.3 s on res 8's, and matched the objective in both).
- **Cutting X did not help the 0.5 model on the placeholder network.** The X% sets are the X = 30 table filtered by rank
  (equivalent to `catchment-build reach --x-pct X`, no OSRM needed); the network stays as placed at X = 30. X = 20, 10
  and 5 (972, 486 and 243 sites) all ran to the limit unproven (medians 60.2, 60.2, 60.1 s; 91, 53 and 30 constrained
  sites; bound still 9.5% above the best plan at X = 5), at a coverage of 88.3%, 79.8% and 71.2% of the area's demand
  against 93.5% at X = 30.
- **Res 8, the last resort, misses too, but proven.** `catchment-build reach --res 8` at X = 30 gives 697 hexes, 210
  sites and 1,194 default-scenario pairs; coverage 78.9% (14.6 points below res 9), 18 constrained sites, largest
  catchment 4,852 against 2,364. The main network, placed by the same rule over the res-8 candidates, is OPTIMAL in a
  median of 25.5 s (24.6 to 27.8), plan 26,619.37 equal to its bound and to `evaluate`'s score, on only 1,140 pairs:
  size is not what makes it slow. An earlier run at a higher load stopped at the 60 s limit (10.1% gap). Res-8 numbers
  are not comparable with res 9's: the native res-8 demand build drops hexes whose centre is outside the area (941,794
  households against 955,163, 1.4% lower; see "Demand and reach (stage 1) design"). The 0.5 entry's 0.04 s for res 8
  assumed no constrained site.
- **Settings and hardware:** Apple M1, 8 cores, 8 GB, OR-tools 9.15.6755, 8 workers, 60 s limit (9 s for the tighter
  model), solver seed 1. The machine was loaded by parallel jobs: the 1-minute load average was 3 to 23 on 8 cores in
  the final run (11 to 13 for the sized network, 16 to 18 for res 8) and 12 to 40 in earlier ones. Unproven runs also
  vary: the main network's plan was 28,266 here and 27,965 to 28,234 earlier.
- **Open, for stage 2:** binding capacity below the default (the capacity-1,000 stress case) and the slow `evaluate`
  (92 s for a good plan's stores), moving the model, tightened, into the package, and re-measuring the placeholder
  network's gap on a quiet machine. Stage 2's network generator should size store counts to the area's orders (about 57
  stores here): with the 0.5 model that alone met the bar at a moderate load (6.1 s), and with the tighter row it is
  proven optimal in 5.3 s.

## 2026-10-29: Second-road rule kept after classifying the residual out-and-back (#20)

- **Kept as it is:** nearest hit within 100 m lying more than 5 m across the first (`SECOND_ROAD_MAX_M`,
  `SECOND_ROAD_GAP_M`). No threshold changes.
- **Why** (`03-area`, the same 200 short slice pairs, seed 42; road class and one-way from the OSM ways under
  each snap): of the 19 pairs still riding more than 300 m out and back at an end, none lacks a second road. 11 snap
  to a two-way road (10 a residential or service lane), not a divided road: in 9 the other snap loops too (the lane
  network round a block), and in 2 it does not loop but is slower. No second-road rule reaches them. 4 are paired
  one-way roads where both carriageways loop; 4 took a second road that is not the far carriageway. No cause dominates.
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
