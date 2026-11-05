// The core metrics: demand and households covered.
const format = (value) => Math.round(value).toLocaleString("en-IN");

export function showMetrics(plan) {
  document.querySelector('[data-testid="metric-demand"]').textContent = format(plan.demand_covered);
  document.querySelector('[data-testid="metric-households"]').textContent = format(plan.households_covered);
}
