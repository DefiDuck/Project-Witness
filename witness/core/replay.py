"""Replay: run a baseline trace's agent again with a perturbation applied.

Two ways to call replay:

1. Programmatic (preferred — you have the function in hand)::

       perturbed = witness.replay(baseline, Truncate(0.5), agent_fn=my_agent)

2. Trace-only (CLI path — load the function from the trace's `entrypoint`)::

       perturbed = witness.replay(baseline, Truncate(0.5))

   This dynamically imports the function recorded as `entrypoint` and re-runs it.
   Requires the agent code to be importable from the current Python environment.

Agents that want to *honor* model/tool overrides (``ModelSwap``, ``ToolRemoval``)
during replay should consult ``witness.replay_context()`` — non-None inside a
replay scope, None during baseline runs.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Callable, Optional

from witness.core.capture import (
    current_trace,
    release_decorator_save,
    suppress_decorator_save,
)
from witness.core.schema import Trace
from witness.core.store import PathLike, save_trace
from witness.perturbations.base import Perturbation, ReplayContext


_active_replay_ctx: ContextVar[Optional[ReplayContext]] = ContextVar(
    "witness_active_replay_ctx", default=None
)


def replay_context() -> Optional[ReplayContext]:
    """Return the perturbed ReplayContext if currently inside a `replay()` call,
    else None. Lets agents honor ModelSwap / ToolRemoval / temperature overrides::

        @witness.observe()
        def agent(prompt: str) -> str:
            ctx = witness.replay_context()
            model = ctx.model if ctx else "claude-opus-4-7"
            tools = ctx.tools_available if ctx else DEFAULT_TOOLS
            ...
    """
    return _active_replay_ctx.get()


def _push_replay_ctx(ctx: ReplayContext) -> Token[Optional[ReplayContext]]:
    return _active_replay_ctx.set(ctx)


def _pop_replay_ctx(token: Token[Optional[ReplayContext]]) -> None:
    _active_replay_ctx.reset(token)


def replay(
    baseline: Trace,
    perturbation: Perturbation,
    *,
    agent_fn: Optional[Callable[..., Any]] = None,
    output_path: Optional[PathLike] = None,
    save: bool = False,
) -> Trace:
    """Apply `perturbation` to `baseline` and re-run.

    Returns the new (perturbed) Trace.

    Parameters
    ----------
    baseline :
        The captured baseline Trace.
    perturbation :
        A Perturbation instance (e.g. ``Truncate(0.5)``).
    agent_fn :
        The agent function to call. If None, attempt to import it from
        `baseline.entrypoint`. The function must be `@witness.observe`-decorated
        for capture to work.
    output_path :
        If provided, also write the perturbed trace to this path.
    save :
        If True and `output_path` is None, write to `traces/<run_id>.trace.json`.
        Default False — perturbed traces are usually consumed in-memory.

    Notes
    -----
    The decorator's own save logic still runs and writes to whatever path the
    decorator was configured with. This function additionally writes to
    `output_path` if you pass one — useful for naming things `perturbed.json`.
    """
    fn = agent_fn or _import_entrypoint(baseline.entrypoint)
    if fn is None:
        raise ValueError(
            "replay() needs either agent_fn or a baseline with a resolvable "
            f"entrypoint. baseline.entrypoint={baseline.entrypoint!r}"
        )

    # Build the perturbed replay context.
    ctx = ReplayContext.from_trace(baseline)
    ctx = perturbation.apply(ctx)

    # Re-invoke the agent with perturbed inputs.
    perturbed_trace_holder: dict[str, Trace] = {}

    def _run() -> Any:
        if inspect.iscoroutinefunction(fn):
            return asyncio.run(fn(**ctx.inputs))
        return fn(**ctx.inputs)

    # The decorator captures into a NEW trace via its own contextvar. We suppress
    # its auto-save so the baseline file the decorator was configured to write
    # isn't clobbered by the perturbed re-run, and we expose the perturbed
    # ReplayContext so agents can honor model/tool overrides.
    save_token = suppress_decorator_save()
    ctx_token = _push_replay_ctx(ctx)
    try:
        _run()
    finally:
        _pop_replay_ctx(ctx_token)
        release_decorator_save(save_token)
    trace = getattr(fn, "__witness_last_trace__", None)
    if trace is None:
        # Fallback: try the still-active trace (extremely rare).
        trace = current_trace()
    if trace is None:
        raise RuntimeError(
            "replay completed but no trace was captured. Did you forget to wrap the "
            "agent with @witness.observe?"
        )

    # Stamp the perturbation lineage onto the new trace.
    trace.parent_run_id = baseline.run_id
    trace.perturbation = perturbation.record()
    perturbed_trace_holder["t"] = trace

    if output_path is not None:
        save_trace(trace, output_path)
    elif save:
        save_trace(trace, Path("traces") / f"{trace.run_id}.trace.json")

    return trace


def _import_entrypoint(entrypoint: Optional[str]) -> Optional[Callable[..., Any]]:
    """Import 'package.module:function_name' style entrypoint."""
    if not entrypoint or ":" not in entrypoint:
        return None
    module_name, qualname = entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj if callable(obj) else None


__all__ = ["replay", "replay_context"]
