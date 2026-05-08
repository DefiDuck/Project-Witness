"""Integration-ish tests using Streamlit's AppTest to render each page.

AppTest spins up the script in-process and lets us inspect what was rendered
without launching a real server. Catches AttributeError / TypeError that show
up only when a page actually renders.

If streamlit isn't installed (or AppTest isn't available), the whole module
is skipped.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    pytest.skip("AppTest not available", allow_module_level=True)

from witness.ui import APP_PATH


def _new_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=10)


def _page_nav(at: AppTest):
    """Locate the page-nav radio (3 sections: Traces / Diffs / Settings),
    tolerant of any number of other radios in the sidebar (mode toggle, etc.)."""
    for r in at.sidebar.radio:
        opts = list(getattr(r, "options", []) or [])
        if "Traces" in opts:
            return r
    raise AssertionError(
        "page-nav radio not found — options seen: "
        + ", ".join(repr(list(getattr(r, "options", []))) for r in at.sidebar.radio)
    )


def _page_text(at: AppTest) -> str:
    """Concatenated text content emitted by the running page (markdown,
    captions, info, error, warning). Used so we can assert on page titles
    that are rendered via raw HTML topbars, not st.header()."""
    parts: list[str] = []
    for collection in (at.markdown, at.caption, at.info, at.warning, at.error):
        for el in collection:
            v = getattr(el, "value", None)
            if v:
                parts.append(str(v))
    for h in at.header:
        if h.value:
            parts.append(str(h.value))
    return "\n".join(parts)


def test_app_renders_traces_section_without_errors() -> None:
    """Default landing section is Traces."""
    at = _new_app()
    at.run()
    assert not at.exception, f"unexpected exception: {at.exception}"
    # Topbar shows "Traces" after the commit-2 dense list view replaced the
    # legacy "Load traces" topbar.
    assert "Traces" in _page_text(at)


def test_app_switches_to_diffs_section() -> None:
    at = _new_app()
    at.run()
    radio = _page_nav(at)
    radio.set_value("Diffs").run()
    assert not at.exception


def test_app_switches_to_settings_section() -> None:
    at = _new_app()
    at.run()
    radio = _page_nav(at)
    radio.set_value("Settings").run()
    assert not at.exception
    assert "Settings" in _page_text(at)


def test_settings_path_loader_loads_a_trace(tmp_path: Path) -> None:
    """The path-based trace loader lives on the Settings section after the
    nav collapse. Loading via that loader should populate session state."""
    from witness.core.schema import DecisionType, Trace
    from witness.core.store import save_trace

    t = Trace(agent_name="ax", final_output="ok", model="m")
    t.add_decision(type=DecisionType.MODEL_CALL, input={}, output={"text": "ok"})
    p = tmp_path / "fixture.json"
    save_trace(t, p)

    at = _new_app()
    at.run()
    radio = _page_nav(at)
    radio.set_value("Settings").run()

    path_input = next(
        ti for ti in at.text_input if getattr(ti, "key", None) == "path_input"
    )
    path_input.set_value(str(p)).run()
    button = next(b for b in at.button if getattr(b, "key", None) == "load_by_path")
    button.click().run()
    assert not at.exception
    # 1 trace should now be loaded — sidebar reports it.
    sidebar_text = " ".join(md.value for md in at.sidebar.markdown)
    assert "1 trace(s) loaded" in sidebar_text or "1 trace" in sidebar_text
