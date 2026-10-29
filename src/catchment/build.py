"""Build the derived tables from the fetched data into data/ (gitignored). Skips existing outputs."""
import argparse
import os
import sys

from catchment.area import load_area
from catchment.demand import build_demand
from catchment.fetch import DATA

WORLDPOP = DATA / "worldpop.tif"
VIIRS = DATA / "viirs.tif"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="catchment-build", description=__doc__)
    ap.add_argument("stages", nargs="*", choices=["demand"], metavar="stage")
    args = ap.parse_args(argv)
    df = build_demand(load_area(), 9, WORLDPOP, VIIRS)
    path = DATA / "demand-r9.parquet"
    tmp = path.with_name(path.name + ".part")
    df.to_parquet(tmp)
    os.replace(tmp, path)
    print(f"  {len(df):,} hexes, {df.households.sum():,.0f} households, {df.demand.sum():,.0f} orders a day, "
          f"capture share {df.attrs['capture_share']:.3f}", file=sys.stderr)
    return 0
