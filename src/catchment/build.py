"""Build the derived tables from the fetched data into data/ (gitignored). Skips existing outputs."""
import argparse
import os
import sys

from catchment.area import load_area
from catchment.demand import build_demand
from catchment.fetch import DATA

WORLDPOP = DATA / "worldpop.tif"
VIIRS = DATA / "viirs.tif"


def build_demand_stage(polygon, res, path):
    df = build_demand(polygon, res, WORLDPOP, VIIRS)
    tmp = path.with_name(path.name + ".part")
    df.to_parquet(tmp)
    os.replace(tmp, path)
    print(f"  {len(df):,} hexes, {df.households.sum():,.0f} households, {df.demand.sum():,.0f} orders a day, "
          f"capture share {df.attrs['capture_share']:.3f}", file=sys.stderr)


def build_reach_stage(polygon, res, path):
    pass


# stage -> (builder(polygon, res, path), output name for a resolution); `reach` joins here later
STAGES = {
    "demand": (build_demand_stage, lambda res: f"demand-r{res}.parquet"),
    "reach": (build_reach_stage, lambda res: f"candidates-r{res}-x30.parquet"),
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="catchment-build", description=__doc__)
    ap.add_argument("stages", nargs="*", choices=list(STAGES), metavar="stage",
                    help=f"subset of: {', '.join(STAGES)} (default: all)")
    ap.add_argument("--res", type=int, default=9, help="H3 resolution (default: 9)")
    ap.add_argument("--force", action="store_true", help="rebuild outputs that exist")
    args = ap.parse_args(argv)
    DATA.mkdir(exist_ok=True)
    polygon = load_area()
    for name in args.stages or STAGES:
        fn, output = STAGES[name]
        path = DATA / output(args.res)
        if not args.force and path.exists():
            print(f"{name}: {path.name} exists, skipping (--force to rebuild)", file=sys.stderr)
            continue
        print(f"{name}: building {path.name}", file=sys.stderr)
        fn(polygon, args.res, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
