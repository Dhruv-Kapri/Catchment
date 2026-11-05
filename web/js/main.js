// Wiring: the Plan button asks the service, then the map and the metrics show the plan.
import { planScenario } from "./api.js";
import { readLevers, renderLevers } from "./levers.js";
import { createMap, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";
import { showCatchment, showServiceAreas } from "./planLayers.js";

const form = document.getElementById("levers");
const error = document.getElementById("error");
renderLevers(form);
export const view = createMap("map");

document.getElementById("plan").addEventListener("click", async () => {
  error.textContent = "";
  try {
    const plan = await planScenario(readLevers(form));
    showStores(view, plan, (store) => showCatchment(view, plan, store).catch((e) => { error.textContent = e.message; }));
    await showCatchment(view, plan, null);
    await showServiceAreas(view, plan);
    showMetrics(plan);
  } catch (e) {
    error.textContent = e.message;
  }
});
