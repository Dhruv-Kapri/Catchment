// The operator's metrics: coverage, the gap to the solver's bound, the result against greedy, and what each new store serves.
const format = (value) => Math.round(value).toLocaleString("en-IN");
const field = (testid) => document.querySelector(`[data-testid="${testid}"]`);

function planNote(plan) {
  if (plan.method === "greedy") return "This is the greedy plan.";
  if (plan.status === "UNKNOWN") return "No plan: CP-SAT found none, or the model was over the size cap. The metrics are the existing network's.";
  if (plan.status === "HEURISTIC") return "Greedy's plan kept: CP-SAT found nothing better in time, or the model was over the size cap, so the gain over greedy is 0.";
  return "";
}

export function showMetrics(plan) {
  const unknown = plan.status === "UNKNOWN";
  field("metric-demand").textContent = format(plan.demand_covered);
  field("metric-households").textContent = format(plan.households_covered);
  field("metric-lost").textContent = format(plan.lost_to_capacity);
  field("metric-unreached").textContent = format(plan.unreached);
  field("metric-slow").textContent = format(plan.slow_traffic_coverage);
  field("metric-gap").textContent = plan.gap === null ? plan.gap_reason : `${(plan.gap * 100).toFixed(1)}%`;
  field("metric-greedy").textContent = format(plan.greedy_demand_covered);
  field("metric-gain").textContent = unknown ? "no plan" : format(plan.demand_covered - plan.greedy_demand_covered);
  field("plan-note").textContent = planNote(plan);
  field("new-stores").replaceChildren(...plan.new_stores.map((store, i) => {
    const item = document.createElement("li");
    item.textContent = `${i + 1}. fresh ${format(store.fresh)}, cannibalised ${format(store.cannibalised)}`;
    return item;
  }));
}
