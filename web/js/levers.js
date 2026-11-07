// The lever panel. Ranges, steps, defaults and labels all come from the service (api.getLevers).

export function renderLevers(form, levers) {
  for (const [name, { min, max, step, default: value, label }] of Object.entries(levers)) {
    const row = document.createElement("label");
    row.textContent = label ?? name;
    const input = Object.assign(document.createElement("input"), { type: "number", name, min, max, step, value });
    input.dataset.testid = `lever-${name}`;
    row.append(input);
    form.append(row);
  }
}

export function readLevers(form) {
  return Object.fromEntries([...form.elements].filter((el) => el.name).map((el) => [el.name, Number(el.value)]));
}

// Every lever but `name` back to its default (the static demo only has plans with one lever moved).
export function resetOthers(form, name, levers) {
  for (const [other, { default: value }] of Object.entries(levers)) {
    if (other !== name) form.elements[other].value = value;
  }
}

// The inverse of readLevers: put each named lever's value into the form (it fires no input event).
export function writeLevers(form, values) {
  for (const [name, value] of Object.entries(values)) form.elements[name].value = value;
}
