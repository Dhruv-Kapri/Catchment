# catchment

Choosing where a quick-commerce operator should open its next stores, and showing what each choice
wins, loses and takes from the stores already there.

## Space

**Area**:
The region a plan covers, as one committed polygon. First area: Gurugram + South Delhi (the Gurgaon tehsil and South Delhi district in OSM).
_Avoid_: city, region, AOI (in prose)

**Hex**:
One H3 cell at the project's working resolution; the unit demand is counted in.
_Avoid_: cell, tile, grid square

**Candidate site**:
A point where a store could open: a hex with enough commercial activity, snapped to the road network.
Only candidate sites can be chosen.
_Avoid_: location, site (alone), store (before it is chosen)

## Demand

**Demand**:
Expected orders per day from one hex: population × affluence proxy × capture share. A model, never
observed data.
_Avoid_: orders (alone, implies real data), sales, forecast

**Capture share**:
The fraction of a hex's households assumed to order on a given day. A lever.

## Reach

**Travel time**:
Two-wheeler time from a candidate site to a hex centroid, from OSRM on OSM roads, times the
congestion multiplier.
_Avoid_: distance, ETA

**Promise**:
The delivery time in minutes the operator commits to. A hex is reachable from a site if travel time
plus a fixed pick-and-pack allowance is within the promise.
_Avoid_: SLA (in the UI), delivery radius

**Catchment**:
The set of hexes a store can reach within the promise.
_Avoid_: radius, coverage area, polygon (a catchment is not a circle)

**Congestion multiplier**:
A factor applied to free-flow OSRM times to stand in for traffic. A lever, not a traffic model.

## Network

**Store**:
A chosen candidate site, or an existing store, own or competitor.

**Competitor layer**:
Synthetic competitor stores, placed by demand weight, with counts sized from publicly reported
figures (source and date recorded). Not a map of any company's real stores.
_Avoid_: competitor data, real stores

**Capacity**:
The most orders per day a store can serve. Demand beyond it is lost.

**Cannibalisation**:
Demand a new store takes from a store the operator already has, as opposed to demand it wins fresh.

**Shared catchment**:
Hexes reached by more than one store; their demand is split between those stores.

## Planning

**Lever**:
A user-set input: number of new stores, promise, congestion multiplier, capacity, competitor density,
capture share.
_Avoid_: parameter (in the UI), knob

**Scenario**:
One set of lever values.

**Plan**:
The sites chosen for one scenario, with its metrics (demand covered, new vs cannibalised demand per
store, lost demand).
_Avoid_: solution, result, recommendation

**Greedy baseline**:
Adds the site with the largest marginal covered demand, one at a time, until N. The bar CP-SAT has to beat.
