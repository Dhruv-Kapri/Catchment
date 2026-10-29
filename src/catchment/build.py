"""Build the derived tables from the fetched data into data/ (gitignored). Skips existing outputs."""
import argparse
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
    df.to_parquet(DATA / "demand-r9.parquet")
    return 0
