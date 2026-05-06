"""Context truncation perturbation.

Removes a fraction (default 0.5) of the *trailing* context from the conversation.
"Context" here means the message history fed to the agent — by chopping the latest
N% of it, we simulate an agent operating with a shorter scrollback (a common real
failure mode).

Strategy
--------
The truncate perturbation operates on two layers:

1. `messages` (the conversation history captured in the baseline trace).
   We drop the last `fraction` of message blocks, but always preserve the very
   first `system` message if present.

2. `inputs` (the kwargs that re-running the agent will re-feed).
   For string-valued kwargs that look like documents (length > 200 chars, or kwarg
   name in {"doc", "document", "context", "text", "content"}), we truncate the
   string to `1 - fraction` of its original length from the end.

The combination means a re-run with the same agent function will see both:
  - a shorter input doc (the tool input changes), and
  - a shorter message list if you replay manually with the captured history.
"""
from __future__ import annotations

from typing import Any

from witness.perturbations.base import Perturbation, ReplayContext
from witness.perturbations.registry import register_perturbation

_DOC_LIKE_KWARGS = frozenset({"doc", "document", "context", "text", "content", "input", "passage"})


@register_perturbation()
class Truncate(Perturbation):
    """Drop a fraction of trailing context from the run.

    Parameters
    ----------
    fraction : float
        Fraction of context to *remove*. 0.5 means remove the latter half.
        Must be in (0, 1).
    preserve_system : bool
        If True (default), the first `system`-role message is always kept even if
        it falls in the truncation window.
    """

    name = "truncate"

    def __init__(self, fraction: float = 0.5, *, preserve_system: bool = True) -> None:
        if not 0 < fraction < 1:
            raise ValueError(f"fraction must be in (0, 1); got {fraction}")
        self.fraction = float(fraction)
        self.preserve_system = preserve_system

    def apply(self, ctx: ReplayContext) -> ReplayContext:
        keep_ratio = 1.0 - self.fraction

        # 1. Truncate message history
        msgs = list(ctx.messages)
        if msgs:
            keep_count = max(1, int(round(len(msgs) * keep_ratio)))
            head: list[dict[str, Any]] = []
            if self.preserve_system and msgs[0].get("role") == "system":
                head = [msgs[0]]
                # We still want at least 1 non-system message if the original had one.
                tail_pool = msgs[1:]
                tail_keep = max(0, keep_count - 1) if tail_pool else 0
                truncated = head + tail_pool[:tail_keep]
            else:
                truncated = msgs[:keep_count]
            ctx.messages = truncated

        # 2. Truncate doc-like inputs
        for k, v in list(ctx.inputs.items()):
            if not isinstance(v, str):
                continue
            if k in _DOC_LIKE_KWARGS or len(v) > 200:
                new_len = max(1, int(round(len(v) * keep_ratio)))
                ctx.inputs[k] = v[:new_len]

        ctx.metadata["truncate"] = {
            "fraction": self.fraction,
            "preserve_system": self.preserve_system,
        }
        return ctx

    def _params(self) -> dict[str, Any]:
        return {"fraction": self.fraction, "preserve_system": self.preserve_system}

    def _summary(self) -> str:
        pct = int(self.fraction * 100)
        return f"removed last {pct}% of context"


__all__ = ["Truncate"]
