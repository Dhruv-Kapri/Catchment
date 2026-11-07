// The data source: the only module that knows URLs (the service or the static bundle, and the basemap style the map draws on).
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";

// Where the page runs is declared by the page itself: the live service serves the template (content="service"), the bundle build rewrites it (content="static").
const SOURCE = document.querySelector('meta[name="catchment-source"]')?.content;
if (SOURCE !== "static" && SOURCE !== "service") throw new Error('index.html must declare <meta name="catchment-source" content="static|service">');
export const STATIC = SOURCE === "static";

// The public demo has no service: plans solved ahead of time sit in bundle/. Its index is fetched on the first plan and kept.
let bundleIndex = null;

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} failed (${response.status})`);
  return response.json();
}

export async function planScenario(levers) {
  if (STATIC) {
    bundleIndex ??= getJson("bundle/index.json").catch((e) => { bundleIndex = null; throw e; });   // a failed fetch is tried again on the next plan, never answered by the service
    const entry = (await bundleIndex).find((e) => Object.keys(levers).every((name) => e.levers[name] === levers[name]));
    if (!entry) throw new Error("The static demo only has plans with one lever moved from its default.");
    return getJson(`bundle/${entry.plan}`);
  }
  const response = await fetch("/plan", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(levers),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? `plan failed (${response.status})`);
  return body;
}

// A read-only endpoint's JSON by name (for example "demand"): the live service's GET, or the bundle's copy of it.
export function readData(name) {
  return getJson(STATIC ? `bundle/data/${name}.json` : `/${name}`);
}

// Every hex with its demand (orders a day at the default capture share) and households.
export const fetchDemand = () => readData("demand");
// The existing stores of the two brands, brand -> H3 ids of their sites.
export const fetchNetwork = () => readData("network");
// The levers' ranges, steps and defaults.
export const getLevers = () => readData("levers");
// The assumptions table, the spot-check error and the synthetic network's seed and store counts.
export const fetchAssumptions = () => readData("assumptions");

export const CREDITS = [
  { text: "© OpenStreetMap contributors (ODbL)", url: "https://www.openstreetmap.org/copyright" },
  { text: "WorldPop (CC BY 4.0)", url: "https://www.worldpop.org" },
  { text: "NASA Black Marble", url: "https://blackmarble.gsfc.nasa.gov" },
  { text: "Overture", url: "https://overturemaps.org" },
  { text: "OpenFreeMap", url: "https://openfreemap.org" },
];
