// The operator's metrics: coverage, the gap to the stated bound (the solver's or the capacity bound), the result against greedy, and what each new store serves.
import { integer, percent } from "./format.js";

// root: one scenario's panel, so the two scenarios' metrics never mix.
export function showMetrics(root, plan) {
  const field = (testid) => root.querySelector(`[data-testid="${testid}"]`);
  const unknown = plan.status === "UNKNOWN";
  field("metric-demand").textContent = integer(plan.demand_covered);
  field("metric-households").textContent = integer(plan.households_covered);
  field("metric-lost").textContent = integer(plan.lost_to_capacity);
  field("metric-unreached").textContent = integer(plan.unreached);
  field("metric-slow").textContent = integer(plan.slow_traffic_coverage);
  const source = plan.bound_source === "capacity" ? " (from the capacity bound, which can be loose)" : "";   // #52: not the solver's own bound
  field("metric-gap").textContent = plan.gap === null ? plan.gap_reason : percent(plan.gap) + source;
  field("metric-greedy").textContent = integer(plan.greedy_demand_covered);
  field("metric-gain").textContent = unknown ? "no plan" : integer(plan.demand_covered - plan.greedy_demand_covered);
  field("plan-note").textContent = plan.plan_note;
  const row = (tag, texts) => {
    const tr = document.createElement("tr");
    tr.append(...texts.map((textContent) => Object.assign(document.createElement(tag), { textContent })));
    return tr;
  };
  const head = document.createElement("thead");
  head.append(row("th", ["Store", "Fresh", "Cannibalised"]));
  const body = document.createElement("tbody");
  body.append(...plan.new_stores.map((store, i) => row("td", [String(i + 1), integer(store.fresh), integer(store.cannibalised)])));
  field("new-stores").replaceChildren(head, body);
}
