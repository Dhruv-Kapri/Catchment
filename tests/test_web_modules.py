import re
from pathlib import Path

from catchment.service import WEB

URL: re.Pattern[str] = re.compile(r"""["'`]((?:https?:)?//[^"'`]*|/[^"'`/][^"'`]*)["'`]""")   # a string literal holding a URL or an absolute path


def test_only_the_data_source_module_knows_urls() -> None:
    """Wave 2 tickets edit the map, levers and metrics modules in parallel; where data and services live stays in api.js."""
    modules: list[Path] = sorted((WEB / "js").glob("*.js"))
    assert "api.js" in {m.name for m in modules} and URL.search((WEB / "js" / "api.js").read_text())
    assert {m.name: URL.findall(m.read_text()) for m in modules if m.name != "api.js" and URL.search(m.read_text())} == {}


def test_only_the_format_module_formats_numbers() -> None:
    """#54: the panel, the B - A table and the demand legend once each had a copy of the formatter, and only some of them caught "-0"."""
    modules: list[Path] = sorted((WEB / "js").glob("*.js"))
    assert {m.name for m in modules if "toLocaleString" in m.read_text()} == {"format.js"}
