// The lever panel. Ranges, steps and defaults come from the service (api.getLevers); only the labels live here.
const LABELS = {
  n_new: "New stores",
  promise: "Promise (min)",
  multiplier: "Congestion multiplier",
  capacity: "Capacity (x)",
  capture: "Capture share (x)",
  competitor_density: "Competitor density (x)",
};

export function renderLevers(form, levers) {
  for (const [name, { min, max, step, default: value }] of Object.entries(levers)) {
    const row = document.createElement("label");
    row.textContent = LABELS[name] ?? name;
    const input = Object.assign(document.createElement("input"), { type: "number", name, min, max, step, value });
    input.dataset.testid = `lever-${name}`;
    row.append(input);
    form.append(row);
  }
}

export function readLevers(form) {
  return Object.fromEntries([...form.elements].filter((el) => el.name).map((el) => [el.name, Number(el.value)]));
}
