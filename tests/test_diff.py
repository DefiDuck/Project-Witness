"""Behavioral diff: alignment, classification, formatter."""
from __future__ import annotations

from witness.core.schema import DecisionType, Trace
from witness.diff.behavioral import diff
from witness.diff.format import format_text


def _trace_with_decisions(name: str, specs: list[tuple]) -> Trace:
    """Build a trace with decisions described by (type, name, output) tuples."""
    t = Trace(agent_name=name, final_output="default")
    for spec in specs:
        if len(spec) == 2:
            dtype, payload = spec
            t.add_decision(type=dtype, input=payload, output={})
        else:
            dtype, payload, output = spec
            t.add_decision(type=dtype, input=payload, output=output)
    return t


def test_identical_traces_produce_no_changes() -> None:
    a = _trace_with_decisions(
        "a",
        [
            ("model_call", {"model": "m"}, {"text": "ok"}),
            ("tool_call", {"name": "search"}, {}),
            ("final_output", {}, {"text": "done"}),
        ],
    )
    b = _trace_with_decisions(
        "a",
        [
            ("model_call", {"model": "m"}, {"text": "ok"}),
            ("tool_call", {"name": "search"}, {}),
            ("final_output", {}, {"text": "done"}),
        ],
    )
    a.final_output = "x"
    b.final_output = "x"
    d = diff(a, b)
    assert d.alignment.count("same") == 3
    assert d.alignment.count("removed") == 0
    assert d.alignment.count("added") == 0
    assert not d.final_output_changed


def test_removed_decisions_detected() -> None:
    a = _trace_with_decisions(
        "x",
        [
            ("model_call", {}),
            ("tool_call", {"name": "search"}),
            ("tool_call", {"name": "read"}),
            ("final_output", {}),
        ],
    )
    b = _trace_with_decisions(
        "x",
        [
            ("model_call", {}),
            ("final_output", {}),
        ],
    )
    d = diff(a, b)
    assert d.alignment.count("removed") == 2
    removed_types = [
        ch.baseline.type for ch in d.alignment.pairs if ch.kind == "removed" and ch.baseline
    ]
    assert DecisionType.TOOL_CALL in removed_types


def test_added_decisions_detected() -> None:
    a = _trace_with_decisions(
        "x",
        [
            ("model_call", {}),
            ("final_output", {}),
        ],
    )
    b = _trace_with_decisions(
        "x",
        [
            ("model_call", {}),
            ("tool_call", {"name": "extra"}),
            ("final_output", {}),
        ],
    )
    d = diff(a, b)
    assert d.alignment.count("added") == 1
    added = d.decisions_added[0]
    assert added.input.get("name") == "extra"


def test_input_changed_detected() -> None:
    a = _trace_with_decisions("x", [("tool_call", {"name": "search", "args": {"q": "a"}})])
    b = _trace_with_decisions("x", [("tool_call", {"name": "search", "args": {"q": "b"}})])
    d = diff(a, b)
    assert d.alignment.count("input_changed") == 1


def test_output_changed_detected() -> None:
    a = _trace_with_decisions("x", [("model_call", {}, {"text": "alpha"})])
    b = _trace_with_decisions("x", [("model_call", {}, {"text": "beta"})])
    d = diff(a, b)
    assert d.alignment.count("output_changed") == 1


def test_tool_counts_summary() -> None:
    a = _trace_with_decisions(
        "x",
        [
            ("tool_call", {"name": "search"}),
            ("tool_call", {"name": "search"}),
            ("tool_call", {"name": "read"}),
        ],
    )
    b = _trace_with_decisions("x", [("tool_call", {"name": "search"})])
    d = diff(a, b)
    assert d.tool_counts_baseline == {"search": 2, "read": 1}
    assert d.tool_counts_perturbed == {"search": 1}


def test_final_output_change_flag() -> None:
    a = Trace(agent_name="x", final_output="hello world")
    b = Trace(agent_name="x", final_output="hello there")
    d = diff(a, b)
    assert d.final_output_changed is True


def test_final_output_unchanged_flag() -> None:
    a = Trace(agent_name="x", final_output={"text": "hi"})
    b = Trace(agent_name="x", final_output={"text": "hi"})
    d = diff(a, b)
    assert d.final_output_changed is False


def test_summary_dict_serializable() -> None:
    import json

    a = _trace_with_decisions("x", [("model_call", {})])
    b = _trace_with_decisions("x", [("model_call", {})])
    d = diff(a, b)
    summary = d.summary()
    # round-trips through json
    json.dumps(summary, default=str)
    assert summary["decisions_delta"] == 0


def test_format_text_includes_key_phrases() -> None:
    a = _trace_with_decisions(
        "research_agent",
        [
            ("model_call", {"model": "m"}),
            ("tool_call", {"name": "search"}),
            ("tool_call", {"name": "read_file"}),
            ("final_output", {}),
        ],
    )
    a.final_output = "first"
    b = _trace_with_decisions(
        "research_agent",
        [
            ("model_call", {"model": "m"}),
            ("final_output", {}),
        ],
    )
    b.final_output = "second"
    d = diff(a, b)
    text = format_text(d, color=False)
    assert "decisions:" in text
    assert "REMOVED" in text
    assert "tool calls:" in text
    assert "final output: CHANGED" in text


def test_format_text_no_color_has_no_ansi() -> None:
    a = _trace_with_decisions("x", [("model_call", {})])
    b = _trace_with_decisions("x", [("model_call", {})])
    d = diff(a, b)
    text = format_text(d, color=False)
    assert "\033[" not in text


def test_format_text_color_has_ansi() -> None:
    a = _trace_with_decisions("x", [("model_call", {})])
    b = _trace_with_decisions("x", [("tool_call", {"name": "x"})])
    d = diff(a, b)
    text = format_text(d, color=True)
    assert "\033[" in text


def test_str_of_tracediff_is_text_render() -> None:
    a = _trace_with_decisions("x", [("model_call", {})])
    b = _trace_with_decisions("x", [("model_call", {})])
    d = diff(a, b)
    s = str(d)
    assert "witness diff" in s
