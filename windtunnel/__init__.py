"""windtunnel — public package alias for ``witness``.

The project was rebranded from Witness to WindTunnel in v0.3.0. The Python
source still lives under ``witness/`` so existing ``import witness`` calls
keep working without churn, but ``import windtunnel`` should work too —
and so should ``python -m windtunnel ...``. This package is a thin shim
that re-exports everything from ``witness`` and delegates the CLI.
"""
from __future__ import annotations

# Re-export the public API surface so `import windtunnel; windtunnel.observe(...)`
# is identical to `import witness; witness.observe(...)`.
from witness import (
    Decision,
    DecisionType,
    Message,
    ModelSwap,
    Perturbation,
    PerturbationRecord,
    PromptInjection,
    Role,
    ToolRemoval,
    Trace,
    TraceDiff,
    Truncate,
    __version__,
    current_trace,
    diff,
    get_perturbation,
    load_trace,
    observe,
    perturbations,
    record_decision,
    register_perturbation,
    replay,
    replay_context,
    save_trace,
)

__all__ = [
    "Decision",
    "DecisionType",
    "Message",
    "ModelSwap",
    "Perturbation",
    "PerturbationRecord",
    "PromptInjection",
    "Role",
    "ToolRemoval",
    "Trace",
    "TraceDiff",
    "Truncate",
    "__version__",
    "current_trace",
    "diff",
    "get_perturbation",
    "load_trace",
    "observe",
    "perturbations",
    "record_decision",
    "register_perturbation",
    "replay",
    "replay_context",
    "save_trace",
]
