"""Anthropic adapter — uses a fake `anthropic` module so no SDK install needed."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

import witness


@pytest.fixture
def fake_anthropic(monkeypatch: pytest.MonkeyPatch):
    """Install a fake `anthropic` package shaped just enough for the adapter's
    `Messages.create` patch to apply.
    """

    pkg = types.ModuleType("anthropic")
    resources = types.ModuleType("anthropic.resources")
    messages_mod = types.ModuleType("anthropic.resources.messages")

    class Messages:
        last_call: dict[str, Any] = {}

        def create(self, **kwargs: Any) -> Any:
            Messages.last_call = kwargs
            # Return a response shape the adapter understands.
            return _FakeResponse(
                content=[
                    _FakeBlock("text", text="hi back"),
                ],
                stop_reason="end_turn",
                model=kwargs.get("model"),
            )

    class AsyncMessages:
        async def create(self, **kwargs: Any) -> Any:
            return _FakeResponse(
                content=[_FakeBlock("text", text="async hi")],
                stop_reason="end_turn",
                model=kwargs.get("model"),
            )

    messages_mod.Messages = Messages  # type: ignore[attr-defined]
    messages_mod.AsyncMessages = AsyncMessages  # type: ignore[attr-defined]
    resources.messages = messages_mod  # type: ignore[attr-defined]
    pkg.resources = resources  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "anthropic", pkg)
    monkeypatch.setitem(sys.modules, "anthropic.resources", resources)
    monkeypatch.setitem(sys.modules, "anthropic.resources.messages", messages_mod)
    yield Messages
    # Reset adapter state in case the previous run patched.
    from witness.adapters import anthropic as ad

    ad._PATCHED = False
    ad._ORIG_SYNC = None
    ad._ORIG_ASYNC = None


class _FakeResponse:
    def __init__(self, *, content: list[Any], stop_reason: str, model: str | None) -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.model = model
        self.id = "msg_fake"
        self.role = "assistant"
        self.usage = _FakeUsage()


class _FakeUsage:
    input_tokens = 1
    output_tokens = 2

    def model_dump(self) -> dict[str, Any]:
        return {"input_tokens": 1, "output_tokens": 2}


class _FakeBlock:
    def __init__(self, type: str, **kwargs: Any) -> None:
        self.type = type
        self._kw = kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self) -> dict[str, Any]:
        return {"type": self.type, **self._kw}


def test_anthropic_adapter_records_model_call(fake_anthropic, tmp_traces: Path) -> None:
    from witness.adapters import anthropic as ad

    ad.install()

    @witness.observe(name="agent", output_dir=str(tmp_traces))
    def agent() -> str:
        import anthropic  # the fake one

        client_messages = anthropic.resources.messages.Messages()
        resp = client_messages.create(
            model="claude-x",
            max_tokens=128,
            messages=[{"role": "user", "content": "hi"}],
        )
        text = resp.content[0].text
        return text

    out = agent()
    assert out == "hi back"
    trace = agent.__witness_last_trace__
    assert trace is not None
    # Model picked up from the SDK call
    assert trace.model == "claude-x"
    # At least one model_call decision recorded
    types_seen = [d.type.value for d in trace.decisions]
    assert "model_call" in types_seen
    # final_output decision recorded because stop_reason was end_turn
    assert "final_output" in types_seen


def test_anthropic_adapter_records_tool_use(fake_anthropic, tmp_traces: Path) -> None:
    """When the response has a tool_use block, the adapter records a tool_call decision."""
    from witness.adapters import anthropic as ad

    Messages = fake_anthropic

    # Override the fake to return a tool_use block.
    def create_with_tool(self, **kwargs: Any) -> Any:
        return _FakeResponse(
            content=[
                _FakeBlock("text", text="thinking..."),
                _FakeBlock(
                    "tool_use",
                    id="tu_1",
                    name="search",
                    input={"q": "anthropic"},
                ),
            ],
            stop_reason="tool_use",
            model=kwargs.get("model"),
        )

    Messages.create = create_with_tool  # type: ignore[method-assign]
    ad.install()

    @witness.observe(name="agent", output_dir=str(tmp_traces))
    def agent() -> str:
        import anthropic

        m = anthropic.resources.messages.Messages()
        m.create(
            model="claude-x",
            max_tokens=128,
            messages=[{"role": "user", "content": "search for stuff"}],
            tools=[{"name": "search", "description": "find things"}],
        )
        return "done"

    agent()
    trace = agent.__witness_last_trace__
    assert trace is not None
    # tool_call decision should have been recorded
    tool_calls = [d for d in trace.decisions if d.type.value == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].input["name"] == "search"
    # tools_available picked up from the request
    assert "search" in trace.tools_available


def test_anthropic_adapter_uninstall_restores(fake_anthropic) -> None:
    from witness.adapters import anthropic as ad

    import anthropic

    pre = anthropic.resources.messages.Messages.create
    ad.install()
    mid = anthropic.resources.messages.Messages.create
    assert mid is not pre  # patched
    ad.uninstall()
    post = anthropic.resources.messages.Messages.create
    assert post is pre  # restored
