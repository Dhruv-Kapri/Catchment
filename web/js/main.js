// Wiring: the Plan button asks the service, then the map and the metrics show the plan.
import { planScenario, STATIC } from "./api.js";
import { readLevers, renderLevers, resetOthers } from "./levers.js";
import { createMap, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";

const form = document.getElementById("levers");
const error = document.getElementById("error");
document.getElementById("static-notice").hidden = !STATIC;
renderLevers(form);
if (STATIC) {
  for (const type of ["input", "change"]) form.addEventListener(type, (e) => resetOthers(form, e.target.name));
}
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
