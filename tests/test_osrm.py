import subprocess
from pathlib import Path

OSRM = Path(__file__).parent.parent / "osrm"


def test_profile_lives_in_osrm_dir():
    assert (OSRM / "two-wheeler.lua").is_file()


def test_script_without_arguments_prints_usage_and_exits_2():
    r = subprocess.run([str(OSRM / "osrm.sh")], capture_output=True, text=True)
    assert r.returncode == 2
    assert "usage:" in r.stderr and "build|serve|stop" in r.stderr
