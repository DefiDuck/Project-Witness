"""Tests for the inline expansion card on the diff page.

The expansion is driven by the ``?expand=<i>`` URL contract emitted by
the ribbon nodes (``inline_click=True`` mode). We verify the URL contract
itself by inspecting the rendered ribbon, and the card renderer by
calling its private helpers directly with synthetic ``DecisionChange``
fixtures.
"""
from __future__ import annotations

from witness.core.schema import Decision, DecisionType
from witness.diff.behavioral import DecisionChange
from witness.ui.components.flow import render_diff_ribbons, render_flow_ribbon
from witness.ui.views.diff import (
    _changed_fields,
    _diff_chars,
    _diff_lines,
    _diff_text,
    _render_expansion_side,
)


def _decision(
    type_: DecisionType = DecisionType.MODEL_CALL,
    *,
    duration_ms: int | None = None,
    input_: dict[str, object] | None = None,
    output: dict[str, object] | None = None,
) -> Decision:
    return Decision(
        type=type_,
        input=input_ or {},
        output=output or {},
        duration_ms=duration_ms,
    )


def _pair(kind: str, a: Decision | None, b: Decision | None) -> DecisionChange:
    return DecisionChange(kind=kind, baseline=a, perturbed=b)


# ---------------------------------------------------------------------------
# URL contract — inline_click switches the href format
# ---------------------------------------------------------------------------


def test_diff_ribbon_emits_expand_href_not_trace_navigation() -> None:
    """Diff page node clicks must stay on the diff page. The brief is
    explicit: do not reintroduce ``?trace=...&sel=...`` for diff clicks."""
    a = _decision(DecisionType.MODEL_CALL, duration_ms=100)
    b = _decision(DecisionType.MODEL_CALL, duration_ms=140)
    pairs = [_pair("input_changed", a, b)]
    svg = render_diff_ribbons("base", "pert", pairs)
    # Each node anchor uses ?expand=<slot>
    assert 'href="?expand=0"' in svg
    # And the trace-navigation form is conspicuously absent.
    assert "tab=sequence" not in svg
    assert "tab=diffs" not in svg


def test_trace_detail_ribbon_keeps_trace_navigation() -> None:
    """Trace detail (default ``inline_click=False``) keeps the original
    URL contract — clicks navigate within the trace."""
    decisions = [_decision(DecisionType.MODEL_CALL, duration_ms=50)]
    svg = render_flow_ribbon("baseline.json", decisions, inline_click=False)
    assert "?trace=baseline.json&tab=sequence&sel=0" in svg


def test_diff_ribbon_expanded_slot_marks_both_sides_active() -> None:
    """When ?expand points at slot 1, both the baseline and perturbed
    nodes at slot 1 should carry the active ring so the user sees the
    pair the expansion card is showing."""
    a1 = _decision(DecisionType.MODEL_CALL, duration_ms=50)
    a2 = _decision(DecisionType.TOOL_CALL, duration_ms=80)
    b1 = _decision(DecisionType.MODEL_CALL, duration_ms=50)
    b2 = _decision(DecisionType.TOOL_CALL, duration_ms=80)
    pairs = [_pair("same", a1, b1), _pair("input_changed", a2, b2)]
    svg = render_diff_ribbons("base", "pert", pairs, expanded_slot=1)
    # Two active nodes (both ribbons, slot 1)
    assert svg.count("flow-node-active") == 2


# ---------------------------------------------------------------------------
# _changed_fields — what shows up in the metadata strip
# ---------------------------------------------------------------------------


def test_changed_fields_input_only() -> None:
    a = _decision(input_={"prompt": "hello"})
    b = _decision(input_={"prompt": "world"})
    assert _changed_fields(a, b) == ["input"]


def test_changed_fields_input_and_output() -> None:
    a = _decision(input_={"x": 1}, output={"y": 2})
    b = _decision(input_={"x": 99}, output={"y": 100})
    assert _changed_fields(a, b) == ["input", "output"]


def test_changed_fields_type_changed() -> None:
    a = _decision(DecisionType.MODEL_CALL, input_={"x": 1})
    b = _decision(DecisionType.TOOL_CALL, input_={"x": 1})
    assert "type" in _changed_fields(a, b)


def test_changed_fields_returns_empty_for_unchanged() -> None:
    a = _decision(input_={"x": 1}, output={"y": 2})
    b = _decision(input_={"x": 1}, output={"y": 2})
    assert _changed_fields(a, b) == []


def test_changed_fields_handles_none_sides() -> None:
    """Added or removed → no field-level diff to surface."""
    a = _decision()
    assert _changed_fields(None, a) == []
    assert _changed_fields(a, None) == []
    assert _changed_fields(None, None) == []


# ---------------------------------------------------------------------------
# _diff_text / _diff_chars / _diff_lines — span fragments
# ---------------------------------------------------------------------------


def test_diff_text_identical_returns_plain_escaped() -> None:
    out = _diff_text("hello", "hello")
    assert out == "hello"
    # No diff spans emitted for unchanged text.
    assert "dv-frag-add" not in out


def test_diff_text_other_missing_marks_whole_self_as_addition() -> None:
    """When the other side is None, the whole text on this side is
    treated as new."""
    out = _diff_text("foo", None)
    assert 'class="dv-frag-add"' in out
    assert "foo" in out


def test_diff_chars_highlights_changed_substring() -> None:
    """Tools args ``{"q": "cat"}`` → ``{"q": "dog"}`` should show 'dog'
    (or its characters) wrapped in dv-frag-add spans."""
    out = _diff_chars(self_text='dog', other_text='cat')
    assert 'class="dv-frag-add"' in out
    # The chars unique to self_text appear inside a span; the chars
    # unique to other_text don't appear at all (they're the OTHER side).
    assert "cat" not in out


def test_diff_lines_handles_multiline_input() -> None:
    self_text = "alpha\nbeta\ngamma"
    other_text = "alpha\nBETA\ngamma"
    out = _diff_lines(self_text, other_text)
    # 'alpha' and 'gamma' unchanged, escaped plain text
    assert "alpha" in out
    assert "gamma" in out
    # 'beta' (this side, lower-case) is the addition
    assert 'class="dv-frag-add">beta' in out


def test_diff_text_short_uses_char_diff_long_uses_line_diff() -> None:
    """The branching threshold is 128 chars / no newline; below that we
    use char-level for crisp single-token swaps."""
    short_self, short_other = "abc", "abd"
    short_out = _diff_text(short_self, short_other)
    # Char-level: each diff char gets its own span
    assert short_out.count('class="dv-frag-add"') == 1

    long_self = "x\n" * 200
    long_other = "y\n" * 200
    long_out = _diff_text(long_self, long_other)
    assert "dv-frag-add" in long_out


# ---------------------------------------------------------------------------
# _render_expansion_side — the column body
# ---------------------------------------------------------------------------


def test_render_expansion_side_baseline_missing_emits_empty_state() -> None:
    """An ``added`` slot has no baseline; the baseline column shows
    'not in baseline' italic per the brief."""
    perturbed = _decision(DecisionType.TOOL_CALL, input_={"name": "new"})
    out = _render_expansion_side(None, perturbed, side="baseline")
    assert "dv-expand-col-empty" in out
    assert "not in baseline" in out


def test_render_expansion_side_perturbed_missing_emits_empty_state() -> None:
    baseline = _decision(DecisionType.TOOL_CALL, input_={"name": "old"})
    out = _render_expansion_side(None, baseline, side="perturbed")
    assert "not in perturbed" in out


def test_render_expansion_side_renders_typed_blocks() -> None:
    """When both sides exist, render the standard caps-label blocks
    (TYPE / INPUT / OUTPUT) so the expansion echoes the trace detail
    typography."""
    a = _decision(DecisionType.MODEL_CALL, input_={"prompt": "hello"})
    b = _decision(DecisionType.MODEL_CALL, input_={"prompt": "world"})
    out = _render_expansion_side(a, b, side="baseline")
    assert ">TYPE<" in out
    assert ">INPUT<" in out
    assert ">OUTPUT<" in out
    # And the diff highlight is present on the changed input.
    assert "dv-frag-add" in out
