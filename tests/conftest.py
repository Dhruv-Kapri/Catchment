import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

POLY = box(77.045, 28.445, 77.055, 28.455)   # ~1 km box: a handful of res-9 hexes


def write_tif(path, arr, pixel, nodata):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs="EPSG:4326", transform=from_origin(77.04, 28.46, pixel, pixel),
                       nodata=nodata) as dst:
        dst.write(arr.astype("float32"), 1)
    return path


def make_rasters(tmp_path):
    """WorldPop-like 100 m pixels (40x40) and coarser VIIRS-like pixels (10x10), covering POLY."""
    rng = np.random.default_rng(0)
    wp = write_tif(tmp_path / "wp.tif", rng.integers(0, 50, (40, 40)) * 0.1 + 1, 0.0005, -99999)
    vi = write_tif(tmp_path / "vi.tif", np.arange(100).reshape(10, 10) + 1.0, 0.002, -9999)
    return wp, vi
