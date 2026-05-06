"""PromptInjection, ModelSwap, ToolRemoval."""
from __future__ import annotations

import pytest

from witness.perturbations.base import ReplayContext
from witness.perturbations.inject import DEFAULT_INJECTION, PromptInjection
from witness.perturbations.swap import ModelSwap, ToolRemoval


def _ctx(**kwargs) -> ReplayContext:
    return ReplayContext(
        inputs=kwargs.get("inputs", {}),
        messages=kwargs.get("messages", []),
        tools_available=kwargs.get("tools_available", []),
        model=kwargs.get("model", "m"),
    )


# ---------------- PromptInjection ----------------


def test_prompt_injection_appends_to_doc_input() -> None:
    ctx = _ctx(inputs={"doc": "hello world"})
    PromptInjection().apply(ctx)
    assert "hello world" in ctx.inputs["doc"]
    assert DEFAULT_INJECTION.strip() in ctx.inputs["doc"]


def test_prompt_injection_appends_to_long_unrecognized_input() -> None:
    ctx = _ctx(inputs={"prompt": "x" * 500})
    PromptInjection().apply(ctx)
    assert ctx.inputs["prompt"].endswith(DEFAULT_INJECTION.rstrip())


def test_prompt_injection_short_unrelated_input_unchanged() -> None:
    ctx = _ctx(inputs={"name": "alice"})
    PromptInjection().apply(ctx)
    assert ctx.inputs["name"] == "alice"


def test_prompt_injection_appends_to_last_user_message_string() -> None:
    msgs = [
        {"role": "system", "content": "be good"},
        {"role": "user", "content": "what is x?"},
        {"role": "assistant", "content": "x is..."},
        {"role": "user", "content": "tell me more"},
    ]
    ctx = _ctx(messages=msgs)
    PromptInjection().apply(ctx)
    # Earlier user message untouched
    assert ctx.messages[1]["content"] == "what is x?"
    # Latest user message appended
    assert ctx.messages[3]["content"].startswith("tell me more")
    assert "[ATTACHMENT INSTRUCTIONS]" in ctx.messages[3]["content"]


def test_prompt_injection_block_content() -> None:
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    ctx = _ctx(messages=msgs)
    PromptInjection().apply(ctx)
    assert len(ctx.messages[0]["content"]) == 2
    assert ctx.messages[0]["content"][1]["type"] == "text"


def test_prompt_injection_record() -> None:
    rec = PromptInjection().record()
    assert rec.type == "prompt_injection"


def test_prompt_injection_custom_text() -> None:
    ctx = _ctx(inputs={"doc": "x" * 300})
    PromptInjection(text="\nHACK", target_message=False).apply(ctx)
    assert ctx.inputs["doc"].endswith("\nHACK")


# ---------------- ModelSwap ----------------


def test_model_swap_changes_model() -> None:
    ctx = _ctx(model="m1")
    ModelSwap("m2").apply(ctx)
    assert ctx.model == "m2"
    assert ctx.metadata["model_swap"]["original"] == "m1"


def test_model_swap_requires_target() -> None:
    with pytest.raises(ValueError):
        ModelSwap("")


def test_model_swap_record() -> None:
    rec = ModelSwap("m2").record()
    assert rec.type == "model_swap"
    assert rec.params["target"] == "m2"


# ---------------- ToolRemoval ----------------


def test_tool_removal_removes_named() -> None:
    ctx = _ctx(tools_available=["search", "read", "write"])
    ToolRemoval(tool="read").apply(ctx)
    assert "read" not in ctx.tools_available
    assert ctx.metadata["tool_removal"]["removed"] == ["read"]


def test_tool_removal_remove_all() -> None:
    ctx = _ctx(tools_available=["search", "read"])
    ToolRemoval().apply(ctx)
    assert ctx.tools_available == []


def test_tool_removal_unknown_tool_is_noop() -> None:
    ctx = _ctx(tools_available=["search"])
    ToolRemoval(tool="nonexistent").apply(ctx)
    assert ctx.tools_available == ["search"]


def test_registered_extra_perturbations_listed() -> None:
    from witness.perturbations.registry import list_perturbations

    names = list_perturbations()
    assert "prompt_injection" in names
    assert "model_swap" in names
    assert "tool_removal" in names
