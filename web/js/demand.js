// The market demand layer: every hex coloured by orders a day, both brands, before the brand split.
// Market demand = the stored demand x the capture lever, so the layer follows the lever without a refetch.
import { cellToBoundary } from "h3-js";

const LAYER = "market-demand";   // the id of both the source and the layer
const RAMP = ["#ffffcc", "#fd8d3c", "#800026"];   // low to high, as the legend in index.html; the top is the busiest hex at the highest capture share

const format = (value) => Math.round(value).toLocaleString("en-IN");

function fillColour(capture, top) {
  return ["interpolate", ["linear"], ["*", ["get", "demand"], capture],
    0, "rgba(255, 255, 204, 0)", top / 2, RAMP[1], top, RAMP[2]];
}

// Draws the layer once the basemap style has loaded; returns setCapture(capture) to recolour it and update the total.
// captureMax: the capture lever's top (GET /levers), so the ramp's top stays fixed as the lever moves.
export function showDemand(view, records, capture, totalElement, captureMax) {
  const top = Math.max(...records.map((r) => r.demand)) * captureMax || 1;
  const features = records.map(({ hex, demand }) => ({
    type: "Feature",
    properties: { demand },
    geometry: { type: "Polygon", coordinates: [cellToBoundary(hex, true)] },
  }));
  const stored = records.reduce((sum, r) => sum + r.demand, 0);
  let current = capture;   // the lever may move before the style loads; draw with its latest value
  const setCapture = (value) => {
    current = value;
    totalElement.textContent = format(stored * value);
    if (view.map.getLayer(LAYER)) view.map.setPaintProperty(LAYER, "fill-color", fillColour(value, top));
  };
  const draw = () => {
    view.map.addSource(LAYER, { type: "geojson", data: { type: "FeatureCollection", features } });
    view.map.addLayer({ id: LAYER, type: "fill", source: LAYER,
      paint: { "fill-color": fillColour(current, top), "fill-opacity": 0.6 } });
  };
  if (view.map.isStyleLoaded()) draw(); else view.map.once("load", draw);
  setCapture(capture);
  return setCapture;
}
