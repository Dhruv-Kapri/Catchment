// Wiring: each scenario's Plan button asks the service, then its map and metrics show the plan.
import { planScenario } from "./api.js";
import { readLevers, renderLevers } from "./levers.js";
import { createMap, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";

function mountScenario(testid, title) {
  const section = document.querySelector(`[data-testid="${testid}"]`);
  const panel = document.getElementById("panel").content.firstElementChild.cloneNode(true);
  panel.querySelector("h2").textContent = title;
  section.append(panel);
  const form = panel.querySelector(".levers");
  const error = panel.querySelector(".error");
  renderLevers(form);
  const view = createMap(section.querySelector(".map"));
  panel.querySelector(".plan").addEventListener("click", async () => {
    error.textContent = "";
    try {
      const plan = await planScenario(readLevers(form));
      showStores(view, plan);
      showMetrics(panel, plan);
    } catch (e) {
      error.textContent = e.message;
    }
  });
  return view;
}

const viewA = mountScenario("scenario-a", "Scenario A");
const viewB = mountScenario("scenario-b", "Scenario B");
window.catchment = { a: viewA, b: viewB };   // test hook: the linked-map test drives the maps directly
