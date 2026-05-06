"""Perturbation base class and ReplayContext shape."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from witness.core.schema import PerturbationRecord, Trace


@dataclass
class ReplayContext:
    """Everything the agent function needs to re-run, plus context for perturbations
    to mutate.

    A perturbation is allowed to mutate any field. The `inputs` dict is what gets
    spread back into the @observed function as its kwargs (or positional args via
    the special `_args` key).

    `messages` and `tools_available` are not always meaningful — only message-level
    perturbations (truncate, injection) touch them. For input-level perturbations
    (e.g. swap a doc path), only `inputs` is touched.
    """

    inputs: dict[str, Any]
    """The arguments captured from the baseline run (Trace.inputs)."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    """The messages the baseline trace ended with (Trace.messages, JSON-ified)."""

    tools_available: list[str] = field(default_factory=list)
    """Tool names that were available to the baseline. Mutate to remove tools."""

    model: str | None = None
    """Model name in the baseline. Mutate to swap models."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Free-form perturbation-specific scratch space."""

    @classmethod
    def from_trace(cls, trace: Trace) -> "ReplayContext":
        return cls(
            inputs=dict(trace.inputs),
            messages=[m.model_dump() for m in trace.messages],
            tools_available=list(trace.tools_available),
            model=trace.model,
            metadata={},
        )


class Perturbation(abc.ABC):
    """Apply a transformation to a ReplayContext.

    Subclasses implement `apply` and `record` (the description that goes into the
    perturbed trace's `perturbation` field).

    A perturbation should be idempotent on its parameters: same params + same
    baseline -> same modified context.
    """

    #: Short identifier used in the registry and the CLI (`--type <name>`).
    name: str = "perturbation"

    @abc.abstractmethod
    def apply(self, ctx: ReplayContext) -> ReplayContext:
        """Mutate or rebuild the ReplayContext. Should not raise on well-formed input."""

    def record(self) -> PerturbationRecord:
        """Description of this perturbation, embedded into the perturbed trace."""
        return PerturbationRecord(
            type=self.name,
            params=self._params(),
            summary=self._summary(),
        )

    # Override these hooks for clean records:
    def _params(self) -> dict[str, Any]:
        return {}

    def _summary(self) -> str:
        return self.name


__all__ = ["Perturbation", "ReplayContext"]
