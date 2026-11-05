// The market demand layer: every hex coloured by orders a day, both brands, before the brand split.
// Market demand = the stored demand x the capture lever, so the layer follows the lever without a refetch.
import { cellToBoundary } from "h3-js";
import { LEVERS } from "./levers.js";

const SOURCE = "market-demand";
export const RAMP = ["#ffffcc", "#fd8d3c", "#800026"];   // low to high; the top is the busiest hex at the highest capture share

const format = (value) => Math.round(value).toLocaleString("en-IN");

function fillColour(capture, top) {
  return ["interpolate", ["linear"], ["*", ["get", "demand"], capture],
    0, "rgba(255, 255, 204, 0)", top / 2, RAMP[1], top, RAMP[2]];
}

// Draws the layer once the basemap style has loaded; returns setCapture(capture) to recolour it and update the total.
export function showDemand(view, records, capture, totalElement) {
  const top = Math.max(...records.map((r) => r.demand)) * LEVERS.capture.max || 1;
  const features = records.map(({ hex, demand }) => ({
    type: "Feature",
    properties: { demand },
    geometry: { type: "Polygon", coordinates: [cellToBoundary(hex, true)] },
  }));
  const stored = records.reduce((sum, r) => sum + r.demand, 0);
  const setCapture = (value) => {
    totalElement.textContent = format(stored * value);
    if (view.map.getLayer(SOURCE)) view.map.setPaintProperty(SOURCE, "fill-color", fillColour(value, top));
  };
  const draw = () => {
    view.map.addSource(SOURCE, { type: "geojson", data: { type: "FeatureCollection", features } });
    view.map.addLayer({ id: SOURCE, type: "fill", source: SOURCE,
      paint: { "fill-color": fillColour(capture, top), "fill-opacity": 0.6 } });
  };
  if (view.map.isStyleLoaded()) draw(); else view.map.once("load", draw);
  setCapture(capture);
  return setCapture;
}
