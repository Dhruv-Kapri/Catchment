// The core metrics: demand and households covered, inside one scenario's panel.
const format = (value) => Math.round(value).toLocaleString("en-IN");

export function showMetrics(root, plan) {
  root.querySelector('[data-testid="metric-demand"]').textContent = format(plan.demand_covered);
  root.querySelector('[data-testid="metric-households"]').textContent = format(plan.households_covered);
}
