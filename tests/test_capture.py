"""@observe decorator behavior."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import witness
from witness.core.schema import DecisionType


def test_observe_captures_inputs_and_output(tmp_traces: Path) -> None:
    @witness.observe(name="echo", output_dir=str(tmp_traces))
    def echo(text: str, n: int = 1) -> str:
        return text * n

    result = echo("hi", n=3)
    assert result == "hihihi"

    trace = echo.__witness_last_trace__
    assert trace is not None
    assert trace.agent_name == "echo"
    assert trace.inputs == {"text": "hi", "n": 3}
    assert trace.final_output == "hihihi"
    assert trace.wall_time_ms is not None


def test_observe_writes_trace_to_disk(tmp_traces: Path) -> None:
    @witness.observe(name="t", output_dir=str(tmp_traces))
    def f() -> int:
        return 42

    f()
    files = list(tmp_traces.glob("*.trace.json"))
    assert len(files) == 1
    loaded = witness.load_trace(files[0])
    assert loaded.final_output == 42


def test_observe_with_explicit_output_path(tmp_path: Path) -> None:
    out = tmp_path / "my.trace.json"

    @witness.observe(output_path=str(out))
    def f() -> str:
        return "ok"

    f()
    assert out.exists()
    loaded = witness.load_trace(out)
    assert loaded.agent_name == "f"


def test_observe_save_false_does_not_write(tmp_traces: Path) -> None:
    @witness.observe(name="x", output_dir=str(tmp_traces), save=False)
    def f() -> int:
        return 1

    f()
    assert list(tmp_traces.glob("*.trace.json")) == []
    # but the trace IS still attached to the function
    assert f.__witness_last_trace__ is not None


def test_record_decision_inside_observe(tmp_traces: Path) -> None:
    @witness.observe(name="agent", output_dir=str(tmp_traces))
    def agent() -> str:
        witness.record_decision(
            DecisionType.TOOL_CALL,
            input={"name": "search", "args": {"q": "foo"}},
            output={},
        )
        witness.record_decision(
            DecisionType.TOOL_RESULT,
            input={"name": "search"},
            output={"hits": ["a", "b"]},
        )
        return "done"

    agent()
    trace = agent.__witness_last_trace__
    assert trace is not None
    assert len(trace.decisions) == 2
    assert trace.decisions[0].type == DecisionType.TOOL_CALL
    assert trace.decisions[1].output == {"hits": ["a", "b"]}


def test_record_decision_outside_observe_is_noop() -> None:
    # No active trace -> no error, returns None.
    result = witness.record_decision(DecisionType.TOOL_CALL, input={"name": "foo"})
    assert result is None


def test_observe_captures_exception_into_trace(tmp_traces: Path) -> None:
    @witness.observe(name="boom", output_dir=str(tmp_traces))
    def boom() -> None:
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        boom()

    trace = boom.__witness_last_trace__
    assert trace is not None
    assert trace.metadata["exception"]["type"] == "RuntimeError"
    assert "kaboom" in trace.metadata["exception"]["message"]


def test_observe_supports_async(tmp_traces: Path) -> None:
    @witness.observe(name="async_agent", output_dir=str(tmp_traces))
    async def agent(n: int) -> int:
        await asyncio.sleep(0)
        witness.record_decision(DecisionType.MODEL_CALL, input={"n": n}, output={"r": n * 2})
        return n * 2

    result = asyncio.run(agent(7))
    assert result == 14
    trace = agent.__witness_last_trace__
    assert trace is not None
    assert trace.decisions[0].input == {"n": 7}


def test_observe_bare_decorator_form(tmp_traces: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_traces.parent)

    @witness.observe
    def f() -> str:
        return "ok"

    assert f() == "ok"
    assert f.__witness_last_trace__ is not None


def test_observe_with_metadata(tmp_traces: Path) -> None:
    @witness.observe(
        name="x",
        output_dir=str(tmp_traces),
        metadata={"experiment": "alpha", "version": 3},
    )
    def f() -> str:
        return "ok"

    f()
    trace = f.__witness_last_trace__
    assert trace.metadata["experiment"] == "alpha"
    assert trace.metadata["version"] == 3


def test_current_trace_returns_none_outside_observe() -> None:
    assert witness.current_trace() is None


def test_current_trace_returns_trace_inside(tmp_traces: Path) -> None:
    captured: dict[str, object] = {}

    @witness.observe(name="x", output_dir=str(tmp_traces))
    def f() -> None:
        captured["t"] = witness.current_trace()

    f()
    assert captured["t"] is not None
    # should be the same object as the one attached to the wrapper
    assert captured["t"] is f.__witness_last_trace__


def test_observe_captures_unjsonable_input_as_repr(tmp_traces: Path) -> None:
    class Weird:
        def __repr__(self) -> str:
            return "<Weird thing>"

    @witness.observe(name="x", output_dir=str(tmp_traces))
    def f(x: object) -> str:
        return "done"

    f(Weird())
    trace = f.__witness_last_trace__
    # we should have captured repr() rather than crashed
    assert "Weird thing" in str(trace.inputs["x"])


def test_observe_entrypoint_is_resolvable(tmp_traces: Path) -> None:
    @witness.observe(name="x", output_dir=str(tmp_traces))
    def f() -> int:
        return 1

    f()
    trace = f.__witness_last_trace__
    assert trace.entrypoint is not None
    assert ":" in trace.entrypoint
