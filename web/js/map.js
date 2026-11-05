// The map: the basemap and the stores drawn on it. Each createMap call is its own map, so a page can hold several.
import { cellToLatLng } from "h3-js";
import { BASEMAP_STYLE } from "./api.js";

const CENTRE = [77.10, 28.48];   // lng, lat: Gurugram / South Delhi

export function createMap(container) {
  const map = new maplibregl.Map({ container, style: BASEMAP_STYLE, center: CENTRE, zoom: 11 });
  map.addControl(new maplibregl.NavigationControl());
  return { map, markers: [] };
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
