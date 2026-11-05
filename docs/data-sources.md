# Data sources

Facts are marked **Verified** (with date, read from the source or measured) or left unmarked
(unverified). Keep that distinction when adding or changing facts.

## Used

| Data | Use | Licence |
| --- | --- | --- |
| OpenStreetMap (Geofabrik India extract, clipped to the area) | road network for OSRM travel times | ODbL 1.0, share-alike; credit "© OpenStreetMap contributors". **Verified 2026-11-05** (osmfoundation.org Licence FAQ) |
| Overture Maps Places (release 2026-10-21.0) | activity and affluence proxy; candidate sites | per source, no theme licence: CDLA-Permissive-2.0, Apache 2.0 (Foursquare), CC0 (AllThePlaces); each source's attribution required. **Verified 2026-11-05** (docs.overturemaps.org/attribution, full page, last updated 15 May 2026): "Data from X. Available under CDLA Permissive 2.0" for Meta, Microsoft, PinMeTo, Krick, RenderSEO, DAC, BrightQuery, Birdeye, Uberall and OpenTravel Alliance; "Data from Foursquare. Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0" (transformed to the Overture schema, with a NOTICE.txt); "Data from AllThePlaces. Available under CC0 1.0". Overture's suggested citation: "Overture Maps Foundation, overturemaps.org" |
| Overture Maps buildings (release 2026-10-21.0) / Google Open Buildings | fetched, not used by `src/` (no demand factor reads it) | Overture buildings: ODbL; Google Open Buildings: CC BY 4.0 |
| WorldPop, India 2025 constrained 100 m, R2025A v1 (`ind_pop_2025_CN_100m_R2025A_v1.tif`) | base demand | CC BY 4.0. **Verified 2026-11-05** on the dataset's own page (hub.worldpop.org/geodata/summary?id=73807, India 2025, category "Individual countries 2015-2030 (100m resolution) R2025A v1", an alpha product), whose licence link is hub.worldpop.org/data/licence.txt (CC BY 4.0). DOI 10.5258/SOTON/WP00839. Recommended citation: Bondarenko M., Priyatikanto R., Tejedor-Garavito N., Zhang W., McKeen T., Cunningham A., Woods T., Hilton J., Cihan D., Nosatiuk B., Brinkhoff T., Tatem A., Sorichetta A.. 2025 Constrained estimates of 2015-2030 total number of people per grid square at a resolution of 3 arc (approximately 100m at the equator) R2025A version v1. Global Demographic Data Project - Funded by The Bill and Melinda Gates Foundation (INV-045237). WorldPop - School of Geography and Environmental Science, University of Southampton. DOI:10.5258/SOTON/WP00839 |
| NASA Black Marble VNP46A4 (annual VIIRS night-time lights, collection 5200, 2025, tile h25v06) | affluence proxy | CC0 (most NASA mission data); NASA asks to be cited. **Verified 2026-10-29** (Earthdata data use guidance) |

- **Verified 2026-10-28:** EOG (Colorado School of Mines) scripted access to VIIRS products became
  paid-only in June 2026 (<https://eogdata.mines.edu/products/register/>), hence Black Marble.
- **Verified 2026-10-28:** the WorldPop server advertises `Accept-Ranges: bytes` but ignores `Range`
  and answers 200 with the full body, so windowed reads over HTTP fail; the national file is downloaded
  whole, then clipped.
- **Verified 2026-10-29:** LAADS downloads need a **LAADS DAAC token** (generated on
  ladsweb after logging in); an Earthdata (EDL) token was redirected to the LAADS login for every file.
  The WorldPop server delivered at 35-85 KB/s (the national file took about 2 hours).
- **Verified 2026-10-29** (real tile): `NearNadir_Composite_Snow_Free` is float32 in nW/(cm² sr),
  `_FillValue` -999.9, scale 1, offset 0; the tile's lat/lon arrays start at 30.0 / 70.0.
- **Measured 2026-10-29**, area only: WorldPop total **4.40 million** people; Overture **81,939** places
  and **389,303** buildings (peak memory about 1 GB to fetch).
- Overture features are kept if they intersect the area (not cut at its boundary).
- **Verified 2026-10-29:** Geofabrik splits India into six zones with no smaller sub-regions; the
  northern zone (`asia/india/northern-zone-latest.osm.pbf`, about 214 MB) has a bbox covering Delhi
  and Gurugram. The full India extract is about 1.6 GiB.
- `catchment-fetch osm` clips that extract to the area plus a 5 km buffer; the manifest records the
  extract's replication timestamp as `data_date`.
- **Verified 2026-10-29:** OSRM ships car, bicycle and foot profiles only, with no two-wheeler profile,
  and no maintained community motorcycle profile was found; the official Docker image
  (`ghcr.io/project-osrm/osrm-backend`) has a linux/arm64 build. `osmium-tool` is in Homebrew for arm64.

## Publishing (stage 3)

- **Verified 2026-11-05** (OSMF Licence FAQ and Produced Work guideline): data that can be read back as data is a
  database, not a Produced Work; a Derivative Database made public must stay under the ODbL; anyone a Produced Work
  reaches may ask for the Derivative Database behind it. Routing engines and apps using them must credit OSM. Whether
  an OSRM travel-time table counts as a Derivative Database is not settled on those pages; this project treats the
  published plan JSON as one ([ADR 0003](adr/0003-static-demo-on-gh-pages.md)).
- **Verified 2026-11-05:** OpenFreeMap's public tiles are free, commercial use allowed, attribution required (MapLibre
  adds it; video: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap"). MapLibre GL JS is BSD-3-Clause.
- **Verified 2026-11-05:** Hugging Face Docker and Gradio Spaces need a paid plan to create (PRO for personal
  accounts); free accounts can host static Spaces. The free CPU basic tier is 2 vCPU, 16 GB.

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

Hence the **synthetic network** (see [CONTEXT.md](../CONTEXT.md)): stores per brand, the operator's included, placed by
demand weight, with counts sized from publicly reported figures. Reported counts vary by source and
date; record the source and date for every number used.

- **Verified 2026-11-01:** the next-largest brand after Blinkit (2,751 stores at quarter end) is Swiggy
  Instamart, with 1,240 active dark stores at the end of Q2 FY27 (30 Sep 2026). Source: Swiggy Ltd Q2 FY27
  shareholders' letter, 22 Oct 2026, p. 7 (also pp. 2, 4; definition p. 19),
  https://www.swiggy.com/corporate/wp-content/uploads/2026/10/Q2-FY2027-Shareholder-letter.pdf. The two
  counts set the operator/competitor split of the synthetic network. Zepto's latest count found is 1,139
  dark stores at 31 Mar 2026 (press reports of its updated DRHP, June 2026; unverified, DRHP not checked at
  primary source), smaller and older; at Zepto's stated pace of about 100 stores a quarter it may since have
  passed 1,240, but no later count is reported. Flipkart Minutes states "over 1,000" (press, 2026; no exact
  count). The two counts are not defined alike: Swiggy counts stores with at least one completed order on
  the period's last day; Eternal's letter gives no definition for its "stores at the end of the period".
  Brands stay generic ("Operator", "Competitor") in anything user-facing.

## Not used (yet)

- **Census of India 2011:** too old for current demand. Census 2027 results: availability not checked.
- **Meta Relative Wealth Index:** licence not checked.
