"""Fetch every source for the area into data/ (gitignored). Idempotent and resumable."""
import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import h5py
import numpy as np
import rasterio
import requests
from rasterio.mask import mask
from rasterio.transform import from_origin
from shapely.geometry import mapping

from catchment.area import load_area

DATA = Path(__file__).resolve().parents[2] / "data"
RAW = DATA / "raw"

WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/IND/v1/100m/"
    "constrained/ind_pop_2025_CN_100m_R2025A_v1.tif"
)
BM_BASE = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A4/2025/001"
BM_LAYER = "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields/NearNadir_Composite_Snow_Free"
BM_NODATA = -9999.0
OVERTURE_RELEASE = "2026-10-21.0"
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
LAADS_TOKEN_PAGE = "https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/data-download-scripts/"


class SourceError(Exception):
    """A source cannot be fetched; reported per source, others still run."""


# ---- resumable downloader -------------------------------------------------

def download(url, dest, headers=None, session=requests):
    """Download url to dest via dest.part and an atomic rename. No-op if dest exists.

    Resumes with a Range request; if the server answers 200 (ignores Range), restarts.
    """
    dest = Path(dest)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    hdrs = dict(headers or {})
    if have:
        hdrs["Range"] = f"bytes={have}-"
    with session.get(url, headers=hdrs, stream=True, timeout=60) as r:
        if r.status_code == 416:  # our partial is not a valid prefix: start over
            part.unlink()
            return download(url, dest, headers, session)
        r.raise_for_status()
        total = None
        if r.status_code == 206:
            spec, _, tot = r.headers.get("Content-Range", "").removeprefix("bytes ").partition("/")
            if spec and int(spec.split("-")[0]) != have:  # resumed at the wrong offset
                part.unlink(missing_ok=True)
                return download(url, dest, headers, session)
            total = int(tot) if tot.isdigit() else None
            mode = "ab"
        else:
            cl = r.headers.get("Content-Length")
            total = int(cl) if cl else None
            mode = "wb"
        with open(part, mode) as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    got = part.stat().st_size
    if total is not None and got != total:
        raise SourceError(f"download incomplete: {got} of {total} bytes of {url}; re-run to resume")
    os.replace(part, dest)
    return dest


# ---- raster helpers -------------------------------------------------------

def clip_raster(src_path, polygon, dest):
    """Clip a raster to polygon (lon/lat, same CRS as the raster); outside is nodata."""
    with rasterio.open(src_path) as src:
        data, transform = mask(src, [mapping(polygon)], crop=True, all_touched=True, nodata=src.nodata)
        profile = src.profile | {
            "driver": "GTiff", "height": data.shape[1], "width": data.shape[2],
            "transform": transform, "compress": "deflate", "tiled": False,
        }
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
    _atomic_write_tif(dest, data, profile)


def _atomic_write_tif(dest, data, profile):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with rasterio.open(tmp, "w", **profile) as out:
        out.write(data)
    os.replace(tmp, dest)


# ---- NASA Black Marble VNP46A4 -------------------------------------------

def black_marble_tile(lon, lat):
    return int((lon + 180) // 10), int((90 - lat) // 10)


def pick_black_marble(listing, h, v):
    tag = f".h{h:02d}v{v:02d}."
    names = [e["name"] for e in listing["content"] if tag in e["name"] and e["name"].endswith(".h5")]
    if not names:
        raise LookupError(f"no tile {tag.strip('.')} in listing")
    return sorted(names)[-1]


def check_hdf5(path):
    with open(path, "rb") as f:
        if f.read(8) != HDF5_SIGNATURE:
            raise ValueError(
                f"{path} is not HDF5 (LAADS sent its login page): LAADS_TOKEN was not accepted. "
                "It must be a LAADS DAAC token (not an Earthdata EDL token) and not expired; "
                f"generate one at {LAADS_TOKEN_PAGE}"
            )


def black_marble_to_tif(h5_path, h, v, polygon, dest):
    """Georeference the 2400x2400 tile from its index, scale, and clip to polygon."""
    n, res = 2400, 10 / 2400
    west, north = h * 10 - 180, 90 - v * 10
    minx, miny, maxx, maxy = polygon.bounds
    c0, c1 = max(0, int((minx - west) // res)), min(n, int(np.ceil((maxx - west) / res)))
    r0, r1 = max(0, int((north - maxy) // res)), min(n, int(np.ceil((north - miny) / res)))
    with h5py.File(h5_path, "r") as f:
        ds = f[BM_LAYER]
        raw = ds[r0:r1, c0:c1]
        fill = ds.attrs.get("_FillValue")
        scale = float(np.ravel(ds.attrs.get("scale_factor", 1.0))[0])
        offset = float(np.ravel(ds.attrs.get("add_offset", 0.0))[0])
    arr = raw.astype("float32") * scale + offset
    if fill is not None:
        arr[raw == np.ravel(fill)[0]] = BM_NODATA
    profile = {
        "driver": "GTiff", "height": arr.shape[0], "width": arr.shape[1], "count": 1,
        "dtype": "float32", "crs": "EPSG:4326", "nodata": BM_NODATA,
        "transform": from_origin(west + c0 * res, north - r0 * res, res, res),
    }
    with tempfile.TemporaryDirectory() as td:
        window = Path(td) / "window.tif"
        _atomic_write_tif(window, arr[None], profile)
        clip_raster(window, polygon, dest)


# ---- sources --------------------------------------------------------------

def fetch_worldpop(polygon):
    raw = download(WORLDPOP_URL, RAW / Path(WORLDPOP_URL).name)
    out = DATA / "worldpop.tif"
    clip_raster(raw, polygon, out)
    return {"source": WORLDPOP_URL, "files": [out.name]}


def fetch_viirs(polygon):
    token = os.environ.get("LAADS_TOKEN")
    if not token:
        raise SourceError(
            "LAADS_TOKEN is not set. Log in to LAADS with Earthdata, generate a LAADS DAAC "
            f"token at {LAADS_TOKEN_PAGE} and put LAADS_TOKEN=... in .env"
        )
    lon, lat = polygon.centroid.x, polygon.centroid.y
    h, v = black_marble_tile(lon, lat)
    auth = {"Authorization": f"Bearer {token}"}
    listing = requests.get(f"{BM_BASE}.json", timeout=60)
    listing.raise_for_status()
    name = pick_black_marble(listing.json(), h, v)
    url = f"{BM_BASE}/{name}"
    raw = RAW / name
    download(url, raw, headers=auth)
    try:
        check_hdf5(raw)
    except ValueError as e:
        raw.unlink()
        raise SourceError(str(e)) from e
    out = DATA / "viirs.tif"
    black_marble_to_tif(raw, h, v, polygon, out)
    return {"source": url, "layer": BM_LAYER, "files": [out.name]}


def fetch_overture(polygon):
    import overturemaps.core as ov
    files = []
    for kind, name in (("place", "overture_places.parquet"), ("building", "overture_buildings.parquet")):
        gdf = ov.geodataframe(kind, bbox=polygon.bounds, release=OVERTURE_RELEASE)
        gdf = gdf[gdf.intersects(polygon)]
        tmp = DATA / (name + ".part")
        gdf.to_parquet(tmp)
        os.replace(tmp, DATA / name)
        print(f"  {name}: {len(gdf)} rows", file=sys.stderr)
        del gdf
        files.append(name)
    return {"release": OVERTURE_RELEASE, "files": files}


SOURCES = {
    "worldpop": (fetch_worldpop, ["worldpop.tif"]),
    "viirs": (fetch_viirs, ["viirs.tif"]),
    "overture": (fetch_overture, ["overture_places.parquet", "overture_buildings.parquet"]),
}


def _update_manifest(name, entry):
    path = DATA / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    manifest[name] = entry | {"fetched": date.today().isoformat()}
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(tmp, path)


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv()
    ap = argparse.ArgumentParser(prog="catchment-fetch", description=__doc__)
    ap.add_argument("sources", nargs="*", choices=list(SOURCES), metavar="source",
                    help=f"subset of: {', '.join(SOURCES)} (default: all)")
    ap.add_argument("--force", action="store_true", help="redo clipping/conversion for sources whose output exists (raw downloads in data/raw are kept)")
    args = ap.parse_args(argv)
    DATA.mkdir(exist_ok=True)
    polygon = load_area()
    failed = []
    for name in args.sources or SOURCES:
        fn, outputs = SOURCES[name]
        if not args.force and all((DATA / o).exists() for o in outputs):
            print(f"{name}: already fetched, skipping (--force to redo)", file=sys.stderr)
            continue
        print(f"{name}: fetching", file=sys.stderr)
        try:
            _update_manifest(name, fn(polygon))
        except SourceError as e:
            print(f"{name}: FAILED: {e}", file=sys.stderr)
            failed.append(name)
        except Exception as e:
            print(f"{name}: FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
