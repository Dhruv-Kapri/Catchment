# Spot-check map-app times are committed

The stage 1 spot check times about 20 routes by hand in Google Maps (two-wheeler mode, weekday 7-8 pm)
and compares them with the modelled travel times. The per-route app minutes are committed in
`docs/spot-check.csv`, with the route endpoints, the app and the date and time of each lookup, so the
reported error and implied congestion multiplier can be re-derived from the repo. This is the one
deliberate exception to "never commit data", and it reverses the roadmap's earlier "numbers noted, not
stored from the app". The lookups are done once, at the stated time, by the planner or by a browser agent
the planner runs on their behalf (one route at a time, as a person would). They are a few dozen values at
most, never bulk-collected or fetched through an API, and never Places content.

## Considered Options

- **Commit only derived statistics** (error median and spread, implied multiplier) and keep the raw
  minutes off the repo: closest to the app's terms, but nobody can check the reported error.
- **An Indian map app (Ola, Mappls) instead of Google Maps:** no clear gain in terms, and Google Maps'
  two-wheeler mode is what riders and planners in the area use.

- **Hand lookups only:** what the first draft said. A browser agent run by the planner was allowed
  instead, to fit the 7-8 pm window. The trade-off is that Google's terms discourage automated access
  to Maps, accepted for about 20 one-off lookups.

## Consequences

Once pushed, the file stays in public git history even if deleted later. Any further app-sourced
numbers need their own decision; this ADR covers the spot-check file only.
