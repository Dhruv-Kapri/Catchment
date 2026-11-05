// Wiring: the Plan button asks the service, then the map and the metrics show the plan.
import { fetchDemand, fetchNetwork, planScenario } from "./api.js";
import { readLevers, renderLevers } from "./levers.js";
import { showDemand } from "./demand.js";
import { createMap, showNetwork, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";

const form = document.getElementById("levers");
const error = document.getElementById("error");
renderLevers(form);
const view = createMap("map");

// On load: the market demand layer and the existing network; the capture lever recolours the layer at once.
const capture = () => Number(form.elements.capture.value);
Promise.all([fetchDemand(), fetchNetwork()]).then(([demand, network]) => {
  const setCapture = showDemand(view, demand, capture(), document.querySelector('[data-testid="market-demand-total"]'));
  form.elements.capture.addEventListener("input", () => setCapture(capture()));
  showNetwork(view, network);
}).catch((e) => { error.textContent = e.message; });

document.getElementById("plan").addEventListener("click", async () => {
  error.textContent = "";
  try {
    const plan = await planScenario(readLevers(form));
    showStores(view, plan);
    showMetrics(plan);
  } catch (e) {
    error.textContent = e.message;
  }
});
