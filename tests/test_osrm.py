import subprocess
from pathlib import Path

OSRM = Path(__file__).parent.parent / "osrm"


def test_profile_lives_in_osrm_dir():
    assert (OSRM / "two-wheeler.lua").is_file()


def test_script_without_arguments_prints_usage_and_exits_2():
    r = subprocess.run([str(OSRM / "osrm.sh")], capture_output=True, text=True)
    assert r.returncode == 2
    assert "usage:" in r.stderr and "build|serve|stop" in r.stderr


# ---- the real router, against a tiny road fixture in Docker ----

import shutil

import pytest

from catchment.reach import served_osrm

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
