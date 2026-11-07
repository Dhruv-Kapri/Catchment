# What was cut, and why

Newest first. Anything removed from the current scope goes here with the reason, so the README never
promises more than exists. "Later" means it is on the [roadmap](roadmap.md) after the first cut.

## 2026-11-05, stage 3 scope

| Cut | Why | Status |
| --- | --- | --- |
| Live public host for `POST /plan` (one small VM or Fly.io) | no free host runs CP-SAT at usable quality (Hugging Face Docker Spaces need a paid plan; fewer cores leave wide gaps); paid compute declined for a demo. The public URL is a static site of plans solved in advance ([ADR 0003](adr/0003-static-demo-on-gh-pages.md)); the live service runs locally | Later |
| Any combination of levers on the public site | the static site carries one lever off its default at a time; pairs mean thousands of plans | Later (pairs of levers) |

## 2026-11-03, stage 2 benchmark (#30)

| Cut | Why | Status |
| --- | --- | --- |
| Promise lever 17-20 min (range 8-20 → 8-16) | at 19-20 CP-SAT finds no plan in the 10 s budget, so no gap can be stated; 17-18 not repeatable (a 10.46 s run, a meaningless bound); see 04-plan and the decision log | Later: re-measure 17-20 now that #33's size cap and the capacity bound (#30) address both failures |

## 2026-10-29, stage 0.5 decisions

| Cut | Why | Status |
| --- | --- | --- |
| Planner-supplied existing stores (upload or place on the map) | time budget; the operator is one brand of the synthetic network instead | Later |

## 2026-10-28, first cut (due 25 Nov)

| Cut | Why | Status |
| --- | --- | --- |
| Real competitor store locations | not in open data; scraping breaks terms; storing Google Places content is forbidden | replaced by the synthetic network |
| ML demand forecasting | no real order data to train or validate it; would be false precision | not planned |
| Ops simulator (dispatch, batching, rider routing) | the planner has to work first; ~28 hours available to 25 Nov | Later |
| All of Delhi NCR | iteration speed; scaling is its own stage with its own measurements | Later |
| arXiv 2312.11494 heuristic as a second baseline | time budget; greedy is the bar for the first cut | Later |
| Hosting OSRM | travel times are precomputed; only the table ships | not planned |
| Store rent, size and real-estate availability | no open data; would be invented numbers | not planned |
