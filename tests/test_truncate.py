"""Truncation perturbation."""
from __future__ import annotations

import pytest

from witness.core.schema import Trace
from witness.perturbations.base import ReplayContext
from witness.perturbations.truncate import Truncate


def _ctx(messages: list[dict] | None = None, inputs: dict | None = None) -> ReplayContext:
    return ReplayContext(
        inputs=dict(inputs or {}),
        messages=list(messages or []),
        tools_available=[],
        model="m",
    )


def test_truncate_default_fraction() -> None:
    p = Truncate()
    assert p.fraction == 0.5
    assert p.preserve_system is True


def test_truncate_invalid_fraction_raises() -> None:
    with pytest.raises(ValueError):
        Truncate(fraction=0.0)
    with pytest.raises(ValueError):
        Truncate(fraction=1.0)
    with pytest.raises(ValueError):
        Truncate(fraction=-0.1)


def test_truncate_messages_drops_trailing_half() -> None:
    msgs = [{"role": "user", "content": str(i)} for i in range(10)]
    ctx = _ctx(messages=msgs)
    Truncate(fraction=0.5).apply(ctx)
    # 10 -> keep 5
    assert len(ctx.messages) == 5
    # Should be the FIRST 5
    assert [m["content"] for m in ctx.messages] == ["0", "1", "2", "3", "4"]


def test_truncate_preserves_system_message() -> None:
    msgs = [
        {"role": "system", "content": "you are a helpful assistant"},
        *[{"role": "user", "content": str(i)} for i in range(8)],
    ]
    ctx = _ctx(messages=msgs)
    Truncate(fraction=0.75).apply(ctx)
    # System always stays in
    assert ctx.messages[0]["role"] == "system"


def test_truncate_doc_input_by_name() -> None:
    long = "x" * 1000
    ctx = _ctx(inputs={"doc": long, "n": 5})
    Truncate(fraction=0.5).apply(ctx)
    assert ctx.inputs["doc"] == "x" * 500
    # non-string inputs untouched
    assert ctx.inputs["n"] == 5


def test_truncate_long_string_input() -> None:
    """Strings >200 chars get truncated even if the kwarg name isn't doc-like."""
    long = "y" * 400
    ctx = _ctx(inputs={"prompt": long})
    Truncate(fraction=0.25).apply(ctx)
    assert len(ctx.inputs["prompt"]) == 300


def test_truncate_short_unrecognized_input_unchanged() -> None:
    ctx = _ctx(inputs={"name": "short"})
    Truncate(fraction=0.5).apply(ctx)
    assert ctx.inputs["name"] == "short"


def test_truncate_record_summary() -> None:
    p = Truncate(fraction=0.5)
    rec = p.record()
    assert rec.type == "truncate"
    assert rec.params == {"fraction": 0.5, "preserve_system": True}
    assert "50" in (rec.summary or "")


def test_truncate_metadata_written_into_ctx() -> None:
    ctx = _ctx(inputs={"doc": "x" * 500})
    Truncate(fraction=0.5).apply(ctx)
    assert ctx.metadata["truncate"]["fraction"] == 0.5


def test_replay_context_from_trace() -> None:
    t = Trace(agent_name="r", model="m1", tools_available=["a", "b"], inputs={"doc": "x"})
    t.add_message(role="user", content="hi")
    ctx = ReplayContext.from_trace(t)
    assert ctx.inputs == {"doc": "x"}
    assert ctx.tools_available == ["a", "b"]
    assert ctx.model == "m1"
    assert len(ctx.messages) == 1


def test_truncate_keeps_at_least_one_message() -> None:
    msgs = [{"role": "user", "content": "only"}]
    ctx = _ctx(messages=msgs)
    Truncate(fraction=0.99).apply(ctx)
    assert len(ctx.messages) >= 1


def test_registry_lookup() -> None:
    from witness.perturbations.registry import get_perturbation, list_perturbations

    assert "truncate" in list_perturbations()
    p = get_perturbation("truncate", fraction=0.3)
    assert isinstance(p, Truncate)
    assert p.fraction == 0.3


def test_registry_unknown_perturbation_raises() -> None:
    from witness.perturbations.registry import get_perturbation

    with pytest.raises(KeyError, match="unknown perturbation"):
        get_perturbation("does_not_exist")
