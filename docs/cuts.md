# What was cut, and why

Newest first. Anything removed from the current scope goes here with the reason, so the README never
promises more than exists. "Later" means it is on the [roadmap](roadmap.md) after the first cut.

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
