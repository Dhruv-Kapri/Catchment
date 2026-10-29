import json
import shutil
import subprocess
from pathlib import Path

import h5py
import numpy as np
import pytest
import requests
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from catchment import fetch


class FakeResp:
    def __init__(self, status, body, ctype="application/octet-stream"):
        self.status_code, self.body = status, body
        self.headers = {"Content-Type": ctype}

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class FakeSession:
    """Serves BODY; honours Range only if `ranges`, else answers 200 with everything."""
    def __init__(self, body, ranges):
        self.body, self.ranges, self.calls = body, ranges, []

    def get(self, url, headers=None, stream=True, timeout=None):
        self.calls.append(headers or {})
        rng = (headers or {}).get("Range")
        if rng and self.ranges:
            start = int(rng.split("=")[1].rstrip("-"))
            return FakeResp(206, self.body[start:])
        return FakeResp(200, self.body)


def test_final_exists_no_request(tmp_path):
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"done")
    s = FakeSession(b"xxxx", True)
    fetch.download("u", dest, session=s)
    assert s.calls == [] and dest.read_bytes() == b"done"


def test_part_with_206_is_appended(tmp_path):
    dest = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(b"hello ")
    s = FakeSession(b"hello world", True)
    fetch.download("u", dest, session=s)
    assert s.calls[0]["Range"] == "bytes=6-"
    assert dest.read_bytes() == b"hello world" and not (tmp_path / "f.bin.part").exists()


def test_part_with_200_is_restarted(tmp_path):
    dest = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(b"hello ")
    s = FakeSession(b"hello world", False)
    fetch.download("u", dest, session=s)
    assert dest.read_bytes() == b"hello world"


def test_clip_raster(tmp_path):
    src = tmp_path / "s.tif"
    data = np.arange(100, dtype="float32").reshape(10, 10)
    with rasterio.open(src, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(0, 10, 1, 1), nodata=-1) as d:
        d.write(data, 1)
    out = tmp_path / "o.tif"
    fetch.clip_raster(src, box(2.5, 2.5, 5.5, 4.5), out)
    with rasterio.open(out) as r:
        assert r.nodata == -1 and r.crs.to_epsg() == 4326
        assert (r.width, r.height) == (4, 3)
        assert r.bounds.left == 2 and r.bounds.top == 5
        assert r.read(1)[0, 0] == data[5, 2]


def test_tile_index():
    assert fetch.black_marble_tile(77.0, 28.5) == (25, 6)
    assert fetch.black_marble_tile(-179.9, 89.9) == (0, 0)


def test_pick_file_from_listing():
    listing = {"content": [
        {"name": "VNP46A4.A2025001.h25v05.002.2026077000001.h5"},
        {"name": "VNP46A4.A2025001.h25v06.002.2026077000736.h5"},
    ]}
    assert fetch.pick_black_marble(listing, 25, 6) == "VNP46A4.A2025001.h25v06.002.2026077000736.h5"
    with pytest.raises(LookupError):
        fetch.pick_black_marble(listing, 1, 1)


def make_h5(path, arr, **attrs):
    with h5py.File(path, "w") as f:
        ds = f.create_dataset(fetch.BM_LAYER, data=arr)
        for k, v in attrs.items():
            ds.attrs[k] = v


def test_black_marble_tile_to_clipped_tif(tmp_path):
    arr = np.full((2400, 2400), 10, dtype="uint16")
    arr[0, 0] = 65535  # fill
    h5 = tmp_path / "t.h5"
    make_h5(h5, arr, _FillValue=np.uint16(65535), scale_factor=0.1, add_offset=0.0)
    out = tmp_path / "v.tif"
    # tile h25v06: west 70, north 30; clip to 77..77.1, 28.5..28.6
    fetch.black_marble_to_tif(h5, 25, 6, box(77, 28.5, 77.1, 28.6), out)
    with rasterio.open(out) as r:
        v = r.read(1)
        assert r.crs.to_epsg() == 4326 and r.nodata is not None
        assert abs(r.bounds.left - 77) < 0.01 and abs(r.bounds.top - 28.6) < 0.01
        assert np.isclose(v, 1.0).mean() > 0.9  # scaled; edge pixels may be masked

    # fill value becomes nodata
    out2 = tmp_path / "v2.tif"
    fetch.black_marble_to_tif(h5, 25, 6, box(70, 29.9, 70.1, 30), out2)
    with rasterio.open(out2) as r:
        assert r.read(1)[0, 0] == r.nodata


def test_non_hdf5_rejected(tmp_path):
    p = tmp_path / "x.h5"
    p.write_text("<html>login</html>")
    with pytest.raises(ValueError, match="TOKEN"):
        fetch.check_hdf5(p)


def test_truncated_200_keeps_part_and_raises(tmp_path):
    dest = tmp_path / "f.bin"
    s = FakeSession(b"hello", False)
    orig = s.get

    def get(url, headers=None, **kw):
        r = orig(url, headers, **kw)
        r.headers["Content-Length"] = "11"  # promises more than the body
        return r
    s.get = get
    with pytest.raises(fetch.SourceError, match="incomplete"):
        fetch.download("u", dest, session=s)
    assert not dest.exists() and (tmp_path / "f.bin.part").read_bytes() == b"hello"


def test_206_start_mismatch_restarts(tmp_path):
    dest = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(b"hello ")
    s = FakeSession(b"hello world", True)
    orig = s.get
    calls = []

    def get(url, headers=None, **kw):
        calls.append(dict(headers or {}))
        r = orig(url, headers, **kw)
        if headers and "Range" in headers:
            r.headers["Content-Range"] = "bytes 0-10/11"  # not where we asked
            r.body = b"hello world"
        return r
    s.get = get
    fetch.download("u", dest, session=s)
    assert dest.read_bytes() == b"hello world" and "Range" not in calls[-1]


def test_one_source_failing_does_not_stop_others(tmp_path, monkeypatch):
    def boom(polygon):
        raise requests.ConnectionError("down")

    def ok(polygon):
        (tmp_path / "b.txt").write_text("x")
        return {"files": ["b.txt"]}
    monkeypatch.setattr(fetch, "DATA", tmp_path)
    monkeypatch.setattr(fetch, "load_area", lambda: box(0, 0, 1, 1))
    monkeypatch.setattr(fetch, "SOURCES", {"a": (boom, ["a.txt"]), "b": (ok, ["b.txt"])})
    assert fetch.main([]) == 1
    assert "b" in json.loads((tmp_path / "manifest.json").read_text())


# ---- osm ------------------------------------------------------------------

TINY_OSM = Path(__file__).parent / "fixtures" / "tiny.osm"
needs_osmium = pytest.mark.skipif(shutil.which("osmium") is None, reason="osmium-tool not installed")


@pytest.fixture
def osm_env(tmp_path, monkeypatch):
    downloads = []

    def fake_download(url, dest, **kw):
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["osmium", "cat", str(TINY_OSM), "-o", str(dest)], check=True)
            downloads.append(url)
        return dest
    monkeypatch.setattr(fetch, "DATA", tmp_path)
    monkeypatch.setattr(fetch, "RAW", tmp_path / "raw")
    monkeypatch.setattr(fetch, "load_area", lambda: box(77.0, 28.4, 77.1, 28.5))
    monkeypatch.setattr(fetch, "download", fake_download)
    return tmp_path, downloads


def osm_node_ids(path):
    out = subprocess.run(["osmium", "cat", str(path), "-f", "opl"], check=True, capture_output=True, text=True).stdout
    return {int(line.split()[0][1:]) for line in out.splitlines() if line.startswith("n")}


@needs_osmium
def test_osm_clips_to_area_plus_buffer(osm_env):
    tmp_path, _ = osm_env
    assert fetch.main(["osm"]) == 0
    assert osm_node_ids(tmp_path / "osm.osm.pbf") == {1, 2, 3}
    entry = json.loads((tmp_path / "manifest.json").read_text())["osm"]
    assert entry["source"] == fetch.OSM_URL and entry["data_date"] == "2026-10-02T12:34:56Z"
    assert entry["buffer_m"] == 5000 and entry["files"] == ["osm.osm.pbf"]


@needs_osmium
def test_osm_rerun_skips_and_force_reclips_without_download(osm_env):
    tmp_path, downloads = osm_env
    assert fetch.main(["osm"]) == 0
    out = tmp_path / "osm.osm.pbf"
    out.write_bytes(b"junk")
    assert fetch.main(["osm"]) == 0 and out.read_bytes() == b"junk"
    assert fetch.main(["osm", "--force"]) == 0
    assert osm_node_ids(out) == {1, 2, 3} and len(downloads) == 1


def test_osm_missing_osmium_fails_before_download(osm_env, monkeypatch, capsys):
    tmp_path, downloads = osm_env

    def ok(polygon):
        return {"files": ["b.txt"]}
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(fetch, "SOURCES", {"osm": fetch.SOURCES["osm"], "b": (ok, ["b.txt"])})
    assert fetch.main([]) == 1
    assert "brew install osmium-tool" in capsys.readouterr().err
    assert "b" in json.loads((tmp_path / "manifest.json").read_text()) and downloads == []


def test_osm_is_a_default_source():
    assert "osm" in fetch.SOURCES
