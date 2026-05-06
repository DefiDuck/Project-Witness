"""OpenAI adapter — fake `openai` module."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

import witness


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch):
    pkg = types.ModuleType("openai")
    resources = types.ModuleType("openai.resources")
    chat = types.ModuleType("openai.resources.chat")
    completions_mod = types.ModuleType("openai.resources.chat.completions")

    class Completions:
        last_call: dict[str, Any] = {}

        def create(self, **kwargs: Any) -> Any:
            Completions.last_call = kwargs
            return _FakeResp(
                model=kwargs.get("model"),
                content="hi from openai",
                tool_calls=None,
                finish_reason="stop",
            )

    class AsyncCompletions:
        async def create(self, **kwargs: Any) -> Any:
            return _FakeResp(
                model=kwargs.get("model"),
                content="async hi",
                tool_calls=None,
                finish_reason="stop",
            )

    completions_mod.Completions = Completions  # type: ignore[attr-defined]
    completions_mod.AsyncCompletions = AsyncCompletions  # type: ignore[attr-defined]
    chat.completions = completions_mod  # type: ignore[attr-defined]
    resources.chat = chat  # type: ignore[attr-defined]
    pkg.resources = resources  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "openai", pkg)
    monkeypatch.setitem(sys.modules, "openai.resources", resources)
    monkeypatch.setitem(sys.modules, "openai.resources.chat", chat)
    monkeypatch.setitem(sys.modules, "openai.resources.chat.completions", completions_mod)
    yield Completions
    from witness.adapters import openai as ad

    ad._PATCHED = False
    ad._ORIG_SYNC = None
    ad._ORIG_ASYNC = None


class _FakeMessage:
    def __init__(self, *, role: str, content: str | None, tool_calls: list[Any] | None) -> None:
        self.role = role
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content, "tool_calls": self.tool_calls}


class _FakeChoice:
    def __init__(self, *, message: _FakeMessage, finish_reason: str) -> None:
        self.message = message
        self.finish_reason = finish_reason


class _FakeUsage:
    prompt_tokens = 5
    completion_tokens = 7
    total_tokens = 12

    def model_dump(self) -> dict[str, Any]:
        return {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}


class _FakeResp:
    def __init__(
        self,
        *,
        model: str | None,
        content: str | None,
        tool_calls: list[Any] | None,
        finish_reason: str,
    ) -> None:
        self.id = "resp_fake"
        self.model = model
        self.choices = [
            _FakeChoice(
                message=_FakeMessage(role="assistant", content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )
        ]
        self.usage = _FakeUsage()


def test_openai_adapter_records_model_call(fake_openai, tmp_traces: Path) -> None:
    from witness.adapters import openai as ad

    ad.install()

    @witness.observe(name="agent", output_dir=str(tmp_traces))
    def agent() -> str:
        import openai

        c = openai.resources.chat.completions.Completions()
        resp = c.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=8,
        )
        return resp.choices[0].message.content or ""

    out = agent()
    assert out == "hi from openai"
    trace = agent.__witness_last_trace__
    assert trace is not None
    assert trace.model == "gpt-4o"
    types_seen = [d.type.value for d in trace.decisions]
    assert "model_call" in types_seen
    assert "final_output" in types_seen


def test_openai_adapter_records_tool_calls(fake_openai, tmp_traces: Path) -> None:
    from witness.adapters import openai as ad

    Completions = fake_openai

    def create_with_tool(self, **kwargs: Any) -> Any:
        tc = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "search", "arguments": '{"q":"foo"}'},
        }
        return _FakeResp(
            model=kwargs.get("model"),
            content=None,
            tool_calls=[tc],
            finish_reason="tool_calls",
        )

    Completions.create = create_with_tool  # type: ignore[method-assign]
    ad.install()

    @witness.observe(name="agent", output_dir=str(tmp_traces))
    def agent() -> None:
        import openai

        c = openai.resources.chat.completions.Completions()
        c.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "search!"}],
            tools=[
                {
                    "type": "function",
                    "function": {"name": "search", "description": "find things"},
                }
            ],
        )

    agent()
    trace = agent.__witness_last_trace__
    assert trace is not None
    tool_calls = [d for d in trace.decisions if d.type.value == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].input["name"] == "search"
    assert "search" in trace.tools_available
