"""Demand per hex: households x affluence multiplier x capture share, at any H3 resolution."""
import h3
import pandas as pd

from catchment.fetch import DATA
from catchment.load import worldpop_pixels


def build_demand(polygon, res=9, worldpop=DATA / "worldpop.tif", viirs=DATA / "viirs.tif"):
    """Demand table for every hex at res whose centre is in polygon, indexed by hex."""
    cells = sorted(h3.geo_to_cells(polygon, res))
    df = pd.DataFrame(index=pd.Index(cells, name="hex"))
    centres = [h3.cell_to_latlng(c) for c in cells]
    df["lat"], df["lon"] = [c[0] for c in centres], [c[1] for c in centres]
    wp = worldpop_pixels(worldpop)
    pix_hex = [h3.latlng_to_cell(y, x, res) for x, y in zip(wp.lon, wp.lat)]
    df["population"] = wp["pop"].groupby(pix_hex).sum().reindex(df.index).fillna(0.0)
    for col in ["households", "radiance", "multiplier", "demand"]:
        df[col] = 0.0
    df.attrs["res"] = res
    return df
