// Wiring: two scenarios, A and B, each a lever panel and a map. Each Plan button asks the service, then its own map and metrics show the plan.
// The levers, the demand, the network and the assumptions are fetched once and drawn on both.
import { fetchDemand, fetchNetwork, getLevers, planScenario, STATIC } from "./api.js";
import { addSpotCheckNote, renderAssumptions, renderCredits } from "./assumptions.js";
import { showDiff } from "./compare.js";
import { readLevers, renderLevers, resetOthers, writeLevers } from "./levers.js";
import { showDemand } from "./demand.js";
import { createMap, linkMaps, showNetwork, showStores } from "./map.js";
import { showMetrics } from "./metrics.js";
import { showCatchment, showServiceAreas } from "./planLayers.js";

const plans = { a: null, b: null };   // the last plan of each scenario
const diff = document.getElementById("diff");

// One scenario: its panel (cloned from the template) and its map. The state is its own: what is on screen, and whether a lever has moved since.
function mountScenario(testid, title, side) {
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
  const scenario = { view, form, error, button, planOnScreen: false, syncCapture: () => {} };   // planOnScreen: a plan's metrics are showing, so there is something to grey
  let changedSincePlan = false;   // a lever moved after the Plan button sent the levers

  const markChanged = () => {
    changedSincePlan = true;
    if (scenario.planOnScreen) metrics.classList.add("stale");
  };
  form.addEventListener("submit", (event) => event.preventDefault());   // Enter plans nothing and reloads nothing
  form.addEventListener("input", markChanged);
  // Levers the person has not touched, set from code (copy A to B): the same effects as typing them.
  scenario.setLevers = (values) => {
    writeLevers(form, values);
    scenario.syncCapture();
    markChanged();
  };

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
      showMetrics(panel, plan);
      scenario.planOnScreen = true;
      metrics.classList.toggle("stale", changedSincePlan);
      plans[side] = plan;
      if (plans.a && plans.b) showDiff(diff, plans.a, plans.b);
      elapsed.textContent = `Planned in ${seconds()} s`;
    } catch (e) {
      error.textContent = e.message;
      elapsed.textContent = "";
    } finally {
      clearInterval(timer);
      button.disabled = false;
    }
  });

  // After the levers: the market demand layer, which the capture lever recolours at once.
  scenario.showDemand = (demand, levers) => {
    const capture = () => Number(form.elements.capture?.value ?? 1);   // 1: the default share, when the levers failed to load
    const setCapture = showDemand(view, demand, capture(), panel.querySelector('[data-testid="market-demand-total"]'), levers?.capture.max ?? 1);
    scenario.syncCapture = () => setCapture(capture());
    form.elements.capture?.addEventListener("input", scenario.syncCapture);
  };
  return scenario;
}

const scenarios = [mountScenario("scenario-a", "Scenario A", "a"), mountScenario("scenario-b", "Scenario B", "b")];
const [a, b] = scenarios;
linkMaps(a.view, b.view);
window.catchment = { a: a.view, b: b.view };   // test hook: the linked-map test drives the maps directly
const showError = (e) => scenarios.forEach((s) => { s.error.textContent = e.message; });   // a failure of something both scenarios share

renderCredits(document.getElementById("credits"));
const drawer = document.getElementById("assumptions-drawer");
document.getElementById("assumptions-button").addEventListener("click", () => { drawer.hidden = !drawer.hidden; });
document.getElementById("static-notice").hidden = !STATIC;
document.getElementById("copy-a-to-b").addEventListener("click", () => b.setLevers(readLevers(a.form)));   // B starts as a copy of A: both open on the defaults

let levers = null;   // ranges, steps and defaults from the service
try {
  levers = await getLevers();
  for (const s of scenarios) {
    renderLevers(s.form, levers);
    if (STATIC) {   // the bundle has plans with one lever moved at most; a reset capture lever recolours the demand layer too
      for (const type of ["input", "change"]) s.form.addEventListener(type, (e) => { resetOthers(s.form, e.target.name, levers); s.syncCapture(); });
    }
  }
} catch (e) {
  showError(e);
  scenarios.forEach((s) => { s.button.disabled = true; });   // without the levers, a plan would silently be the default scenario
}
renderAssumptions(drawer).then((text) => scenarios.forEach((s) => addSpotCheckNote(s.form, text))).catch(showError);   // after the levers: each spot-check note sits by its congestion lever

Promise.all([fetchDemand(), fetchNetwork()]).then(([demand, network]) => {
  for (const s of scenarios) {
    s.showDemand(demand, levers);
    if (!s.planOnScreen) showNetwork(s.view, network);   // a plan drawn first already shows the network
  }
}).catch(showError);
