// The data source: the only module that knows where the service lives.
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
