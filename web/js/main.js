// Wiring: the levers come from the service; the Plan button asks it, then the map and the metrics show the plan.
import { fetchDemand, fetchNetwork, getLevers, planScenario } from "./api.js";
import { renderAssumptions, renderCredits } from "./assumptions.js";
import { readLevers, renderLevers } from "./levers.js";
import { showDemand } from "./demand.js";
import { createMap, showNetwork, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";
import { showCatchment, showServiceAreas } from "./planLayers.js";

const form = document.getElementById("levers");
const error = document.getElementById("error");
const button = document.getElementById("plan");
const elapsed = document.querySelector('[data-testid="elapsed"]');
const metrics = document.getElementById("metrics");
export const view = createMap("map");
let planOnScreen = false;   // a plan's metrics are showing, so there is something to grey
let changedSincePlan = false;   // a lever moved after the Plan button sent the levers
renderCredits(document.getElementById("credits"));
const drawer = document.getElementById("assumptions-drawer");
document.getElementById("assumptions-button").addEventListener("click", () => { drawer.hidden = !drawer.hidden; });

form.addEventListener("submit", (event) => event.preventDefault());   // Enter plans nothing and reloads nothing
form.addEventListener("input", () => {
  changedSincePlan = true;
  if (planOnScreen) metrics.classList.add("stale");
});

let levers = null;   // ranges, steps and defaults from the service
try {
  levers = await getLevers();
  renderLevers(form, levers);
} catch (e) {
  error.textContent = e.message;
  button.disabled = true;   // without the levers, a plan would silently be the default scenario
}
renderAssumptions(drawer, form).catch((e) => { error.textContent = e.message; });   // after the levers: the spot-check note sits by the congestion lever

// After the levers: the market demand layer and the existing network; the capture lever recolours the layer at once.
const capture = () => Number(form.elements.capture?.value ?? 1);   // 1: the default share, when the levers failed to load
Promise.all([fetchDemand(), fetchNetwork()]).then(([demand, network]) => {
  const setCapture = showDemand(view, demand, capture(), document.querySelector('[data-testid="market-demand-total"]'),
    levers?.capture.max ?? 1);
  form.elements.capture?.addEventListener("input", () => setCapture(capture()));
  if (!planOnScreen) showNetwork(view, network);   // a plan drawn first already shows the network
}).catch((e) => { error.textContent = e.message; });

button.addEventListener("click", async () => {
  error.textContent = "";
  button.disabled = true;
  changedSincePlan = false;
  const started = performance.now();
  const seconds = () => ((performance.now() - started) / 1000).toFixed(1);
  elapsed.textContent = "Planning… 0.0 s";
  const timer = setInterval(() => (elapsed.textContent = `Planning… ${seconds()} s`), 100);
  try {
    const plan = await planScenario(readLevers(form));
    showStores(view, plan, (store) => showCatchment(view, plan, store).catch((e) => { error.textContent = e.message; }));
    await showCatchment(view, plan, null);
    await showServiceAreas(view, plan);
    showMetrics(plan);
    planOnScreen = true;
    metrics.classList.toggle("stale", changedSincePlan);
    elapsed.textContent = `Planned in ${seconds()} s`;
  } catch (e) {
    error.textContent = e.message;
    elapsed.textContent = "";
  } finally {
    clearInterval(timer);
    button.disabled = false;
  }
});
