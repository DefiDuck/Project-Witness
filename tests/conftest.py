"""Shared pytest fixtures: deterministic mock LLM and tmp trace dirs."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def tmp_traces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp directory the @observe decorator will write into.

    Tests pointing @observe at this fixture get fully isolated traces.
    """
    out = tmp_path / "traces"
    out.mkdir()
    monkeypatch.chdir(tmp_path)
    return out


# ---------------------------------------------------------------------------
# MockLLM — used by tests that exercise the adapters without hitting the network
# ---------------------------------------------------------------------------


class MockLLMResponse:
    """Anthropic-shaped response object. Supports `.content`, `.stop_reason`,
    `.usage`, `.id`, `.role`, `.model`."""

    def __init__(
        self,
        *,
        text: str | None = None,
        tool_uses: list[dict[str, Any]] | None = None,
        stop_reason: str = "end_turn",
        model: str = "mock-claude",
    ) -> None:
        blocks: list[dict[str, Any]] = []
        if text is not None:
            blocks.append({"type": "text", "text": text})
        for tu in tool_uses or []:
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tu.get("id", "tu_1"),
                    "name": tu["name"],
                    "input": tu.get("input", {}),
                }
            )
        # Use a tiny SimpleNamespace-like wrapper so adapters' getattr/model_dump
        # paths exercise both branches.
        self.content = [_Block(b) for b in blocks]
        self.stop_reason = stop_reason
        self.usage = _Usage(input_tokens=10, output_tokens=20)
        self.id = "msg_mock_1"
        self.role = "assistant"
        self.model = model


class _Block:
    """An object that mimics an Anthropic content block (model_dump aware)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        for k, v in data.items():
            setattr(self, k, v)

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)


class _Usage:
    def __init__(self, *, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def model_dump(self) -> dict[str, Any]:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}


@pytest.fixture
def mock_llm_response() -> type[MockLLMResponse]:
    return MockLLMResponse


# ---------------------------------------------------------------------------
# Skip integration tests unless explicitly enabled
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if os.environ.get("RUN_INTEGRATION") == "1":
        return
    skip_integ = pytest.mark.skip(reason="set RUN_INTEGRATION=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integ)
