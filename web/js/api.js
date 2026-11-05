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

export async function getLevers() {
  const response = await fetch("/levers");
  if (!response.ok) throw new Error(`levers failed (${response.status})`);
  return response.json();
}
