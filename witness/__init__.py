"""Witness — capture, perturb, and diff LLM agent decisions.

Public API:

    @witness.observe(name="my_agent")
    def my_agent(...): ...

    baseline  = my_agent(...)                                    # captures trace
    perturbed = witness.replay(baseline, perturbations.Truncate(0.5))
    delta     = witness.diff(baseline, perturbed)
"""
from __future__ import annotations

from witness.core.capture import current_trace, observe, record_decision
from witness.core.replay import replay, replay_context
from witness.core.schema import (
    Decision,
    DecisionType,
    Message,
    PerturbationRecord,
    Role,
    Trace,
)
from witness.core.store import load_trace, save_trace
from witness.diff.behavioral import TraceDiff, diff
from witness.perturbations import (
    ModelSwap,
    Perturbation,
    PromptInjection,
    ToolRemoval,
    Truncate,
    get_perturbation,
    register_perturbation,
)

__version__ = "0.1.0"

__all__ = [
    # core
    "observe",
    "record_decision",
    "current_trace",
    "replay",
    "replay_context",
    "diff",
    # schema
    "Trace",
    "Message",
    "Decision",
    "DecisionType",
    "Role",
    "PerturbationRecord",
    # store
    "save_trace",
    "load_trace",
    # diff
    "TraceDiff",
    # perturbations
    "Perturbation",
    "Truncate",
    "PromptInjection",
    "ModelSwap",
    "ToolRemoval",
    "register_perturbation",
    "get_perturbation",
    # subpackage handles
    "perturbations",
]

# expose subpackage as attribute for `witness.perturbations.Truncate(...)`
from witness import perturbations  # noqa: E402,F401
