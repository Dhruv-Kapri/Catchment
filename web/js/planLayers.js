// What a plan adds to the map besides the markers: each operator store's service area as fill, the selected store's catchment as an outline (the other service areas dim while a store is selected).
import { cellToBoundary, cellsToMultiPolygon } from "h3-js";
import { markSelected } from "./map.js";

// One colour per store, cycled through a muted categorical palette: neighbouring areas stay apart without one loud hue per store.
const PALETTE = ["#7a9bbf", "#e0a06a", "#7fb08f", "#cf7f80", "#a692c2", "#c2a679", "#dd9fb8", "#98a0a8", "#bdbd6c", "#72b5bd"];
const colour = (index) => PALETTE[index % PALETTE.length];
const OPACITY = 0.38;   // the service areas' fill; a selected store's own area keeps it and the others dim
const DIMMED = 0.08;
const EMPTY = { type: "FeatureCollection", features: [] };

// Sources and layers can be added only once the style has loaded (view.ready).
async function ensureLayers(view) {
  await view.ready;
  const { map } = view;
  if (map.getSource("service-areas")) return;
  map.addSource("service-areas", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "service-areas", type: "fill", source: "service-areas", paint: { "fill-color": ["get", "colour"], "fill-opacity": OPACITY, "fill-outline-color": "#ffffff" } });
  map.addSource("catchment-outline", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "catchment-outline", type: "line", source: "catchment-outline", paint: { "line-color": "#123b39", "line-width": 3 } });
}

// One fill feature per served hex, coloured by its store; hexes no operator store serves have no feature.
export async function showServiceAreas(view, plan) {
  await ensureLayers(view);
  const features = Object.entries(plan.service_areas).flatMap(([store, cells], index) =>
    cells.map((cell) => ({
      type: "Feature",
      properties: { store, cell, colour: colour(index) },
      geometry: { type: "Polygon", coordinates: [cellToBoundary(cell, true)] },
    })));
  view.map.getSource("service-areas").setData({ type: "FeatureCollection", features });
}

// Outline the outer boundary of the store's catchment; no store (or one with no catchment) clears the outline.
export async function showCatchment(view, plan, store) {
  await ensureLayers(view);
  const cells = plan.catchments[store];
  markSelected(view, cells ? store : null);
  const features = cells ? [{ type: "Feature", properties: { store }, geometry: { type: "MultiPolygon", coordinates: cellsToMultiPolygon(cells, true) } }] : [];
  view.map.setPaintProperty("service-areas", "fill-opacity", cells ? ["case", ["==", ["get", "store"], store], OPACITY + 0.12, DIMMED] : OPACITY);
  view.map.getSource("catchment-outline").setData({ type: "FeatureCollection", features });
}
