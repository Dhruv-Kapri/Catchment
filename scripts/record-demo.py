"""Record the main flow of the live web map as a ~90 s video, plus a screenshot (ticket #51).

Start the service first (`uv run catchment-serve --port 8000`), then:

    uv run python scripts/record-demo.py [--url http://127.0.0.1:8000] [--out outputs/demo]

Writes demo.mp4 (H.264, 1280 wide, faststart) and screenshot.png into --out.
Needs ffmpeg on the PATH (or at /opt/homebrew/bin/ffmpeg) and Chromium (`uv run playwright install chromium`).
"""
import argparse
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import Locator, Page, expect, sync_playwright

PLAN_TIMEOUT_MS: int = 30_000


def pause(page: Page, seconds: float) -> None:
    """A deliberate beat for the viewer."""
    page.wait_for_timeout(int(seconds * 1000))


def clamp(value: float, spec: dict[str, float]) -> float:
    """The value held to the lever's range and rounded to its step (the service rejects off-step values)."""
    stepped: float = spec["min"] + round((value - spec["min"]) / spec["step"]) * spec["step"]
    return round(min(max(stepped, spec["min"]), spec["max"]), 6)


def plan(page: Page, scenario: Locator) -> None:
    """Press Plan and wait until this scenario's /plan answered and its stores are drawn."""
    with page.expect_response("**/plan", timeout=PLAN_TIMEOUT_MS):
        scenario.get_by_test_id("plan-button").click()
    expect(scenario.get_by_test_id("plan-button")).to_be_enabled(timeout=PLAN_TIMEOUT_MS)
    expect(scenario.get_by_test_id("elapsed")).to_contain_text("Planned in")
    expect(scenario.locator(".store-new").first).to_be_visible()


def set_lever(page: Page, scenario: Locator, lever: str, value: float) -> None:
    field: Locator = scenario.get_by_test_id(f"lever-{lever}")
    field.scroll_into_view_if_needed()
    field.click(click_count=3)   # select the old value, as a person would
    page.keyboard.type(f"{value:g}", delay=150)
    field.dispatch_event("input")
    pause(page, 1)


def drive(page: Page, url: str, levers: dict[str, dict[str, float]], out: Path) -> float:
    """Run the flow; returns the seconds the page took to load, which the video drops from its start."""
    started: float = time.monotonic()
    page.goto(url)
    a, b = page.get_by_test_id("scenario-a"), page.get_by_test_id("scenario-b")
    page.wait_for_function("window.catchment && window.catchment.a.map.loaded() && window.catchment.b.map.loaded()", timeout=60_000)
    expect(a.locator(".store-operator").first).to_be_visible(timeout=20_000)
    expect(a.get_by_test_id("market-demand-total")).not_to_have_text("-")
    expect(b.get_by_test_id("spot-check-note")).to_be_visible(timeout=20_000)
    loaded: float = time.monotonic() - started
    pause(page, 9)   # the demand layer, the existing stores, the levers and the spot-check note

    plan(page, a)   # scenario A at the defaults
    pause(page, 8)   # the new stores and the metrics

    a.locator(".store-new").first.click()   # a new store: its catchment outline
    page.wait_for_function(
        "async () => (await window.catchment.a.map.getSource('catchment-outline').getData()).features.length > 0", timeout=10_000)
    pause(page, 10)

    page.get_by_test_id("copy-a-to-b").click()   # B starts from A's levers
    pause(page, 3)
    n_new, promise = levers["n_new"], levers["promise"]
    set_lever(page, b, "n_new", clamp(n_new["default"] + 5, n_new))
    set_lever(page, b, "promise", clamp(promise["default"] + 2, promise))
    pause(page, 2)
    plan(page, b)
    expect(page.get_by_test_id("diff-row-new_stores")).to_be_visible()
    page.get_by_test_id("diff").scroll_into_view_if_needed()
    pause(page, 4)
    page.screenshot(path=out / "screenshot.png")   # both plans drawn, the B - A table filled
    pause(page, 12)   # the B - A table

    page.get_by_test_id("assumptions-button").click()
    drawer: Locator = page.get_by_test_id("assumptions-drawer")
    expect(drawer).to_be_visible()
    expect(drawer.get_by_role("row").filter(has_text="Household size")).to_be_visible()
    pause(page, 9)
    drawer.evaluate("(el) => el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })")   # down to the synthetic network's note
    pause(page, 9)
    page.keyboard.press("Escape")   # closes it (the drawer covers the header button)
    expect(drawer).to_be_hidden()
    pause(page, 8)   # both scenarios, side by side, once more
    return loaded


def convert(webm: Path, mp4: Path, skip: float) -> None:
    ffmpeg: str = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{skip:.2f}", "-i", str(webm), "-c:v", "libx264", "-preset", "slow", "-crf", "30",
                    "-pix_fmt", "yuv420p", "-vf", "scale=1280:-2", "-movflags", "+faststart", "-an", str(mp4)], check=True)


def duration(mp4: Path) -> float:
    ffprobe: str = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                            check=True, capture_output=True, text=True)
    return float(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=Path("outputs/demo"))
    args = parser.parse_args()
    out: Path = args.out
    raw: Path = out / "raw"
    shutil.rmtree(raw, ignore_errors=True)
    raw.mkdir(parents=True)
    levers: dict[str, dict[str, float]] = httpx.get(f"{args.url}/levers").json()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context: Any = browser.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(raw),
                                           record_video_size={"width": 1440, "height": 900})
        page: Page = context.new_page()
        loaded: float = 0.0
        try:
            loaded = drive(page, args.url, levers, out)
        finally:
            context.close()   # saves the video
            browser.close()

    webm: Path = next(raw.glob("*.webm"))
    mp4: Path = out / "demo.mp4"
    convert(webm, mp4, max(loaded - 1.0, 0.0))   # keep a second of the load
    print(f"video:      {mp4}  ({duration(mp4):.1f} s, {mp4.stat().st_size / 1e6:.1f} MB)")
    print(f"raw webm:   {webm}  ({webm.stat().st_size / 1e6:.1f} MB)")
    print(f"screenshot: {out / 'screenshot.png'}  ({(out / 'screenshot.png').stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
