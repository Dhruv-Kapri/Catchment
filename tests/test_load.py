import numpy as np
import rasterio
from rasterio.transform import from_origin

from catchment.load import viirs_at, worldpop_pixels


def tif(path, arr, nodata):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs="EPSG:4326", transform=from_origin(77.0, 29.0, 0.5, 0.5),
                       nodata=nodata) as dst:
        dst.write(arr.astype("float32"), 1)
    return path


def test_worldpop_pixels_drops_nodata_and_zero(tmp_path):
    p = tif(tmp_path / "w.tif", np.array([[1.5, -99999], [0, 4]]), -99999)
    df = worldpop_pixels(p)
    assert list(df.columns) == ["lon", "lat", "pop"]
    assert {(r.lon, r.lat): r["pop"] for _, r in df.iterrows()} == {(77.25, 28.75): 1.5, (77.75, 28.25): 4.0}


def test_viirs_at_nodata_is_nan(tmp_path):
    p = tif(tmp_path / "v.tif", np.array([[2.0, -9999], [0, 7]]), -9999)
    rad = viirs_at([77.25, 77.75, 77.25, 77.75], [28.75, 28.75, 28.25, 28.25], p)
    assert rad.dtype == float
    assert np.isnan(rad[1]) and rad[[0, 2, 3]].tolist() == [2.0, 0.0, 7.0]
