"""Rich-powered formatter tests. Skipped if rich isn't installed."""
from __future__ import annotations

import pytest

pytest.importorskip("rich")

from witness.core.schema import DecisionType, Trace
from witness.diff.behavioral import diff
from witness.diff.fingerprint import fingerprint
from witness.diff.format_rich import (
    make_console,
    render_diff,
    render_fingerprint,
    render_trace_summary,
)


def _make_trace(name: str = "x", final: str = "ok") -> Trace:
    t = Trace(agent_name=name, model="m", final_output=final, wall_time_ms=42)
    t.add_decision(type=DecisionType.MODEL_CALL, input={"model": "m"}, output={"text": final})
    t.add_decision(type=DecisionType.TOOL_CALL, input={"name": "search"}, output={})
    t.add_decision(type=DecisionType.FINAL_OUTPUT, input={}, output={"text": final})
    return t


def _capture(renderable) -> str:
    """Render to a string with no color so assertions are stable."""
    console = make_console(no_color=True, force_terminal=False)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def test_render_diff_basic_shape() -> None:
    a = _make_trace(final="alpha")
    b = _make_trace(final="beta")
    output = _capture(render_diff(diff(a, b)))
    assert "witness diff" in output
    assert "final output" in output
    assert "CHANGED" in output


def test_render_diff_unchanged_shows_unchanged_label() -> None:
    a = _make_trace(final="same")
    b = _make_trace(final="same")
    output = _capture(render_diff(diff(a, b)))
    assert "unchanged" in output


def test_render_diff_tool_count_table_shows_delta() -> None:
    a = _make_trace()
    a.add_decision(type=DecisionType.TOOL_CALL, input={"name": "search"}, output={})
    b = _make_trace()  # one less search
    output = _capture(render_diff(diff(a, b)))
    assert "search" in output
    # Delta column for search should show -1
    assert "-1" in output


def test_render_fingerprint_shape() -> None:
    base = _make_trace()
    fp = fingerprint(base, [base, base])
    output = _capture(render_fingerprint(fp))
    assert "witness fingerprint" in output
    assert "stability by decision type" in output
    assert "overall stability" in output


def test_render_trace_summary_includes_basics() -> None:
    t = _make_trace(name="zelda")
    output = _capture(render_trace_summary(t))
    assert "zelda" in output
    assert "agent_name" in output


def test_render_diff_verbose_shows_unchanged_decisions() -> None:
    a = _make_trace()
    b = _make_trace()
    # Identical: no changed decisions, but verbose should still list them.
    out_terse = _capture(render_diff(diff(a, b), verbose=False))
    out_verbose = _capture(render_diff(diff(a, b), verbose=True))
    # Verbose output should be longer (lists every decision as 'unchanged').
    assert len(out_verbose) > len(out_terse)
