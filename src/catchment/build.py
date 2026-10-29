"""Build the derived tables from the fetched data into data/ (gitignored). Skips existing outputs."""
from catchment.area import load_area
from catchment.fetch import DATA

WORLDPOP = DATA / "worldpop.tif"
VIIRS = DATA / "viirs.tif"


def main(argv=None):
    return 0
