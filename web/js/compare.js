// B - A: one row per scalar metric of the plan, with the signed difference.
const MINUS = "−";
const count = (plan) => plan.sites.length;

// key, label, how to read it from a plan (null when a plan has no value), and how to format it.
const integer = (value) => Math.round(value).toLocaleString("en-IN");
const percent = (value) => `${(value * 100).toFixed(1)}%`;
const field = (name) => (plan) => plan[name];

const METRICS = [
  { key: "demand_covered", label: "Demand covered", read: field("demand_covered"), format: integer },
  { key: "households_covered", label: "Households covered", read: field("households_covered"), format: integer },
  { key: "lost_to_capacity", label: "Lost to capacity", read: field("lost_to_capacity"), format: integer },
  { key: "unreached", label: "Unreached", read: field("unreached"), format: integer },
  { key: "slow_traffic_coverage", label: "Covered in slow traffic", read: field("slow_traffic_coverage"), format: integer },
  { key: "greedy_demand_covered", label: "Greedy demand covered", read: field("greedy_demand_covered"), format: integer },
  { key: "gain_over_greedy", label: "Gain over greedy", read: (plan) => plan.demand_covered - plan.greedy_demand_covered, format: integer },
  { key: "gap", label: "Gap", read: field("gap"), format: percent },
  { key: "new_stores", label: "New stores", read: count, format: integer },
];

const show = (metric, value) => (value === null ? "–" : metric.format(value));

function signed(metric, delta) {
  if (delta === null) return "–";
  const text = metric.format(Math.abs(delta));
  if (Number(text.replace(/[^\d]/g, "")) === 0) return metric.format(0);
  return (delta > 0 ? "+" : MINUS) + text;
}

export function diffRows(a, b) {
  return METRICS.map((metric) => {
    const [from, to] = [metric.read(a), metric.read(b)];
    const delta = from === null || to === null ? null : to - from;
    return { key: metric.key, label: metric.label, a: show(metric, from), b: show(metric, to), delta: signed(metric, delta) };
  });
}

export function showDiff(table, a, b) {
  const head = document.createElement("tr");
  for (const text of ["Metric", "A", "B", "B − A"]) head.append(Object.assign(document.createElement("th"), { textContent: text }));
  const rows = diffRows(a, b).map((row) => {
    const tr = document.createElement("tr");
    tr.dataset.testid = `diff-row-${row.key}`;
    for (const text of [row.label, row.a, row.b, row.delta]) tr.append(Object.assign(document.createElement("td"), { textContent: text }));
    return tr;
  });
  table.replaceChildren(head, ...rows);
}
