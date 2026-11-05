// Wiring: each scenario's Plan button asks the service, then its map and metrics show the plan.
import { planScenario } from "./api.js";
import { showDiff } from "./compare.js";
import { readLevers, renderLevers, writeLevers } from "./levers.js";
import { createMap, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";

const plans = { a: null, b: null };   // the last plan of each scenario
const diff = document.getElementById("diff");

function mountScenario(testid, title, side) {
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
      plans[side] = plan;
      if (plans.a && plans.b) showDiff(diff, plans.a, plans.b);
    } catch (e) {
      error.textContent = e.message;
    }
  });
  return { view, form };
}

const a = mountScenario("scenario-a", "Scenario A", "a");
const b = mountScenario("scenario-b", "Scenario B", "b");
writeLevers(b.form, readLevers(a.form));
document.getElementById("copy-a-to-b").addEventListener("click", () => writeLevers(b.form, readLevers(a.form)));
window.catchment = { a: a.view, b: b.view };   // test hook: the linked-map test drives the maps directly
