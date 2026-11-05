// The lever panel. Ranges and defaults are constants for now.
export const LEVERS = {
  n_new: { label: "New stores", min: 1, max: 20, step: 1, value: 10 },
  promise: { label: "Promise (min)", min: 8, max: 16, step: 1, value: 10 },
  multiplier: { label: "Congestion multiplier", min: 1, max: 2.5, step: 0.1, value: 1.8 },
  capacity: { label: "Capacity (x)", min: 0.5, max: 2, step: 0.25, value: 1 },
  capture: { label: "Capture share (x)", min: 0.5, max: 1.5, step: 0.25, value: 1 },
  competitor_density: { label: "Competitor density (x)", min: 0, max: 2, step: 0.25, value: 1 },
};

export function renderLevers(form) {
  for (const [name, { label, min, max, step, value }] of Object.entries(LEVERS)) {
    const row = document.createElement("label");
    row.textContent = label;
    const input = Object.assign(document.createElement("input"), { type: "number", name, min, max, step, value });
    input.dataset.testid = `lever-${name}`;
    row.append(input);
    form.append(row);
  }
}

export function readLevers(form) {
  return Object.fromEntries(Object.keys(LEVERS).map((name) => [name, Number(form.elements[name].value)]));
}

// Every lever but `name` back to its default (the static demo only has plans with one lever moved).
export function resetOthers(form, name) {
  for (const [other, { value }] of Object.entries(LEVERS)) {
    if (other !== name) form.elements[other].value = value;
  }
}
