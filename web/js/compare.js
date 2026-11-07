// B - A: one row per scalar metric of the plan, with the signed difference.
import { integer, percent, points } from "./format.js";

const MINUS = "−";
const count = (plan) => plan.sites.length;

// better: which way is good news (up or down), for tinting the difference; no better, no tint.
// key, label, how to format it, and how to read it from a plan when it isn't the plan's field of that name. Only gap can be null.
const METRICS = [
  { key: "demand_covered", better: "up", label: "Demand covered", format: integer },
  { key: "households_covered", better: "up", label: "Households covered", format: integer },
  { key: "lost_to_capacity", better: "down", label: "Lost to capacity", format: integer },
  { key: "unreached", better: "down", label: "Unreached", format: integer },
  { key: "slow_traffic_coverage", better: "up", label: "Covered in slow traffic", format: integer },
  { key: "greedy_demand_covered", better: "up", label: "Greedy demand covered", format: integer },
  { key: "gain_over_greedy", better: "up", label: "Gain over greedy", read: (plan) => plan.demand_covered - plan.greedy_demand_covered, format: integer },
  { key: "gap", better: "down", label: "Gap", format: percent, deltaFormat: points,
    suffix: (plan) => (plan.bound_source === "capacity" ? " (capacity bound)" : ""),   // #52: not the solver's own bound
    comparable: (a, b) => a.bound_source === b.bound_source },   // a capacity-bound gap minus a solver-bound gap says nothing
  { key: "new_stores", label: "New stores", read: count, format: integer },
];

const read = (metric, plan) => (metric.read ? metric.read(plan) : plan[metric.key]);
const show = (metric, value, plan) => (value === null ? "–" : metric.format(value) + (metric.suffix?.(plan) ?? ""));

function signed(metric, delta) {
  if (delta === null) return "–";
  const format = metric.deltaFormat ?? metric.format;
  const text = format(Math.abs(delta));
  return text === format(0) ? text : (delta > 0 ? "+" : MINUS) + text;   // a delta that rounds to zero shows unsigned
}

const TONE = { "+": { up: "good", down: "bad" }, [MINUS]: { up: "bad", down: "good" } };   // a rounded-to-zero or missing difference has no sign, so no tone

export function diffRows(a, b) {
  return METRICS.map((metric) => {
    const [from, to] = [read(metric, a), read(metric, b)];
    const delta = from === null || to === null || metric.comparable?.(a, b) === false ? null : to - from;
    const text = signed(metric, delta);
    return { key: metric.key, label: metric.label, a: show(metric, from, a), b: show(metric, to, b), delta: text, tone: TONE[text[0]]?.[metric.better] ?? "" };
  });
}

export function showDiff(table, a, b) {
  const head = document.createElement("tr");
  for (const text of ["Metric", "A", "B", "B − A"]) head.append(Object.assign(document.createElement("th"), { textContent: text }));
  const rows = diffRows(a, b).map((row) => {
    const tr = document.createElement("tr");
    tr.dataset.testid = `diff-row-${row.key}`;
    for (const text of [row.label, row.a, row.b, row.delta]) tr.append(Object.assign(document.createElement("td"), { textContent: text }));
    tr.lastElementChild.className = row.tone;   // good news teal, bad news rust
    return tr;
  });
  table.replaceChildren(head, ...rows);
}
