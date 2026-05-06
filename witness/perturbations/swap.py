"""Model and tool swap perturbations.

These mutate ``ReplayContext.model`` / ``ReplayContext.tools_available``. To
take effect, the agent must consult those values during the run — see
``witness.replay_context`` (set when ``replay()`` is active) for how.

Perturbations are still recorded in the trace's `perturbation` field even when
the agent ignores the override, so a fingerprint run can detect "this agent
doesn't honor model swaps" as a stability fact in itself.
"""
from __future__ import annotations

from typing import Any

from witness.perturbations.base import Perturbation, ReplayContext
from witness.perturbations.registry import register_perturbation


@register_perturbation()
class ModelSwap(Perturbation):
    """Replace the model identifier the agent will use during replay."""

    name = "model_swap"

    def __init__(self, target: str) -> None:
        if not target:
            raise ValueError("ModelSwap requires a non-empty target model name")
        self.target = target

    def apply(self, ctx: ReplayContext) -> ReplayContext:
        ctx.metadata["model_swap"] = {"original": ctx.model, "target": self.target}
        ctx.model = self.target
        return ctx

    def _params(self) -> dict[str, Any]:
        return {"target": self.target}

    def _summary(self) -> str:
        return f"swap model -> {self.target}"


@register_perturbation()
class ToolRemoval(Perturbation):
    """Remove a named tool (or all tools) from ``tools_available``."""

    name = "tool_removal"

    def __init__(self, tool: str | None = None) -> None:
        """If `tool` is None, remove ALL tools."""
        self.tool = tool

    def apply(self, ctx: ReplayContext) -> ReplayContext:
        if self.tool is None:
            removed = list(ctx.tools_available)
            ctx.tools_available = []
        else:
            removed = [t for t in ctx.tools_available if t == self.tool]
            ctx.tools_available = [t for t in ctx.tools_available if t != self.tool]
        ctx.metadata["tool_removal"] = {"removed": removed}
        return ctx

    def _params(self) -> dict[str, Any]:
        return {"tool": self.tool}

    def _summary(self) -> str:
        return "removed all tools" if self.tool is None else f"removed tool '{self.tool}'"


__all__ = ["ModelSwap", "ToolRemoval"]
