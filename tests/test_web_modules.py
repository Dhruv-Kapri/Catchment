import re
from pathlib import Path

from catchment.service import WEB

URL: re.Pattern[str] = re.compile(r"""["'`]((?:https?:)?//[^"'`]*|/[^"'`/][^"'`]*)["'`]""")   # a string literal holding a URL or an absolute path


def test_only_the_data_source_module_knows_urls() -> None:
    """Wave 2 tickets edit the map, levers and metrics modules in parallel; where data and services live stays in api.js."""
    modules: list[Path] = sorted((WEB / "js").glob("*.js"))
    assert "api.js" in {m.name for m in modules} and URL.search((WEB / "js" / "api.js").read_text())
    assert {m.name: URL.findall(m.read_text()) for m in modules if m.name != "api.js" and URL.search(m.read_text())} == {}
