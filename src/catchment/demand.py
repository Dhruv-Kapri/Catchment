"""Demand per hex: households x affluence multiplier x capture share, at any H3 resolution."""
import h3
import numpy as np
import pandas as pd

from catchment import assumptions
from catchment.fetch import VIIRS, WORLDPOP
from catchment.load import viirs_at, worldpop_pixels


def build_demand(polygon, res=9, worldpop=WORLDPOP, viirs=VIIRS):
    """Demand table for every hex at res whose centre is in polygon, indexed by hex.

    Population is the WorldPop pixels whose centre falls in the hex (pixels in non-area hexes are dropped).
    Radiance is sampled at the hex centre (NaN takes the minimum) and ranked across the area; the multiplier runs
    from M_LOW to M_HIGH with that rank. If every hex has the same radiance, every hex gets the midpoint multiplier.
    The default capture share makes the area's demand per household the calibration target; it is stored in
    df.attrs["capture_share"] (with "res"), which parquet round-trips.
    Every step runs at res itself, so a coarser res drops the population of hexes whose centre is outside polygon.
    """
    cells = sorted(h3.geo_to_cells(polygon, res))
    df = pd.DataFrame(index=pd.Index(cells, name="hex"))
    centres = [h3.cell_to_latlng(c) for c in cells]
    df["lat"], df["lon"] = [c[0] for c in centres], [c[1] for c in centres]

    wp = worldpop_pixels(worldpop)
    pix_hex = [h3.latlng_to_cell(y, x, res) for x, y in zip(wp.lon, wp.lat)]
    df["population"] = wp["pop"].groupby(pix_hex).sum().reindex(df.index).fillna(0.0)
    df["households"] = df["population"] / assumptions.HOUSEHOLD_SIZE

    rad = viirs_at(df.lon, df.lat, viirs)
    if np.isnan(rad).all():
        raise ValueError("VIIRS has no data over the area")
    df["radiance"] = np.where(np.isnan(rad), np.nanmin(rad), rad)
    pct = df["radiance"].rank(pct=True, method="average")
    span = pct.max() - pct.min()
    p = (pct - pct.min()) / span if span > 0 else pd.Series(0.5, index=df.index)
    df["multiplier"] = assumptions.M_LOW + p * (assumptions.M_HIGH - assumptions.M_LOW)

    capture_share = assumptions.ORDERS_PER_HOUSEHOLD_DAY / np.average(df["multiplier"], weights=df["households"])
    df["demand"] = df["households"] * df["multiplier"] * capture_share
    df.attrs["capture_share"] = capture_share
    df.attrs["res"] = res
    return df
