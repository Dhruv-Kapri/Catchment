// Wiring: the Plan button asks the service, then the map and the metrics show the plan.
import { planScenario } from "./api.js";
import { readLevers, renderLevers } from "./levers.js";
import { createMap, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";

const form = document.getElementById("levers");
const error = document.getElementById("error");
renderLevers(form);
const view = createMap("map");

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
