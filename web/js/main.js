// Wiring: two scenarios, A and B, each a lever panel and a map (scenario.js). Each Plan button asks the data source, then its own map and metrics show the plan.
// The levers, the demand, the network and the assumptions are fetched once and drawn on both.
import { fetchDemand, fetchNetwork, getLevers, STATIC } from "./api.js";
import { renderAssumptions, renderCredits } from "./assumptions.js";
import { showDiff } from "./compare.js";
import { linkMaps } from "./map.js";
import { mountScenario } from "./scenario.js";

const plans = { a: null, b: null };   // the last plan of each scenario
const diff = document.getElementById("diff");
const planned = (side) => (plan) => {
  plans[side] = plan;
  if (plans.a && plans.b) showDiff(diff, plans.a, plans.b);
};

const a = mountScenario("scenario-a", "Scenario A", planned("a"));
const b = mountScenario("scenario-b", "Scenario B", planned("b"));
const scenarios = [a, b];
linkMaps(a.view, b.view);
window.catchment = { a: a.view, b: b.view };   // test hook: the linked-map test drives the maps directly
const showError = (e) => scenarios.forEach((s) => s.showError(e.message));   // a failure of something both scenarios share

renderCredits(document.getElementById("credits"));
const drawer = document.getElementById("assumptions-drawer");
document.getElementById("assumptions-button").addEventListener("click", () => { drawer.hidden = !drawer.hidden; });
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
