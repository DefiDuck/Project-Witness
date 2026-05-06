"""Trace serialization to JSON files.

Plain JSON. No SQLite, no DB, no remote backend — that's intentional for v0. The
store layer is a single screen of code so anyone can swap it out.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from witness.core.schema import Trace

PathLike = Union[str, Path]


def save_trace(trace: Trace, path: PathLike, *, indent: int = 2) -> Path:
    """Write a Trace to disk as JSON. Returns the resolved Path."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        trace.model_dump_json(indent=indent, exclude_none=False),
        encoding="utf-8",
    )
    return p


def load_trace(path: PathLike) -> Trace:
    """Read a Trace from a JSON file. Forward-compatible: unknown fields are preserved
    (schema models use extra='allow').
    """
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    return Trace.model_validate_json(raw)


def load_trace_dict(path: PathLike) -> dict[str, Any]:
    """For tooling that wants the raw dict (e.g. for migrations)."""
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


__all__ = ["save_trace", "load_trace", "load_trace_dict", "PathLike"]
