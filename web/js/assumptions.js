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
  const to = s.looked_up_to.split(" ").pop();   // the time only: every route was looked up the same evening
  return `Spot check: ${s.routes} routes in ${s.app}, one evening's live estimates (${s.looked_up_from}-${to}). ` +
    `The app times imply a congestion multiplier of ${f(s.implied_median)} (25th-75th percentile ${f(s.implied_q25)}-${f(s.implied_q75)}); ` +
    `at the default ×${s.multiplier} the app took a median ${f(s.ratio_median)}× the modelled time (${f(s.ratio_q25)}-${f(s.ratio_q75)}).`;
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

// Fetches the assumptions once and fills the drawer; returns the spot-check note's text for addSpotCheckNote, once per lever form.
export async function renderAssumptions(drawer) {
  const { table, spot_check: spot, network } = await fetchAssumptions();
  const { Operator, Competitor } = network.stores;
  drawer.replaceChildren(
    element("h2", "Assumptions"),
    element("p", `The existing network is synthetic, not real stores: placed by seed ${network.seed} (fixed, not a lever). At the default competitor density it has ${Operator} Operator and ${Competitor} Competitor stores.`, "network-seed"),
    renderTable(table),
  );
  return spotCheckText(spot);
}

export function addSpotCheckNote(form, text) {
  form.elements.multiplier?.closest("label").after(element("p", text, "spot-check-note"));
}
