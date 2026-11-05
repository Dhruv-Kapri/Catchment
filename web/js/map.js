// The map: the basemap and the stores drawn on it. Each createMap call is its own map, so a page can hold several.
import { cellToLatLng } from "h3-js";
import { BASEMAP_STYLE } from "./api.js";

const CENTRE = [77.10, 28.48];   // lng, lat: Gurugram / South Delhi

export function createMap(container) {
  const map = new maplibregl.Map({ container, style: BASEMAP_STYLE, center: CENTRE, zoom: 11 });
  map.addControl(new maplibregl.NavigationControl());
  return { map, markers: [] };
}

function addStore(view, cell, kind, label) {
  const [lat, lng] = cellToLatLng(cell);
  const element = document.createElement("div");
  element.className = `store store-${kind}`;
  element.title = label;
  view.markers.push(new maplibregl.Marker({ element }).setLngLat([lng, lat]).addTo(view.map));
}

// Brands are shown only as Operator / Competitor.
export function showStores(view, plan) {
  view.markers.forEach((marker) => marker.remove());
  view.markers = [];
  for (const cell of plan.network.Operator ?? []) addStore(view, cell, "operator", "Operator");
  for (const cell of plan.network.Competitor ?? []) addStore(view, cell, "competitor", "Competitor");
  for (const cell of plan.sites) addStore(view, cell, "new", "New store");
}

// Pan, zoom, rotate and tilt on either map moves the other. One shared flag stops the two echoing each other.
export function linkMaps(a, b) {
  let syncing = false;
  const follow = (from, to) => from.map.on("move", () => {
    if (syncing) return;
    syncing = true;
    try {
      to.map.jumpTo({ center: from.map.getCenter(), zoom: from.map.getZoom(), bearing: from.map.getBearing(), pitch: from.map.getPitch() });
    } finally {
      syncing = false;
    }
  });
  follow(a, b);
  follow(b, a);
}
