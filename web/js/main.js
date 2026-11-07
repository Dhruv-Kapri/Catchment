// Wiring: two scenarios, A and B, each a lever panel and a map (scenario.js). Each Plan button asks the data source, then its own map and metrics show the plan.
// The levers, the demand, the network and the assumptions are fetched once and drawn on both.
import { fetchDemand, fetchNetwork, getLevers, STATIC } from "./api.js";
import { renderAssumptions, renderCredits } from "./assumptions.js";
import { showDiff } from "./compare.js";
import { linkMaps } from "./map.js";
import { mountScenario } from "./scenario.js";

const plans = { a: null, b: null };   // the last plan of each scenario
const diff = document.getElementById("diff");
const refreshDiffStale = () => diff.classList.toggle("stale", document.querySelector(".metrics.stale") !== null);   // the table greys while either scenario's metrics are grey
const planned = (side) => (plan) => {
  plans[side] = plan;
  if (plans.a && plans.b) showDiff(diff, plans.a, plans.b);
};

const a = mountScenario("scenario-a", "Scenario A", planned("a"), refreshDiffStale);
const b = mountScenario("scenario-b", "Scenario B", planned("b"), refreshDiffStale);
const scenarios = [a, b];
linkMaps(a.view, b.view);
window.catchment = { a: a.view, b: b.view };   // test hook: the linked-map test drives the maps directly
const showError = (e) => scenarios.forEach((s) => s.showError(e.message));   // a failure of something both scenarios share

renderCredits(document.getElementById("credits"));
const drawer = document.getElementById("assumptions-drawer");
const toggleDrawer = (open = drawer.hidden) => { drawer.hidden = !open; };
document.getElementById("assumptions-button").addEventListener("click", () => toggleDrawer());
drawer.querySelector(".drawer-close").addEventListener("click", () => toggleDrawer(false));
document.addEventListener("keydown", (event) => { if (event.key === "Escape") toggleDrawer(false); });
const compare = document.getElementById("compare");
const compareToggle = document.getElementById("compare-toggle");
compareToggle.addEventListener("click", () => {   // collapsing hides the table, not the Copy A to B button
  const collapsed = compare.classList.toggle("collapsed");
  compareToggle.textContent = collapsed ? "Show" : "Hide";
  compareToggle.setAttribute("aria-expanded", String(!collapsed));
});
document.getElementById("static-notice").hidden = !STATIC;
document.getElementById("copy-a-to-b").addEventListener("click", () => b.setLevers(a.readLevers()));   // B starts as a copy of A: both open on the defaults

let levers = null;   // ranges, steps and defaults from the service
try {
  levers = await getLevers();
  scenarios.forEach((s) => s.renderLevers(levers));
} catch (e) {
  showError(e);
  scenarios.forEach((s) => s.disablePlan());
}
renderAssumptions(drawer).then((text) => scenarios.forEach((s) => s.addSpotCheckNote(text))).catch(showError);   // after the levers: each spot-check note sits by its congestion lever

Promise.all([fetchDemand(), fetchNetwork()]).then(([demand, network]) => {
  for (const s of scenarios) {
    s.showDemand(demand, levers);
    s.showNetwork(network);
  }
}).catch(showError);
