// B - A: one row per scalar metric of the plan, with the signed difference.
const MINUS = "−";
const count = (plan) => plan.sites.length;

// key, label, how to format it, and how to read it from a plan when it isn't the plan's field of that name. Only gap can be null.
const integer = (value) => Math.round(value).toLocaleString("en-IN");
const percent = (value) => `${(value * 100).toFixed(1)}%`;
const points = (value) => `${(value * 100).toFixed(1)} pp`;   // a difference of two percentages

const METRICS = [
  { key: "demand_covered", label: "Demand covered", format: integer },
  { key: "households_covered", label: "Households covered", format: integer },
  { key: "lost_to_capacity", label: "Lost to capacity", format: integer },
  { key: "unreached", label: "Unreached", format: integer },
  { key: "slow_traffic_coverage", label: "Covered in slow traffic", format: integer },
  { key: "greedy_demand_covered", label: "Greedy demand covered", format: integer },
  { key: "gain_over_greedy", label: "Gain over greedy", read: (plan) => plan.demand_covered - plan.greedy_demand_covered, format: integer },
  { key: "gap", label: "Gap", format: percent, deltaFormat: points },
  { key: "new_stores", label: "New stores", read: count, format: integer },
];

const read = (metric, plan) => (metric.read ? metric.read(plan) : plan[metric.key]);
const show = (metric, value) => (value === null ? "–" : metric.format(value));

function signed(metric, delta) {
  if (delta === null) return "–";
  const format = metric.deltaFormat ?? metric.format;
  const text = format(Math.abs(delta));
  return text === format(0) ? text : (delta > 0 ? "+" : MINUS) + text;   // a delta that rounds to zero shows unsigned
}

export function diffRows(a, b) {
  return METRICS.map((metric) => {
    const [from, to] = [read(metric, a), read(metric, b)];
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
