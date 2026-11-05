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
let shown = false;   // a plan is on screen, so there is something to grey

form.addEventListener("submit", (event) => event.preventDefault());   // Enter plans nothing and reloads nothing
form.addEventListener("input", () => {
  if (shown) metrics.classList.add("stale");
});

try {
  renderLevers(form, await getLevers());
} catch (e) {
  error.textContent = e.message;
}

button.addEventListener("click", async () => {
  error.textContent = "";
  button.disabled = true;
  const started = performance.now();
  const seconds = () => ((performance.now() - started) / 1000).toFixed(1);
  elapsed.textContent = "Planning… 0.0 s";
  const timer = setInterval(() => (elapsed.textContent = `Planning… ${seconds()} s`), 100);
  try {
    const plan = await planScenario(readLevers(form));
    showStores(view, plan);
    showMetrics(plan);
    shown = true;
    metrics.classList.remove("stale");
    elapsed.textContent = `Planned in ${seconds()} s`;
  } catch (e) {
    error.textContent = e.message;
    elapsed.textContent = "";
  } finally {
    clearInterval(timer);
    button.disabled = false;
  }
});
