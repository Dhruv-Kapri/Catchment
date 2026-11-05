// Every number traces to a stated assumption: the assumptions drawer, the spot-check note by the congestion lever, and the credits.
import { CREDITS, fetchAssumptions } from "./api.js";

const COLUMNS = ["Input", "Value", "Source", "Date", "Status"];

function element(tag, text, testid) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (testid) node.dataset.testid = testid;
  return node;
}

function spotCheckText(s) {
  const f = (x) => x.toFixed(2);
  return `Spot check: ${s.routes} routes, ${s.app}, ${s.looked_up_from}-${s.looked_up_to.slice(-5)}. ` +
    `At ×${s.multiplier} the app took a median ${f(s.ratio_median)}× the modelled time (25th-75th percentile ${f(s.ratio_q25)}-${f(s.ratio_q75)}); ` +
    `implied multiplier ${f(s.implied_median)} (${f(s.implied_q25)}-${f(s.implied_q75)}).`;
}

function renderTable(rows) {
  const table = element("table");
  table.createTHead().insertRow().append(...COLUMNS.map((c) => element("th", c)));
  const body = table.createTBody();
  for (const row of rows) body.insertRow().append(...COLUMNS.map((c) => element("td", row[c])));
  return table;
}

export function renderCredits(footer) {
  CREDITS.forEach(({ text, url }, i) => {
    if (i) footer.append(" · ");
    const link = Object.assign(element("a", text), { href: url, target: "_blank", rel: "noopener" });
    footer.append(link);
  });
}

export async function renderAssumptions(drawer, form) {
  const { table, spot_check: spot, network } = await fetchAssumptions();
  const multiplier = form.elements.multiplier.closest("label");
  multiplier.after(element("p", spotCheckText(spot), "spot-check-note"));
  const { Operator, Competitor } = network.stores;
  drawer.replaceChildren(
    element("h2", "Assumptions"),
    element("p", `The existing network is synthetic: ${Operator} Operator and ${Competitor} Competitor stores placed by seed ${network.seed}, not real stores.`, "network-seed"),
    renderTable(table),
  );
}
