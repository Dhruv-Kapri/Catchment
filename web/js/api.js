// The data source: the only module that knows URLs (the service, and the basemap style the map draws on).
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

export async function planScenario(levers) {
  const response = await fetch("/plan", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(levers),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? `plan failed (${response.status})`);
  return body;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} failed (${response.status})`);
  return response.json();
}

// Every hex with its demand (orders a day at the default capture share) and households.
export const fetchDemand = () => getJson("/demand");
// The existing stores of the two brands, brand -> H3 ids of their sites.
export const fetchNetwork = () => getJson("/network");
