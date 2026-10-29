import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from catchment import reach
from catchment.reach import served_osrm

OSRM = Path(__file__).parent.parent / "osrm"


def test_profile_lives_in_osrm_dir():
    assert (OSRM / "two-wheeler.lua").is_file()


def test_script_without_arguments_prints_usage_and_exits_2():
    r = subprocess.run([str(OSRM / "osrm.sh")], capture_output=True, text=True)
    assert r.returncode == 2
    assert "usage:" in r.stderr and "build|serve|stop" in r.stderr


# ---- the real router, against a tiny road fixture in Docker ----

ROADS_OSM = Path(__file__).parent / "fixtures" / "roads.osm"
PORT, NAME = 5091, "catchment-osrm-test"


def docker_running():
    return shutil.which("docker") is not None and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


needs_docker = pytest.mark.skipif(not docker_running(), reason="Docker is not running")
docker = pytest.mark.docker   # deselect with -m "not docker"


def container_running():
    out = subprocess.run(["docker", "ps", "-q", "--filter", f"name=^{NAME}$"], capture_output=True, text=True, check=True)
    return bool(out.stdout.strip())


@pytest.fixture
def road_data(tmp_path):
    subprocess.run(["osmium", "cat", str(ROADS_OSM), "-o", str(tmp_path / "osm.osm.pbf")], check=True)
    return tmp_path


@docker
@needs_docker
def test_served_osrm_builds_the_graph_and_leaves_no_container(road_data):
    with served_osrm(road_data, PORT, NAME):
        assert (road_data / "osrm" / "osm.osrm.hsgr").exists()
        assert container_running()
    assert not container_running()


@docker
@needs_docker
def test_the_container_is_stopped_when_the_block_raises(road_data):
    with pytest.raises(RuntimeError, match="boom"):
        with served_osrm(road_data, PORT, NAME):
            assert container_running()
            raise RuntimeError("boom")
    assert not container_running()


@docker
@needs_docker
def test_the_peak_memory_is_read_before_the_container_stops(road_data):
    with served_osrm(road_data, PORT, NAME) as router:
        pass
    assert (router.peak_bytes or 0) > 1_000_000   # a running osrm-routed holds at least a few MB


@docker
@needs_docker
def test_snap_puts_an_off_road_point_on_the_road(road_data):
    lon, lat = 77.0305, 28.4503   # ~33 m north of the east-west road (lat 28.4500)
    with served_osrm(road_data, PORT, NAME) as router:
        s_lon, s_lat, dist = router.snap([lon], [lat])
    assert s_lon.shape == s_lat.shape == dist.shape == (1, 1)
    assert s_lat[0, 0] == pytest.approx(28.4500, abs=1e-5) and 77.0300 <= s_lon[0, 0] <= 77.0310
    assert 25 < dist[0, 0] < 40


@docker
@needs_docker
def test_minutes_along_the_road_are_positive_and_finite(road_data):
    with served_osrm(road_data, PORT, NAME) as router:
        m = router.minutes([77.0280, 77.0300], [28.4500, 28.4480], [77.0320], [28.4500])
    assert m.shape == (2, 1) and m.dtype == np.float32
    assert np.isfinite(m).all() and (m > 0).all()
    assert 0.2 < m[0, 0] < 1.5   # 400 m of residential road


@docker
@needs_docker
def test_a_destination_on_a_disconnected_road_is_nan(road_data):
    with served_osrm(road_data, PORT, NAME) as router:
        m = router.minutes([77.0280], [28.4500], [77.0320, 77.0405], [28.4500, 28.4500])   # 2nd: an island road
    assert np.isfinite(m[0, 0]) and np.isnan(m[0, 1])


@docker
@needs_docker
def test_chunked_requests_give_the_same_table(road_data, monkeypatch):
    src, dst = ([77.0280, 77.0300, 77.0320], [28.4500, 28.4480, 28.4520]), ([77.0290, 77.0300, 77.0310], [28.4500, 28.4520, 28.4500])
    with served_osrm(road_data, PORT, NAME) as router:
        whole = router.minutes(*src, *dst)
        monkeypatch.setattr(reach, "CHUNK_SRC", 2)
        monkeypatch.setattr(reach, "CHUNK_DST", 2)
        assert np.array_equal(router.minutes(*src, *dst), whole)
