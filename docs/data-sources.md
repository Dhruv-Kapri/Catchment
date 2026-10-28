# Data sources

Facts are marked **Verified** (with date, read from the source or measured) or left unmarked
(unverified). Keep that distinction when adding or changing facts.

## Used

| Data | Use | Licence |
| --- | --- | --- |
| OpenStreetMap (Geofabrik India extract, clipped to the area) | road network for OSRM travel times | ODbL |
| Overture Maps Places | activity and affluence proxy; candidate sites | CDLA-Permissive-2.0 |
| Overture Maps / Google Open Buildings | built-up density | Overture buildings: ODbL; Google Open Buildings: CC BY 4.0 |
| WorldPop (≈100 m population) | base demand | CC BY 4.0 |
| VIIRS night-time lights | affluence proxy | public domain (NOAA/EOG); check the product page |

## Checked and not usable for competitor stores

Operators don't publish store locations, and dark stores have no storefront, so community map data
barely has them.

- **OpenStreetMap. Verified 2026-10-28** (Overpass query, bbox 76.85,28.35 – 77.55,28.95): **5**
  features named Blinkit, Zepto, BigBasket, Instamart, Grofers or Flipkart Minutes in the whole box.
- **Overture Places. Verified 2026-10-28** (`overturemaps download`, same bbox): **382,822** places in
  the box, of which **11** carry one of those names, mostly offices and franchise listings, not stores.
- **Google Places:** the Places API policies forbid pre-fetching, caching or storing content except
  `place_id`, so it cannot become a dataset.
- **Scraping operator apps:** not used (terms of service).

Hence the **synthetic competitor layer** (see [CONTEXT.md](../CONTEXT.md)): stores per brand placed by
demand weight, with counts sized from publicly reported figures. Reported counts vary by source and
date; record the source and date for every number used.

## Not used (yet)

- **Census of India 2011:** too old for current demand. Census 2027 results: availability not checked.
- **Meta Relative Wealth Index:** licence not checked.
