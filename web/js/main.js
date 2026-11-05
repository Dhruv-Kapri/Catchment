// Wiring: the levers come from the service; the Plan button asks it, then the map and the metrics show the plan.
import { getLevers, planScenario } from "./api.js";
import { readLevers, renderLevers } from "./levers.js";
import { createMap, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";

const form = document.getElementById("levers");
const error = document.getElementById("error");
const button = document.getElementById("plan");
const elapsed = document.querySelector('[data-testid="elapsed"]');
const metrics = document.getElementById("metrics");
const view = createMap("map");
let planOnScreen = false;   // a plan's metrics are showing, so there is something to grey
let changedSincePlan = false;   // a lever moved after the Plan button sent the levers

form.addEventListener("submit", (event) => event.preventDefault());   // Enter plans nothing and reloads nothing
form.addEventListener("input", () => {
  changedSincePlan = true;
  if (planOnScreen) metrics.classList.add("stale");
});

try {
  renderLevers(form, await getLevers());
} catch (e) {
  error.textContent = e.message;
  button.disabled = true;   // without the levers, a plan would silently be the default scenario
}

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
    showStores(view, plan);
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
