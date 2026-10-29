# catchment

Choosing where a quick-commerce operator should open its next stores, and showing what each choice
wins, loses and takes from the stores already there.

## Space

**Area**:
The region a plan covers, as one committed polygon. First area: Gurugram + South Delhi (the Gurgaon tehsil and South Delhi district in OSM).
_Avoid_: city, region, AOI (in prose)

**Slice**:
A part of the area, several catchments across, that the Explore notebooks run the whole chain on before
it runs on the full area. First slice: old Gurugram to Golf Course Road.
_Avoid_: sample, test area

**Hex**:
One H3 cell at the project's working resolution; the unit demand is counted in.
_Avoid_: cell, tile, grid square

**Candidate site**:
A point where a store could open: the centre of one of the area's busiest hexes by count of mapped
places, snapped to the road network.
Only candidate sites can be chosen.
_Avoid_: location, site (alone), store (before it is chosen)

## Demand

**Demand**:
Expected orders per day from one hex: households × affluence multiplier × capture share. A model,
never observed data.
_Avoid_: orders (alone, implies real data), sales, forecast

**Households**:
A hex's population divided by one stated household size (a labelled assumption).

**Affluence multiplier**:
A bounded factor per hex from night-time light brightness, ranked within the area; the bounds are a
labelled assumption.
_Avoid_: affluence proxy (in the UI), wealth, income

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

**Brand**:
One quick-commerce operator's app. Customers choose a brand, not a store.

**Operator**:
The brand the planner works for. In the first cut it is one brand of the synthetic network.

**Store**:
A chosen candidate site, or an existing store of the operator or a competitor.

**Synthetic network**:
The existing stores of every brand, the operator's included, placed by demand weight, with counts sized
from publicly reported figures (source and date recorded). Not a map of any company's real stores.
_Avoid_: competitor data, real stores, competitor layer (it holds the operator's stores too)

**Capacity**:
The most orders per day a store can serve. Demand beyond it is lost.

**Shared catchment**:
Hexes reached by more than one brand. Their demand is split equally between the brands that reach them;
within the operator, the plan assigns each hex to one of its stores that reaches it, within capacity.

**Cannibalisation**:
Demand a new store takes from a store the operator already has (a hex that moves from an existing
store to the new one), as opposed to demand it wins fresh.

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
