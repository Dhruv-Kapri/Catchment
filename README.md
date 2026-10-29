# catchment

*Where should a quick-commerce operator open its next N dark stores, and what does each one win, or
take from the stores it already has?*

> **Status: stage 0 done** (setup and data fetch). Next: notebooks that run the whole chain on a small
> slice. The [roadmap](docs/roadmap.md) says what gets built and in what order.

## Getting started

```sh
uv sync                          # Python 3.12+
uv run nbstripout --install      # once per clone: strip notebook outputs on commit
cp .env.example .env             # then set LAADS_TOKEN (needed for the night-lights data)
uv run catchment-fetch           # fetch every source for the area into data/ (idempotent)
uv run pytest
```

`LAADS_TOKEN` is a LAADS DAAC token: log in at <https://ladsweb.modaps.eosdis.nasa.gov> with an
Earthdata account, then generate it on the
[download scripts page](https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/data-download-scripts/)
(an Earthdata "EDL" token is not accepted). The WorldPop file is slow to fetch (about 2 hours, once).

## The problem

Ten-minute delivery is a geography problem before it is an app problem. A store can only serve the
households a rider reaches in a few minutes, so every new store is a bet on one small catchment: how
many orders live there, how many of them an existing store (yours or a competitor's) already serves,
and whether the city's traffic lets you keep the promise at 7 pm. India now has several thousand dark
stores, and the next ones are being placed with exactly these trade-offs in mind.

This project builds a planning tool for that decision, from open data only.

## What it builds

```
population, night lights,   ─┐
places, buildings (open data)├─► 1. demand ──► 2. reach ──► 3. plan ──► 4. compare
road network (OSM)          ─┘    per hexagon    travel times   CP-SAT picks    scenarios
                                  (H3)           (OSRM, 2-wheeler) N stores       in a web map
```

- **Demand:** expected orders per H3 hexagon, from population × an affluence proxy × a capture share.
  Every factor is a visible, labelled assumption.
- **Reach:** two-wheeler travel times from candidate sites to hexagons, precomputed with OSRM, with a
  congestion multiplier the user can change.
- **Plan:** a CP-SAT model chooses N sites to maximise the demand reached within the delivery promise,
  under store capacity, with competing stores splitting shared catchments. Compared with a greedy
  baseline.
- **Compare:** a web map where the user changes the levers (N, promise in minutes, congestion,
  competitor density) and gets a new plan back in seconds.

First area: **Gurugram and South Delhi**. All of Delhi NCR comes after.

## What it is not

- **Not a forecast.** There is no real order data here. Demand is a transparent model, and the tool's
  value is in comparing plans under stated assumptions, not in the absolute numbers.
- **Not a map of any company's real stores.** Operators don't publish store locations and open map
  data barely has them (see [data sources](docs/data-sources.md)). Competitors are a synthetic layer,
  sized from publicly reported store counts.

## Docs

| File | What it holds |
| --- | --- |
| [docs/brief.md](docs/brief.md) | One-page product brief: user, decision, success metric |
| [docs/roadmap.md](docs/roadmap.md) | Stages with "done when" criteria |
| [docs/decisions.md](docs/decisions.md) | Decision log, newest first |
| [docs/cuts.md](docs/cuts.md) | What was cut from scope, and why |
| [docs/data-sources.md](docs/data-sources.md) | Datasets, licences, and what was checked |
| [CONTEXT.md](CONTEXT.md) | Glossary of the project's terms |
| [Reading list](docs/reference/Resources_Catchment.pdf) | Papers, docs and data for each stage, in build order |
| [Foundations](docs/reference/Foundations_Location_Intelligence_Logistics.pdf) | The field behind it: spatial thinking, retail geography, OR, last-mile, decision tools |

## Licence

Code: MIT. Data keeps its own licence (OpenStreetMap and Overture buildings: ODbL; Overture Places:
CDLA-Permissive-2.0; WorldPop: CC BY 4.0; NASA Black Marble: CC0, cited); derived outputs carry the
matching attribution.
