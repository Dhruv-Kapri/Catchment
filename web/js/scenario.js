// One scenario, A or B: its panel (cloned from the template) and its map. The state is its own: what is on screen, and whether a lever has moved since.
import { planScenario, STATIC } from "./api.js";
import { addSpotCheckNote } from "./assumptions.js";
import { showDemand } from "./demand.js";
import { readLevers, renderLevers, resetOthers, writeLevers } from "./levers.js";
import { createMap, showNetwork, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";
import { showCatchment, showServiceAreas } from "./planLayers.js";

// onPlanned(plan) is called when this scenario has drawn a new plan, and onStaleChange() when its metrics grey or un-grey, for whatever compares it with the other scenario.
export function mountScenario(testid, title, onPlanned, onStaleChange) {
  const section = document.querySelector(`[data-testid="${testid}"]`);
  const panel = document.getElementById("panel").content.firstElementChild.cloneNode(true);
  panel.querySelector(".title").textContent = title;
  section.append(panel);
  const form = panel.querySelector(".levers");
  const error = panel.querySelector(".error");
  const button = panel.querySelector(".plan");
  const elapsed = panel.querySelector(".elapsed");
  const metrics = panel.querySelector(".metrics");
  const view = createMap(section.querySelector(".map"));
  let planOnScreen = false;   // a plan's metrics are showing, so there is something to grey
  let storesDrawn = false;   // a plan's markers are on the map, so the bare network must not replace them
  let changedSincePlan = false;   // a lever moved after the Plan button sent the levers
  let syncCapture = () => {};   // puts the capture lever's value on the demand layer; set once the demand is drawn

  const markChanged = () => {
    changedSincePlan = true;
    if (planOnScreen) metrics.classList.add("stale");
    onStaleChange();
  };
  form.addEventListener("submit", (event) => event.preventDefault());   // Enter plans nothing and reloads nothing
  form.addEventListener("input", markChanged);

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
      storesDrawn = true;
      showStores(view, plan, (store) => showCatchment(view, plan, store).catch((e) => { error.textContent = e.message; }));
      await showCatchment(view, plan, null);
      await showServiceAreas(view, plan);
      showMetrics(panel, plan);
      planOnScreen = true;
      metrics.classList.toggle("stale", changedSincePlan);
      onStaleChange();
      onPlanned(plan);
      elapsed.textContent = `Planned in ${seconds()} s`;
    } catch (e) {
      error.textContent = e.message;
      elapsed.textContent = "";
    } finally {
      clearInterval(timer);
      button.disabled = false;
    }
  });

  return {
    view,
    readLevers: () => readLevers(form),
    // The lever inputs, from the service's ranges and defaults.
    renderLevers(levers) {
      renderLevers(form, levers);
      if (STATIC) {   // the bundle has plans with one lever moved at most; a reset capture lever recolours the demand layer too
        for (const type of ["input", "change"]) form.addEventListener(type, (e) => { resetOthers(form, e.target.name, levers); syncCapture(); });
      }
    },
    // Levers the person has not touched, set from code (copy A to B): the same effects as typing them.
    setLevers(values) {
      writeLevers(form, values);
      syncCapture();
      markChanged();
    },
    addSpotCheckNote: (text) => addSpotCheckNote(form, text),
    // After the levers: the market demand layer, which the capture lever recolours at once.
    showDemand(demand, levers) {
      const capture = () => Number(form.elements.capture?.value ?? 1);   // 1: the default share, when the levers failed to load
      const setCapture = showDemand(view, demand, capture(), panel.querySelector('[data-testid="market-demand-total"]'), levers?.capture.max ?? 1);
      syncCapture = () => setCapture(capture());
      form.elements.capture?.addEventListener("input", syncCapture);
    },
    // The existing network alone, unless a plan's markers are already drawn.
    showNetwork(network) {
      if (!storesDrawn) showNetwork(view, network);
    },
    showError(message) { error.textContent = message; },
    disablePlan() { button.disabled = true; },   // without the levers, a plan would silently be the default scenario
  };
}
