"""Demand per hex: households x affluence multiplier x capture share, at any H3 resolution."""
import h3
import pandas as pd

from catchment.fetch import DATA


def build_demand(polygon, res=9, worldpop=DATA / "worldpop.tif", viirs=DATA / "viirs.tif"):
    """Demand table for every hex at res whose centre is in polygon, indexed by hex."""
    cells = sorted(h3.geo_to_cells(polygon, res))
    df = pd.DataFrame(index=pd.Index(cells, name="hex"))
    for col in ["lat", "lon", "population", "households", "radiance", "multiplier", "demand"]:
        df[col] = 0.0
    df.attrs["res"] = res
    return df
