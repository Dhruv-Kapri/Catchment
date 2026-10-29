# Data sources

Facts are marked **Verified** (with date, read from the source or measured) or left unmarked
(unverified). Keep that distinction when adding or changing facts.

## Used

| Data | Use | Licence |
| --- | --- | --- |
| OpenStreetMap (Geofabrik India extract, clipped to the area) | road network for OSRM travel times | ODbL |
| Overture Maps Places (release 2026-10-21.0) | activity and affluence proxy; candidate sites | CDLA-Permissive-2.0 |
| Overture Maps buildings (release 2026-10-21.0) / Google Open Buildings | built-up density | Overture buildings: ODbL; Google Open Buildings: CC BY 4.0 |
| WorldPop, India 2025 constrained 100 m, R2025A v1 (`ind_pop_2025_CN_100m_R2025A_v1.tif`) | base demand | CC BY 4.0 |
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
- **Verified 2026-10-29:** OSRM ships car, bicycle and foot profiles only, with no two-wheeler profile,
  and no maintained community motorcycle profile was found; the official Docker image
  (`ghcr.io/project-osrm/osrm-backend`) has a linux/arm64 build. `osmium-tool` is in Homebrew for arm64.

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

## Not used (yet)

- **Census of India 2011:** too old for current demand. Census 2027 results: availability not checked.
- **Meta Relative Wealth Index:** licence not checked.
