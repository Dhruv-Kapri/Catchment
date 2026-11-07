"""Check the public static demo end to end in a fresh browser (ticket #51).

    uv run python scripts/check-public.py [--url https://dhruv-kapri.github.io/Catchment/] [--log outputs/check-public.log]

Each run launches Chromium with a new context (no stored state), drives the page as a user would, prints a PASS/FAIL
line per step and writes the same lines, under a header (UTC time, URL, Chromium version), to --log. Exit 0 only if every step passed.
Needs Chromium (`uv run playwright install chromium`).
"""
import argparse
import re
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Locator, Page, expect, sync_playwright

TIMEOUT_MS: int = 30_000
NUMBER: re.Pattern[str] = re.compile(r"^[\d,]+$")


def run_steps(page: Page, url: str, errors: list[str], failed: list[str]) -> list[tuple[str, Callable[[], None]]]:
    """The steps in order; each raises AssertionError (or a Playwright timeout) with its failure message."""
    a: Locator = page.get_by_test_id("scenario-a")
    b: Locator = page.get_by_test_id("scenario-b")
    state: dict[str, str | int] = {}

    def notice() -> None:
        response = page.goto(url)
        assert response is not None and response.ok, f"{url} answered {response and response.status}, not 200"
        expect(page.get_by_test_id("static-notice")).to_be_visible(timeout=TIMEOUT_MS)

    def plan_a() -> None:
        expect(a.get_by_test_id("lever-n_new")).to_have_value(re.compile(r"^\d+$"), timeout=TIMEOUT_MS)   # the levers have loaded
        default: int = int(a.get_by_test_id("lever-n_new").input_value())
        state["default"] = default
        a.get_by_test_id("plan-button").click()
        expect(a.get_by_test_id("metric-demand")).to_have_text(NUMBER, timeout=TIMEOUT_MS)
        state["demand_a"] = a.get_by_test_id("metric-demand").inner_text()
        gap: str = a.get_by_test_id("metric-gap").inner_text()
        assert gap not in ("", "-"), f"A's gap is not filled (shows {gap!r})"
        expect(a.get_by_test_id("new-stores").locator("tbody tr")).to_have_count(default, timeout=TIMEOUT_MS)

    def plan_b() -> None:
        n_new: int = int(state["default"]) + 5
        field: Locator = b.get_by_test_id("lever-n_new")
        field.fill(str(n_new))
        field.dispatch_event("input")   # on the static site this resets B's other levers to their defaults
        b.get_by_test_id("plan-button").click()
        expect(b.get_by_test_id("metric-demand")).to_have_text(NUMBER, timeout=TIMEOUT_MS)
        demand_b: str = b.get_by_test_id("metric-demand").inner_text()
        assert demand_b != state["demand_a"], f"B's demand ({demand_b}) equals A's with {n_new} new stores against {state['default']}"
        expect(b.get_by_test_id("new-stores").locator("tbody tr")).to_have_count(n_new, timeout=TIMEOUT_MS)
        rows: int = page.get_by_test_id("diff").locator("tr[data-testid^=diff-row-]").count()
        assert rows > 0, "the B - A table has no rows"

    def drawer() -> None:
        page.get_by_test_id("assumptions-button").click()
        expect(page.get_by_test_id("assumptions-drawer")).to_be_visible(timeout=TIMEOUT_MS)

    def clean() -> None:
        assert not errors and not failed, f"page errors {errors}; failed responses {failed}"

    return [
        ("static notice is visible", notice),
        ("plan in A: demand, gap and the default N new stores", plan_a),
        ("plan in B with N + 5: demand differs, B - A table has rows", plan_b),
        ("assumptions drawer opens", drawer),
        ("no page errors and no failed responses", clean),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="https://dhruv-kapri.github.io/Catchment/")
    parser.add_argument("--log", type=Path, default=Path("outputs/check-public.log"))
    args = parser.parse_args()

    errors: list[str] = []
    failed: list[str] = []
    lines: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()   # fresh: no storage state
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        for name, step in run_steps(page, args.url, errors, failed):
            try:
                step()
                lines.append(f"PASS {name}")
            except Exception as e:   # AssertionError or a Playwright timeout
                lines.append(f"FAIL {name}: {str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__}")
        header: list[str] = [f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {args.url}  Chromium {browser.version}"]
        browser.close()
    if failed or errors:
        lines += [f"  page error: {e}" for e in errors] + [f"  failed response: {f}" for f in failed]
    report: str = "\n".join(header + lines)
    print(report)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(report + "\n")
    return 1 if any(line.startswith("FAIL") for line in lines) else 0


if __name__ == "__main__":
    sys.exit(main())
