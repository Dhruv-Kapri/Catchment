#!/usr/bin/env bash
# Build and run the two-wheeler OSRM graph in Docker.
#   osrm/osrm.sh build   extract + contract (CH) data/osm.osm.pbf with osrm/two-wheeler.lua into data/osrm/
#   osrm/osrm.sh serve   osrm-routed on http://localhost:5001 as container catchment-osrm (replaces a running one)
#   osrm/osrm.sh stop    remove the container
# Overrides (env), defaults in brackets: OSRM_DATA [<repo>/data], OSRM_PORT [5001], OSRM_NAME [catchment-osrm]
set -euo pipefail

IMAGE="ghcr.io/project-osrm/osrm-backend:v26.10.0-debian"   # linux/arm64 build; pinned
NAME="${OSRM_NAME:-catchment-osrm}"
PORT="${OSRM_PORT:-5001}"                                    # macOS AirPlay often holds 5000

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PROFILE="$ROOT/osrm/two-wheeler.lua"
DATA="${OSRM_DATA:-$ROOT/data}"
PBF="$DATA/osm.osm.pbf"
OUT="$(mkdir -p "$DATA/osrm" && cd -P "$DATA/osrm" && pwd -P)"   # data may be a symlink; docker needs the real path
STATS="$OUT/build-stats.tsv"

now() { perl -MTime::HiRes=time -e 'printf "%.1f\n", time'; }

# step NAME CMD...: run one OSRM tool in its own container; log it; append peak memory (cgroup) and wall time to STATS
step() {
  local name="$1"; shift
  local peakfile="$OUT/$name.peak" start end rc=0
  rm -f "$peakfile"
  start="$(now)"
  docker run --rm -v "$OUT:/data" -v "$PROFILE:/opt/two-wheeler.lua:ro" "$IMAGE" bash -c \
    "$* ; rc=\$?; cat /sys/fs/cgroup/memory.peak > /data/$name.peak; exit \$rc" \
    > "$OUT/$name.log" 2>&1 || rc=$?
  end="$(now)"
  if [ "$rc" -ne 0 ]; then
    echo "osrm.sh: step '$name' failed (exit $rc); last lines of $OUT/$name.log:" >&2
    tail -n 20 "$OUT/$name.log" >&2
    exit "$rc"
  fi
  [ -s "$peakfile" ] || { echo "osrm.sh: no peak memory recorded for '$name'" >&2; exit 1; }
  printf '%s\t%s\t%s\n' "$name" "$(cat "$peakfile")" "$(perl -e "printf '%.1f', $end - $start")" >> "$STATS"
  rm -f "$peakfile"
  echo "$name done: see $OUT/$name.log" >&2
}

case "${1:-}" in
  build)
    [ -f "$PBF" ] || { echo "osrm.sh: $PBF missing; run 'uv run catchment-fetch osm'" >&2; exit 1; }
    docker info >/dev/null 2>&1 || { echo "osrm.sh: Docker is not running" >&2; exit 1; }
    "$0" stop
    rm -f "$OUT"/osm.osrm* "$OUT"/*.log "$OUT"/*.peak "$STATS"
    cp "$PBF" "$OUT/osm.osm.pbf"
    printf 'step\tpeak_bytes\tseconds\n' > "$STATS"
    step extract "osrm-extract -p /opt/two-wheeler.lua /data/osm.osm.pbf"
    step contract "osrm-contract /data/osm.osrm"
    cat "$STATS"
    ;;
  serve)
    [ -f "$OUT/osm.osrm.hsgr" ] || { echo "osrm.sh: no graph in $OUT; run 'osrm/osrm.sh build'" >&2; exit 1; }
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    # --max-table-size: /table accepts at most this many coordinates (default 100); the travel-time table is built in chunks of up to this size
    docker run -d --name "$NAME" -p "$PORT:5000" -v "$OUT:/data:ro" "$IMAGE" \
      osrm-routed --algorithm ch --max-table-size 1000 /data/osm.osrm >/dev/null
    for _ in $(seq 1 60); do
      if curl -fs "http://localhost:$PORT/nearest/v1/driving/77.03,28.45" >/dev/null 2>&1; then
        echo "OSRM answering on http://localhost:$PORT"
        exit 0
      fi
      sleep 1
    done
    echo "osrm.sh: OSRM did not answer within 60 s; container logs:" >&2
    docker logs "$NAME" >&2 || true
    exit 1
    ;;
  stop)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    ;;
  *)
    echo "usage: $0 build|serve|stop" >&2
    exit 2
    ;;
esac
