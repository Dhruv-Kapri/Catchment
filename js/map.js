// The map: the basemap and the stores drawn on it. Each createMap call is its own map, so a page can hold several.
import { cellToLatLng } from "h3-js";
import { BASEMAP_STYLE, CREDITS } from "./api.js";

const BOUNDS = [[76.90, 28.36], [77.27, 28.60]];   // lng/lat corners of where the stores are (Gurugram / South Delhi); the map fits to it, whatever its width

export function createMap(container) {
  // The plans are routed on OpenStreetMap roads (ODbL, ADR 0003), so the corner credits OSM's contributors (in CREDITS) as well as the basemap.
  const map = new maplibregl.Map({ container, style: BASEMAP_STYLE, bounds: BOUNDS, fitBoundsOptions: { padding: 6 },
    attributionControl: { compact: true, customAttribution: CREDITS.map(({ text }) => text) } });
  map.addControl(new maplibregl.NavigationControl());
  // Markers shrink at the overview: --zoom-t runs from 0 (zoom 10 and below) to 1 (zoom 13 and above), and css/style.css sizes the markers by it.
  const scaleMarkers = () => container.style.setProperty("--zoom-t", Math.min(1, Math.max(0, (map.getZoom() - 10) / 3)));
  map.on("zoom", scaleMarkers);
  scaleMarkers();
  // The footer carries the credits, so the attribution starts collapsed to its (i) button.
  map.once("load", () => container.querySelectorAll(".maplibregl-ctrl-attrib").forEach((el) => { el.classList.remove("maplibregl-compact-show"); el.removeAttribute("open"); }));
  // ready resolves once the style has loaded, and stays resolved: isStyleLoaded() goes false again while tiles load, after "load" has fired.
  return { map, markers: [], ready: map.once("load") };
}

// Fit each map to where the hexes are, once they are known (the first view is the BOUNDS guess); the linked maps keep to each other.
// The extent leaves out the outermost 1% each way, so a few stray hexes do not shrink the study area on screen.
export function fitToCells(views, cells) {
  const points = cells.map(cellToLatLng);
  const extent = (i) => {
    const sorted = points.map((point) => point[i]).sort((x, y) => x - y);
    return [sorted[Math.floor(0.01 * sorted.length)], sorted[Math.ceil(0.99 * sorted.length) - 1]];
  };
  const [[south, north], [west, east]] = [extent(0), extent(1)];
  const bounds = [[west, south], [east, north]];
  for (const view of views) view.ready.then(() => view.map.fitBounds(bounds, { padding: 24, maxZoom: 15, animate: false }));
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
