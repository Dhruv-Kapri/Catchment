"""Demand per hex: households x affluence multiplier x capture share, at any H3 resolution."""
import pandas as pd

from catchment.fetch import DATA


def build_demand(polygon, res=9, worldpop=DATA / "worldpop.tif", viirs=DATA / "viirs.tif"):
    """Demand table for every hex at res whose centre is in polygon, indexed by hex."""
    return pd.DataFrame()
