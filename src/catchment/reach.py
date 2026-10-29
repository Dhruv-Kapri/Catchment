"""Reach: candidate sites and the travel-time table for the area, from a router."""
import contextlib
import math
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import requests
import shapely

from catchment import assumptions

OSRM_SH = Path(__file__).resolve().parents[2] / "osrm" / "osrm.sh"

CHUNK_SRC, CHUNK_DST = 50, 950   # one /table request; osrm-routed runs with --max-table-size 1000


def n_top(x_pct, n_hexes, n_with_places):
    """Candidate site count: the top X% of the area's hexes (rounded up, exactly), only those with a place."""
    return min(math.ceil(Fraction(str(x_pct)) * n_hexes / 100), n_with_places)


def build_reach(polygon, demand, places, res, x_pct, router):
    if demand.attrs.get("res", res) != res:
        raise ValueError(f"demand table is res {demand.attrs['res']}, asked for res {res}")
    hexes = demand[shapely.contains_xy(polygon, demand.lon, demand.lat)]
    places = places[places.operating_status != "permanently_closed"]
    cells = pd.Series([h3.latlng_to_cell(y, x, res) for x, y in zip(places.lon, places.lat)])
    hexes = hexes.assign(places=cells.value_counts().reindex(hexes.index).fillna(0).astype(int))
    order = hexes.sort_values(["places", "demand"], ascending=False, kind="stable").index
    hexes["rank"] = pd.Series(np.arange(len(hexes)), index=order)
    k = n_top(x_pct, len(hexes), int((hexes.places > 0).sum()))
    candidates = hexes[hexes["rank"] < k].sort_values("rank")[["lat", "lon", "places", "rank"]]
    snap_lon, snap_lat, snap_m = router.snap(candidates.lon.to_numpy(), candidates.lat.to_numpy(), k=1)
    candidates["snap_lon"], candidates["snap_lat"], candidates["snap_m"] = snap_lon[:, 0], snap_lat[:, 0], snap_m[:, 0]
    minutes = router.minutes(candidates.snap_lon.to_numpy(), candidates.snap_lat.to_numpy(),
                             hexes.lon.to_numpy(), hexes.lat.to_numpy())
    src, dst = np.nonzero(minutes <= assumptions.MAX_PAIR_MIN)   # NaN compares False, so unroutable pairs drop out
    table = pd.DataFrame({"candidate": candidates.index[src], "hex": hexes.index[dst], "minutes": minutes[src, dst]})
    for df in (candidates, table):
        df.attrs = {"res": res, "x_pct": x_pct}
    return candidates, table


class OsrmRouter:
    def __init__(self, url="http://localhost:5001"):
        self.url, self.session = url, requests.Session()
        self.peak_bytes = None   # osrm-routed's peak memory, set by served_osrm before it stops the container

    def snap(self, lons, lats, k=1):
        """The k nearest road points of each point: arrays (n, k) of snapped lon, lat and distance in metres."""
        out = np.full((3, len(lons), k), np.nan)
        for i, (x, y) in enumerate(zip(lons, lats)):
            r = self.session.get(f"{self.url}/nearest/v1/driving/{x:.6f},{y:.6f}", params={"number": k}, timeout=300)
            r.raise_for_status()
            for j, w in enumerate(r.json()["waypoints"]):
                out[:, i, j] = *w["location"], w["distance"]
        return out[0], out[1], out[2]

    def minutes(self, src_lons, src_lats, dst_lons, dst_lats):
        """Free-flow minutes, sources x destinations, float32, NaN where there is no route. Requests are chunked."""
        out = np.full((len(src_lons), len(dst_lons)), np.nan, dtype=np.float32)
        for i in range(0, len(src_lons), CHUNK_SRC):
            s = slice(i, i + CHUNK_SRC)
            for j in range(0, len(dst_lons), CHUNK_DST):
                d = slice(j, j + CHUNK_DST)
                ns, nd = len(src_lons[s]), len(dst_lons[d])
                coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in zip([*src_lons[s], *dst_lons[d]], [*src_lats[s], *dst_lats[d]]))
                params = {"sources": ";".join(map(str, range(ns))), "destinations": ";".join(map(str, range(ns, ns + nd))),
                          "annotations": "duration"}
                r = self.session.get(f"{self.url}/table/v1/driving/{coords}", params=params, timeout=300)
                r.raise_for_status()
                out[s, d] = np.array(r.json()["durations"], dtype=float) / 60   # null -> NaN
        return out


def _container_peak_bytes(name):
    try:
        r = subprocess.run(["docker", "exec", name, "cat", "/sys/fs/cgroup/memory.peak"], capture_output=True, text=True)
        return int(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError):
        return None


@contextlib.contextmanager
def served_osrm(data_dir, port=5001, name="catchment-osrm"):
    """Build the graph in data_dir/osrm if missing, serve it, yield an OsrmRouter; always stop the container.
    Before stopping it sets router.peak_bytes to the container's peak memory (None if unreadable)."""
    data_dir = Path(data_dir)
    env = {**os.environ, "OSRM_DATA": str(data_dir), "OSRM_PORT": str(port), "OSRM_NAME": name}

    def osrm_sh(cmd):
        r = subprocess.run([str(OSRM_SH), cmd], env=env, capture_output=True, text=True)
        print(r.stdout + r.stderr, end="", file=sys.stderr)
        r.check_returncode()

    def stop():
        router.peak_bytes = _container_peak_bytes(name)
        osrm_sh("stop")

    router = OsrmRouter(f"http://localhost:{port}")
    try:
        if not (data_dir / "osrm" / "osm.osrm.hsgr").exists():
            osrm_sh("build")
        osrm_sh("serve")
        yield router
    except BaseException:
        with contextlib.suppress(Exception):   # a failed stop must not hide the error that got us here
            stop()
        raise
    stop()
