"""Streamlit-powered web UI for Witness.

Run with: ``witness ui`` (or ``streamlit run witness/ui/app.py``).

Public re-exports:

  ``witness.ui.export``     — pure-Python markdown export helpers (no streamlit dep).
  ``witness.ui.components`` — reusable UI building blocks (streamlit dep).
  ``witness.ui.APP_PATH``   — file path to the Streamlit app.
"""
from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).parent / "app.py"

# Re-export the export helpers so callers can `from witness.ui import diff_to_markdown`
# without having to import streamlit (export.py has no streamlit imports).
from witness.ui.export import (  # noqa: E402
    diff_to_markdown,
    fingerprint_to_markdown,
    preset_from_json,
    preset_to_json,
    trace_to_markdown,
)
from witness.ui.lineage import render_lineage_svg  # noqa: E402
from witness.ui.onboarding import SAMPLE_DOC, generate_sample_traces  # noqa: E402

__all__ = [
    "APP_PATH",
    "diff_to_markdown",
    "fingerprint_to_markdown",
    "trace_to_markdown",
    "preset_to_json",
    "preset_from_json",
    "generate_sample_traces",
    "SAMPLE_DOC",
    "render_lineage_svg",
]
