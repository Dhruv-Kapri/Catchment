# The public demo is a static site whose plans are committed to a gh-pages branch, under the ODbL

Stage 3's public URL serves the web map as a static site on GitHub Pages. It reads plans solved ahead of time on
the dev machine: the default scenario and each lever swept on its own (about 61 plans), plus each hex's
demand and the candidate sites as JSON. The JSON is committed to an orphan `gh-pages` branch, the second deliberate
exception to "never commit data" after [ADR 0002](0002-spot-check-times-in-repo.md). `main` and the stage branches
still hold no data. The live FastAPI service (`POST /plan`, any scenario in the lever ranges) runs locally only. The
~90 s recording is made against it.

The plans are computed from travel times routed on OpenStreetMap roads, so the published JSON is treated as a
Derivative Database under the ODbL 1.0 (share-alike), not only a Produced Work. The branch carries an ODbL notice
and a metadata file with the attribution and provenance: OSM extract date, Overture release, WorldPop product,
OSRM image. The map shows "© OpenStreetMap contributors" in a corner. The travel-time table itself is not
published, but the ODbL lets anyone the plans reach ask for it, and it is supplied under the ODbL if they do.
Overture buildings (ODbL) are fetched but do not feed demand, so they put no extra terms on the JSON.

## Considered Options

- **A live host running `POST /plan`:** the roadmap's first plan. Free compute is too thin. Hugging Face Docker
  Spaces need a paid plan to create (verified 2026-11-05). Render's free tier has 0.1 CPU. Oracle Always Free
  needs a card and its capacity is unreliable. A paid 8-vCPU host was declined for a demo. On fewer cores the 8 s
  budget still holds, but plan quality drops: at 1-4 workers the default scenario stopped at the time limit with a
  48% stated gap, against optimal in 0.26 s at 8 workers (one run each, load about 5-6).
- **Static site on Hugging Face (static Space) or Cloudflare Pages upload:** keeps the data out of the GitHub
  repo, but adds a second account and a second place to deploy from.
- **Credits only, no ODbL notice on the JSON:** reads the JSON as a Produced Work. Rejected: the JSON can be
  read back as data, which the OSMF guideline treats as a database.

## Consequences

The public site answers only scenarios with one lever off its default; the page says so, and pairs of levers are
Later. Once pushed, the JSON stays in public git history even if the branch is rewritten. Re-publishing means
re-solving the sweep on the dev machine and force-pushing the branch. A live public host comes back only with paid
compute (cuts.md).
