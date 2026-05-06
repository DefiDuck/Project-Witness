"""Capture: the @observe decorator and the context machinery that adapters listen on.

Design
------
A `Trace` is created when an @observe-wrapped function is entered, stored in a
contextvar, populated by the function (directly via `record_decision` or indirectly
via SDK adapters that read the contextvar), and serialized to disk on exit.

Async-safe: contextvars propagate across `await` and `asyncio.gather`. The same
trace is visible to every coroutine running inside the @observe scope.

One trace at a time per task: nesting an @observe inside another @observe replaces
the active trace for the inner scope, restoring on exit. The library does not try
to merge nested traces — keep your agent function the boundary.
"""
from __future__ import annotations

import functools
import inspect
import time
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar, Union, cast, overload

from witness.core.schema import (
    Decision,
    DecisionType,
    Trace,
)
from witness.core.store import PathLike, save_trace

_F = TypeVar("_F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Active-trace context variable
# ---------------------------------------------------------------------------

_active_trace: ContextVar[Optional[Trace]] = ContextVar("witness_active_trace", default=None)
_suppress_save: ContextVar[bool] = ContextVar("witness_suppress_save", default=False)


def current_trace() -> Optional[Trace]:
    """Return the trace currently being captured, or None if not inside @observe."""
    return _active_trace.get()


def _push_trace(trace: Trace) -> Token[Optional[Trace]]:
    return _active_trace.set(trace)


def _pop_trace(token: Token[Optional[Trace]]) -> None:
    _active_trace.reset(token)


def suppress_decorator_save() -> Token[bool]:
    """Internal: tell @observe wrappers to not write to disk for the lifetime of the
    returned token. Used by `replay()` so the decorator's configured output_path
    isn't clobbered when the agent is re-invoked.

    Pair with ``release_decorator_save(token)``.
    """
    return _suppress_save.set(True)


def release_decorator_save(token: Token[bool]) -> None:
    _suppress_save.reset(token)


def _is_save_suppressed() -> bool:
    return _suppress_save.get()


# ---------------------------------------------------------------------------
# Public helper for user-recorded decisions
# ---------------------------------------------------------------------------


def record_decision(
    type: DecisionType | str,
    *,
    input: Optional[dict[str, Any]] = None,
    output: Optional[dict[str, Any]] = None,
    parent_step_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Decision]:
    """Record a decision into the active trace.

    Returns the Decision, or None if there is no active trace (in which case this
    is a no-op — safe to leave in code that runs both inside and outside @observe).
    """
    trace = current_trace()
    if trace is None:
        return None
    return trace.add_decision(
        type=type,
        input=input,
        output=output,
        parent_step_id=parent_step_id,
        duration_ms=duration_ms,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Argument capture
# ---------------------------------------------------------------------------


def _safe_repr(value: Any, *, max_chars: int = 4_000) -> Any:
    """Best-effort serialize an arbitrary Python value into something JSON-friendly.

    We never want @observe to crash on a weird input. If a value can't be converted,
    we fall back to `repr(value)` truncated to a sane length.
    """
    try:
        # Most pydantic models, dicts, lists, scalars — round-trip via json.
        import json as _json

        _json.dumps(value)
        return value
    except (TypeError, ValueError):
        try:
            r = repr(value)
        except Exception:  # pragma: no cover — extremely defensive
            r = f"<unrepresentable {type(value).__name__}>"
        return r[:max_chars] + ("…<truncated>" if len(r) > max_chars else "")


def _capture_inputs(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Bind args/kwargs to parameter names, then JSON-coerce them."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return {k: _safe_repr(v) for k, v in bound.arguments.items()}
    except (TypeError, ValueError):
        return {
            "args": [_safe_repr(a) for a in args],
            "kwargs": {k: _safe_repr(v) for k, v in kwargs.items()},
        }


def _entrypoint_for(func: Callable[..., Any]) -> str:
    """`module.path:function_name` — used to re-import the function for replay.

    When the function is defined inside the entry-point script (``__module__ ==
    '__main__'``), try to recover the real module path from
    ``sys.modules['__main__'].__spec__.name`` — this is set when the script is
    invoked via ``python -m pkg.module`` and lets `witness perturb` find the
    function from a fresh process.
    """
    import sys

    mod = getattr(func, "__module__", "") or ""
    if mod == "__main__":
        main_mod = sys.modules.get("__main__")
        spec = getattr(main_mod, "__spec__", None)
        if spec is not None and getattr(spec, "name", None):
            mod = spec.name
    qual = getattr(func, "__qualname__", getattr(func, "__name__", "<anon>"))
    return f"{mod}:{qual}"


# ---------------------------------------------------------------------------
# The decorator
# ---------------------------------------------------------------------------


@overload
def observe(func: _F) -> _F: ...


@overload
def observe(
    *,
    name: Optional[str] = ...,
    output_dir: Optional[PathLike] = ...,
    output_path: Optional[PathLike] = ...,
    save: bool = ...,
    capture_inputs: bool = ...,
    metadata: Optional[dict[str, Any]] = ...,
) -> Callable[[_F], _F]: ...


def observe(
    func: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    output_dir: Optional[PathLike] = None,
    output_path: Optional[PathLike] = None,
    save: bool = True,
    capture_inputs: bool = True,
    metadata: Optional[dict[str, Any]] = None,
) -> Any:
    """Wrap an agent function so its inputs, decisions, and outputs are captured.

    Usage::

        @witness.observe                                    # bare form
        def agent(...): ...

        @witness.observe(name="research_agent")             # with options
        def agent(...): ...

    Parameters
    ----------
    name :
        Display name for the trace's `agent_name`. Defaults to the function name.
    output_dir :
        Directory to write `<run_id>.trace.json` into. Defaults to ``./traces/``.
        Ignored if `output_path` is provided.
    output_path :
        Exact file path to write the trace to. Overrides `output_dir`.
    save :
        If False, do not write to disk — return the Trace via ``trace`` attribute on
        the wrapped function's return value (also accessible via ``current_trace()``
        during the call). Useful for tests.
    capture_inputs :
        If True (default), record arguments passed to the function in the trace's
        ``inputs`` field.
    metadata :
        Free-form dict copied into ``trace.metadata``.

    Returns
    -------
    The function's original return value, unchanged. The trace itself is written
    to disk and made available via ``witness.current_trace()`` during the call,
    or via the special attribute ``__witness_last_trace__`` on the wrapped
    function after the call returns.
    """

    # Decorator-without-parens form: @observe (no call)
    if func is not None and callable(func):
        return _build_wrapper(
            func,
            name=name,
            output_dir=output_dir,
            output_path=output_path,
            save=save,
            capture_inputs=capture_inputs,
            metadata=metadata,
        )

    # Decorator-with-parens form: @observe(...)
    def deco(f: _F) -> _F:
        return cast(
            _F,
            _build_wrapper(
                f,
                name=name,
                output_dir=output_dir,
                output_path=output_path,
                save=save,
                capture_inputs=capture_inputs,
                metadata=metadata,
            ),
        )

    return deco


def _build_wrapper(
    func: Callable[..., Any],
    *,
    name: Optional[str],
    output_dir: Optional[PathLike],
    output_path: Optional[PathLike],
    save: bool,
    capture_inputs: bool,
    metadata: Optional[dict[str, Any]],
) -> Callable[..., Any]:
    is_coro = inspect.iscoroutinefunction(func)
    agent_name = name or func.__name__
    entrypoint = _entrypoint_for(func)

    def _new_trace(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Trace:
        trace = Trace(
            agent_name=agent_name,
            entrypoint=entrypoint,
            metadata=dict(metadata) if metadata else {},
        )
        if capture_inputs:
            trace.inputs = _capture_inputs(func, args, kwargs)
        return trace

    def _resolve_output_path(trace: Trace) -> Path:
        if output_path is not None:
            return Path(output_path)
        directory = Path(output_dir) if output_dir is not None else Path("traces")
        return directory / f"{trace.run_id}.trace.json"

    def _finalize(trace: Trace, started: float, result: Any) -> None:
        trace.finalize(final_output=_safe_repr(result), started_monotonic=started)
        if save and not _is_save_suppressed():
            save_trace(trace, _resolve_output_path(trace))
        # stash on the function for the caller's convenience
        wrapper.__witness_last_trace__ = trace  # type: ignore[attr-defined]

    if is_coro:

        @functools.wraps(func)
        async def awrapper(*args: Any, **kwargs: Any) -> Any:
            trace = _new_trace(args, kwargs)
            token = _push_trace(trace)
            started = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                _finalize(trace, started, result)
                return result
            except BaseException as e:
                # Capture exceptions into the trace, then re-raise.
                trace.metadata.setdefault("exception", {})
                trace.metadata["exception"] = {
                    "type": type(e).__name__,
                    "message": str(e),
                }
                _finalize(trace, started, None)
                raise
            finally:
                _pop_trace(token)

        wrapper: Callable[..., Any] = awrapper
    else:

        @functools.wraps(func)
        def swrapper(*args: Any, **kwargs: Any) -> Any:
            trace = _new_trace(args, kwargs)
            token = _push_trace(trace)
            started = time.monotonic()
            try:
                result = func(*args, **kwargs)
                _finalize(trace, started, result)
                return result
            except BaseException as e:
                trace.metadata.setdefault("exception", {})
                trace.metadata["exception"] = {
                    "type": type(e).__name__,
                    "message": str(e),
                }
                _finalize(trace, started, None)
                raise
            finally:
                _pop_trace(token)

        wrapper = swrapper

    # Always-attach attributes
    wrapper.__witness_observed__ = True  # type: ignore[attr-defined]
    wrapper.__witness_entrypoint__ = entrypoint  # type: ignore[attr-defined]
    wrapper.__witness_last_trace__ = None  # type: ignore[attr-defined]
    return wrapper


__all__ = [
    "observe",
    "current_trace",
    "record_decision",
]


# Re-export type so consumers don't need a separate import path.
ObserveDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
ObservedFn = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]
