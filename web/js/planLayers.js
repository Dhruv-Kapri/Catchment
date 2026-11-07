// What a plan adds to the map besides the markers: each operator store's service area as fill, the selected store's catchment as an outline.
import { cellToBoundary, cellsToMultiPolygon } from "h3-js";
import { markSelected } from "./map.js";

// One colour per store: hues a golden angle apart never repeat, however many stores the plan has.
const colour = (index) => `hsl(${(index * 137.508) % 360}, 70%, 45%)`;
const EMPTY = { type: "FeatureCollection", features: [] };

// Sources and layers can be added only once the style has loaded (view.ready).
async function ensureLayers(view) {
  await view.ready;
  const { map } = view;
  if (map.getSource("service-areas")) return;
  map.addSource("service-areas", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "service-areas", type: "fill", source: "service-areas", paint: { "fill-color": ["get", "colour"], "fill-opacity": 0.4, "fill-outline-color": "#ffffff" } });
  map.addSource("catchment-outline", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "catchment-outline", type: "line", source: "catchment-outline", paint: { "line-color": "#111111", "line-width": 3 } });
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
  view.map.getSource("catchment-outline").setData({ type: "FeatureCollection", features });
}
