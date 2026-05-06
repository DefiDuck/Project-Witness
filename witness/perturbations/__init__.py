"""Perturbations: transforms applied to a baseline trace before replay.

A `Perturbation` is a pure function from a `ReplayContext` (the inputs that would
be fed to a re-run of the agent) to a modified `ReplayContext` plus a record of
what was changed.

Built-in perturbations register themselves into a global registry so the CLI can
look them up by name (`--type truncate`).
"""
from __future__ import annotations

from witness.perturbations.base import Perturbation, ReplayContext
from witness.perturbations.inject import DEFAULT_INJECTION, PromptInjection
from witness.perturbations.registry import (
    PERTURBATION_REGISTRY,
    get_perturbation,
    list_perturbations,
    register_perturbation,
)
from witness.perturbations.swap import ModelSwap, ToolRemoval
from witness.perturbations.truncate import Truncate

__all__ = [
    "Perturbation",
    "ReplayContext",
    "Truncate",
    "PromptInjection",
    "DEFAULT_INJECTION",
    "ModelSwap",
    "ToolRemoval",
    "PERTURBATION_REGISTRY",
    "register_perturbation",
    "get_perturbation",
    "list_perturbations",
]
