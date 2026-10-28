"""The area polygon: built from OSM admin relations, committed as GeoJSON."""
import json
import sys
from datetime import date
from pathlib import Path

import requests
from shapely.geometry import LineString, mapping, shape
from shapely.ops import linemerge, polygonize, unary_union

AREA_PATH = Path(__file__).resolve().parents[2] / "area" / "gurugram-south-delhi.geojson"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RELATIONS = {10398244: "Gurgaon tehsil", 21181223: "South Delhi district"}


def _rings(members, role):
    """Polygons formed by the ways with this role, joining ways end to end."""
    lines = [
        LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        for m in members
        if m.get("type") == "way" and m.get("role") == role and m.get("geometry")
    ]
    if not lines:
        return []
    return list(polygonize(linemerge(lines)))


def relation_to_geometry(element):
    """Overpass relation element (`out geom`) -> shapely (Multi)Polygon."""
    members = element["members"]
    outer = unary_union(_rings(members, "outer"))
    inner = unary_union(_rings(members, "inner"))
    return outer.difference(inner)


def load_area():
    """The committed area as a shapely geometry (lon/lat, EPSG:4326)."""
    return shape(json.loads(AREA_PATH.read_text())["features"][0]["geometry"])


def _fetch(ids):
    query = "[out:json][timeout:120];(" + "".join(f"rel({i});" for i in ids) + ");out geom;"
    r = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": "catchment-area-build/0.1"},
        timeout=180,
    )
    r.raise_for_status()
    return {e["id"]: e for e in r.json()["elements"] if e["type"] == "relation"}


def _round(obj, nd=6):
    return [_round(x, nd) for x in obj] if isinstance(obj, (list, tuple)) else round(obj, nd)


def build():
    elements = _fetch(list(RELATIONS))
    geom = unary_union([relation_to_geometry(elements[i]) for i in RELATIONS])
    feature = mapping(geom)
    feature["coordinates"] = _round(feature["coordinates"])
    collection = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "relations": [{"id": i, "name": n} for i, n in RELATIONS.items()],
                "retrieved": date.today().isoformat(),
                "source": "© OpenStreetMap contributors, ODbL",
            },
            "geometry": feature,
        }],
    }
    AREA_PATH.parent.mkdir(exist_ok=True)
    AREA_PATH.write_text(json.dumps(collection, separators=(",", ":")) + "\n")
    print(f"wrote {AREA_PATH}", file=sys.stderr)


if __name__ == "__main__":
    build()
