// The data source: the only module that knows URLs (the service or the static bundle, and the basemap style the map draws on).
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

// The public demo has no service: plans solved ahead of time sit in bundle/. On the live service this URL is a 404.
const indexResponse = await fetch("bundle/index.json").catch(() => null);
export const STATIC = Boolean(indexResponse?.ok);
const bundleIndex = STATIC ? await indexResponse.json() : [];

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} failed (${response.status})`);
  return response.json();
}

export async function planScenario(levers) {
  if (STATIC) {
    const entry = bundleIndex.find((e) => Object.keys(levers).every((name) => e.levers[name] === levers[name]));
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
