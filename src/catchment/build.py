"""Build the derived tables from the fetched data into data/ (gitignored). Skips existing outputs."""
import argparse
import resource
import sys
import time

import geopandas as gpd
import pandas as pd

from catchment import assumptions
from catchment.area import load_area
from catchment.demand import build_demand
from catchment.fetch import DATA, atomic_path, VIIRS, WORLDPOP
from catchment.reach import build_reach, served_osrm

PLACES = DATA / "overture_places.parquet"
EXPLORE_PAIRS = 1.40e6   # stage 0.5's extrapolation of the full-area table (01-reach, res 9, X 30)


def demand_name(res):
    return f"demand-r{res}.parquet"


def reach_names(res, x_pct):
    return [f"candidates-r{res}-x{x_pct:g}.parquet", f"table-r{res}-x{x_pct:g}.parquet"]


def write_parquet(df, path):
    with atomic_path(path) as tmp:
        df.to_parquet(tmp)


def build_demand_stage(polygon, args, paths):
    df = build_demand(polygon, args.res, WORLDPOP, VIIRS)
    write_parquet(df, paths[0])
    print(f"  {len(df):,} hexes, {df.households.sum():,.0f} households, {df.demand.sum():,.0f} orders a day, "
          f"capture share {df.attrs['capture_share']:.3f}", file=sys.stderr)


def build_reach_stage(polygon, args, paths):
    demand_path = DATA / demand_name(args.res)
    if not demand_path.exists():
        print(f"reach: {demand_path.name} missing, building it first", file=sys.stderr)
        build_demand_stage(polygon, args, [demand_path])
    demand = pd.read_parquet(demand_path)
    pts = gpd.read_parquet(PLACES)
    places = pd.DataFrame({"lon": pts.geometry.x, "lat": pts.geometry.y, "operating_status": pts.operating_status})
    stats = DATA / "osrm" / "build-stats.tsv"
    built = not (DATA / "osrm" / "osm.osrm.hsgr").exists()
    t0 = time.perf_counter()
    with served_osrm(DATA) as router:
        candidates, table = build_reach(polygon, demand, places, args.res, args.x_pct, router)
    seconds = time.perf_counter() - t0
    for df, path in zip((candidates, table), paths):
        write_parquet(df, path)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)   # bytes on macOS, KiB on Linux
    peak = router.peak_bytes
    print(f"  {len(candidates):,} candidate sites, {len(table):,} pairs within {assumptions.MAX_PAIR_MIN} min, "
          f"against 0.5's extrapolation of about {EXPLORE_PAIRS / 1e6:.2f} M pairs", file=sys.stderr)
    print(f"  wall time {seconds:,.0f} s (OSRM build and serve included); this process's peak RSS {rss / 1e6:,.0f} MB; "
          f"osrm-routed peak {'unknown' if peak is None else f'{peak / 1e6:,.0f} MB'}", file=sys.stderr)
    if built and stats.exists():
        print("  OSRM build peaks:\n" + stats.read_text(), end="", file=sys.stderr)


# stage -> (builder(polygon, args, output paths), output names from args)
STAGES = {
    "demand": (build_demand_stage, lambda a: [demand_name(a.res)]),
    "reach": (build_reach_stage, lambda a: reach_names(a.res, a.x_pct)),
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="catchment-build", description=__doc__)
    ap.add_argument("stages", nargs="*", choices=list(STAGES), metavar="stage",
                    help=f"subset of: {', '.join(STAGES)} (default: all)")
    ap.add_argument("--res", type=int, default=9, help="H3 resolution (default: 9)")
    ap.add_argument("--x-pct", type=float, default=30, help="candidate sites: top X%% of the area's hexes by places (default: 30)")
    ap.add_argument("--force", action="store_true", help="rebuild outputs that exist")
    args = ap.parse_args(argv)
    DATA.mkdir(exist_ok=True)
    polygon = load_area()
    for name in args.stages or STAGES:
        fn, outputs = STAGES[name]
        paths = [DATA / o for o in outputs(args)]
        if not args.force and all(p.exists() for p in paths):
            print(f"{name}: {', '.join(p.name for p in paths)} exist, skipping (--force to rebuild)", file=sys.stderr)
            continue
        print(f"{name}: building {', '.join(p.name for p in paths)}", file=sys.stderr)
        fn(polygon, args, paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
