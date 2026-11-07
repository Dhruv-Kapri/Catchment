#!/usr/bin/env bash
# Build the static demo site and force-push it as an orphan gh-pages branch (ADR 0003).
# Local branches are untouched: the push happens from a fresh repo in a temp dir.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
ORIGIN="$(git remote get-url origin)"

uv run catchment-bundle --out outputs/site

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -R outputs/site/. "$TMP/"
touch "$TMP/.nojekyll"
cd "$TMP"
git init -q -b gh-pages
git add -A
git commit -q -m "Static demo $(date +%Y-%m-%d)"
git push --force "$ORIGIN" HEAD:gh-pages
