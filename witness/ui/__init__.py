"""Streamlit-powered web UI for Witness.

Run with: ``witness ui`` (or ``streamlit run witness/ui/app.py``).
"""
from __future__ import annotations

from pathlib import Path

APP_PATH = Path(__file__).parent / "app.py"

__all__ = ["APP_PATH"]
