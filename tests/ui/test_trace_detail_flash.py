"""Tests for the click-celebration wrapper on the Sequence tab.

The visible signal that "yes, something happened" when the user clicks
a ribbon node is the content pane fading in fresh content. Implementation:

- Wrap the content pane in ``<div id="td-content-anchor"
  class="td-content-pane td-content-flash-<sel>">``
- The unique ``td-content-flash-<sel>`` class is what makes the browser
  re-run the keyframe — same name across renders would be a no-op.

These tests use Streamlit's ``AppTest`` framework to render the app and
inspect the resulting markdown output for the wrapper attributes.
"""
from __future__ import annotations

import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from witness.core.schema import Decision, DecisionType, Trace  # noqa: E402


@pytest.fixture
def tiny_trace() -> Trace:
    return Trace(
        agent_name="t",
        decisions=[
            Decision(type=DecisionType.MODEL_CALL, duration_ms=50, input={"prompt": "a"}),
            Decision(type=DecisionType.TOOL_CALL, duration_ms=10, input={"name": "x"}),
            Decision(type=DecisionType.FINAL_OUTPUT, duration_ms=5, output={"text": "z"}),
        ],
    )


def _run_with_trace(trace: Trace, label: str = "fixture.json") -> AppTest:
    """Spin up an AppTest with one preloaded trace under ``label``."""
    at = AppTest.from_file(
        "witness/ui/app.py", default_timeout=30
    )
    at.session_state["loaded_traces"] = {label: trace}
    at.session_state["active_label"] = label
    return at


def _all_markdown(at: AppTest) -> str:
    """Concatenate every markdown body the app emitted, for substring
    asserts. Covers both ``st.markdown(unsafe_allow_html=True)`` strings
    and any HTML rendered through components.html."""
    chunks: list[str] = []
    for el in at.markdown:
        chunks.append(el.value or "")
    return "\n".join(chunks)


def test_content_pane_carries_dynamic_flash_class(tiny_trace: Trace) -> None:
    """The flash class must encode the current ``sel`` so each click
    triggers a fresh keyframe run."""
    at = _run_with_trace(tiny_trace)
    at.query_params["trace"] = "fixture.json"
    at.query_params["tab"] = "sequence"
    at.query_params["sel"] = "1"
    at.run()
    md = _all_markdown(at)
    assert 'id="td-content-anchor"' in md
    assert "td-content-pane" in md
    assert "td-content-flash-1" in md


def test_content_flash_class_changes_with_selection(tiny_trace: Trace) -> None:
    """Two different ``sel`` values must produce two distinct flash
    class names — same name across renders would no-op the keyframe."""
    at = _run_with_trace(tiny_trace)
    at.query_params["trace"] = "fixture.json"
    at.query_params["tab"] = "sequence"
    at.query_params["sel"] = "0"
    at.run()
    md0 = _all_markdown(at)
    assert "td-content-flash-0" in md0
    assert "td-content-flash-1" not in md0

    at.query_params["sel"] = "2"
    at.run()
    md2 = _all_markdown(at)
    assert "td-content-flash-2" in md2


def test_play_strip_renders_when_trace_has_decisions(tiny_trace: Trace) -> None:
    """Smoke: the play controls strip is present on the Sequence tab."""
    at = _run_with_trace(tiny_trace)
    at.query_params["trace"] = "fixture.json"
    at.query_params["tab"] = "sequence"
    at.run()
    md = _all_markdown(at)
    assert "pc-strip" in md
    assert "pc-scrubber" in md
    assert "1 / 3" in md  # 3 decisions, starting at index 0
