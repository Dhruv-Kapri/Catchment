// The map: the basemap and the stores drawn on it. Each createMap call is its own map, so a page can hold several.
import { cellToLatLng } from "h3-js";
import { BASEMAP_STYLE, CREDITS } from "./api.js";

const CENTRE = [77.10, 28.48];   // lng, lat: Gurugram / South Delhi

export function createMap(container) {
  // The plans are routed on OpenStreetMap roads (ODbL, ADR 0003), so the corner credits OSM's contributors (in CREDITS) as well as the basemap.
  const map = new maplibregl.Map({ container, style: BASEMAP_STYLE, center: CENTRE, zoom: 11,
    attributionControl: { customAttribution: CREDITS.map(({ text }) => text) } });
  map.addControl(new maplibregl.NavigationControl());
  // ready resolves once the style has loaded, and stays resolved: isStyleLoaded() goes false again while tiles load, after "load" has fired.
  return { map, markers: [], ready: map.once("load") };
}

function addStore(view, cell, kind, label, onSelect) {
  const [lat, lng] = cellToLatLng(cell);
  const element = document.createElement("div");
  element.className = `store store-${kind}`;
  element.title = label;
  element.dataset.cell = cell;
  if (onSelect) element.addEventListener("click", () => onSelect(cell));
  view.markers.push(new maplibregl.Marker({ element }).setLngLat([lng, lat]).addTo(view.map));
}

// Brands are shown only as Operator / Competitor.
// onSelect(cell) is called when an operator store (existing or new) is clicked; competitors have no catchment.
export function showStores(view, plan, onSelect) {
  view.markers.forEach((marker) => marker.remove());
  view.markers = [];
  for (const cell of plan.network.Operator ?? []) addStore(view, cell, "operator", "Operator", onSelect);
  for (const cell of plan.network.Competitor ?? []) addStore(view, cell, "competitor", "Competitor");
  for (const cell of plan.sites) addStore(view, cell, "new", "New store", onSelect);
}

// Highlight the selected operator store's marker; null clears the highlight.
export function markSelected(view, cell) {
  for (const marker of view.markers) marker.getElement().classList.toggle("store-selected", marker.getElement().dataset.cell === cell);
}

// The existing network alone, before any plan.
export function showNetwork(view, network) {
  showStores(view, { network, sites: [] });
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
