# Product brief

One page. Written before any code; change it only with an entry in [decisions.md](decisions.md).

## User

A **network planner** at a quick-commerce operator, or at a retailer adding fast delivery, who has to
propose where the next stores go in a city they already serve.

## The decision

"We have budget for N more stores in this area. Which sites, and what do we get for them?"

Today this is answered with spreadsheets of catchments drawn as circles, plus local knowledge. Circles
ignore the road network and traffic, and spreadsheets don't show how a new store eats into the orders
of the stores already there.

## What the tool gives them

1. The **demand map**: expected orders per hexagon, with every assumption visible and adjustable.
2. A **plan**: N sites chosen to maximise the demand reached within the delivery promise, respecting
   store capacity and shared catchments.
3. The **trade-offs**, per plan: households covered, the orders each new store wins and how many of
   them it takes from existing stores, and how coverage falls when traffic slows.
4. **Scenarios side by side**: change one lever, see what moves.

## Levers (inputs)

Number of new stores · delivery promise (minutes) · congestion multiplier · store capacity
(orders/day) · competitor density · capture share.

## Success metric

A planner can go from "N more stores" to a defensible plan, with its trade-offs, in **under five
minutes**, and every number in the plan traces back to a stated assumption.

Engineering bars that support it: a new plan returns in **≤ 10 s**; the CP-SAT plan beats the greedy
baseline on covered demand (or the gap is reported honestly); travel-time error against a hand-checked
sample is measured and shown.

## Out of scope for the first cut

See [cuts.md](cuts.md).
