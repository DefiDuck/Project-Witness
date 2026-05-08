"""Smoke tests for the trace-lineage SVG renderer."""
from __future__ import annotations

from witness.core.schema import DecisionType, Trace
from witness.perturbations import Truncate
import witness
from witness.ui.lineage import render_lineage_svg


def _baseline(name: str = "baseline", n: int = 4) -> Trace:
    t = Trace(agent_name=name, model="m", final_output="ok", wall_time_ms=42)
    for i in range(n):
        t.add_decision(
            type=DecisionType.MODEL_CALL if i == 0 else DecisionType.TOOL_CALL,
            input={"name": f"step_{i}"},
            output={},
        )
    return t


def test_render_empty_returns_empty() -> None:
    assert render_lineage_svg({}) == ""


def test_render_single_trace_shape() -> None:
    t = _baseline()
    svg = render_lineage_svg({"baseline": t})
    assert svg.startswith("<svg")
    assert "</svg>" in svg
    assert "baseline" in svg
    # 4 decisions => 4 circles
    assert svg.count("<circle") >= 4


def test_render_includes_legend() -> None:
    svg = render_lineage_svg({"baseline": _baseline()})
    assert "model_call" in svg
    assert "tool_call" in svg
    assert "final_output" in svg


def test_render_baseline_plus_perturbed_has_branch_curve() -> None:
    """A baseline + a perturbed child should produce at least one branch
    curve (cubic-bezier <path d="M ... C ..."/>) connecting their lanes."""
    from witness.ui.onboarding import generate_sample_traces

    baseline, perturbed = generate_sample_traces()
    svg = render_lineage_svg(
        {"baseline": baseline, "perturbed": perturbed},
        active_label="baseline",
    )
    # Bezier path emitted for the branch
    assert " C " in svg
    # Active-lane background highlight
    assert 'opacity="0.04"' in svg


def test_render_truncates_long_label() -> None:
    long_name = "x" * 60
    svg = render_lineage_svg({long_name: _baseline()})
    # Output should not contain the full untruncated name
    assert long_name not in svg
    # Some truncation marker
    assert "…" in svg or "..." in svg
