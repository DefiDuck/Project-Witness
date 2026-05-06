"""Versioned JSON Schema files for the on-disk trace format.

The current schema is exported as ``trace_v1.json`` next to this package. It's
auto-generated from the pydantic models in ``witness.core.schema`` — regenerate
with ``python -m witness.schema.generate`` (or ``witness schema --regenerate``).
"""
from __future__ import annotations

import json
from pathlib import Path

from witness.core.schema import SCHEMA_VERSION, Trace

_HERE = Path(__file__).parent


def schema_path(version: str = "v1") -> Path:
    """Path to the on-disk JSON Schema for the given version."""
    return _HERE / f"trace_{version}.json"


def load_schema(version: str = "v1") -> dict:
    """Read and parse the on-disk JSON Schema."""
    return json.loads(schema_path(version).read_text(encoding="utf-8"))


def generate_schema_dict() -> dict:
    """Build the JSON Schema dict from the live pydantic Trace model."""
    schema = Trace.model_json_schema()
    schema["$id"] = "https://github.com/witness-ai/witness/schema/trace_v1.json"
    schema["title"] = f"Witness Trace v{SCHEMA_VERSION}"
    schema["description"] = (
        "Stable on-disk format for an agent trace. Forward-compatible: unknown "
        "top-level fields and unknown fields inside any object should be preserved."
    )
    return schema


def write_schema_file(version: str = "v1") -> Path:
    """Regenerate the on-disk schema file. Returns the path written."""
    p = schema_path(version)
    p.write_text(
        json.dumps(generate_schema_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    return p


__all__ = ["schema_path", "load_schema", "generate_schema_dict", "write_schema_file"]
