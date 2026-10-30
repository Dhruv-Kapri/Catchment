import numpy as np
import pandas as pd
import rasterio

from catchment.fetch import VIIRS, WORLDPOP


def worldpop_pixels(path=WORLDPOP):
    """Pixels with population > 0 (nodata dropped) as lon, lat (pixel centre), pop."""
    with rasterio.open(path) as src:
        pop = src.read(1)
        rows, cols = np.nonzero((pop != src.nodata) & (pop > 0))
        xs, ys = src.xy(rows, cols)
        return pd.DataFrame({"lon": xs, "lat": ys, "pop": pop[rows, cols].astype(float)})


def viirs_at(lons, lats, path=VIIRS):
    """Radiance at each (lon, lat), nodata as NaN."""
    with rasterio.open(path) as src:
        rad = np.array([v[0] for v in src.sample(zip(lons, lats), masked=False)], dtype=float)
        rad[rad == src.nodata] = np.nan
        return rad
