"""Smoke tests for the Streamlit app module.

We don't spin up a real Streamlit server in unit tests — that would be slow
and platform-dependent. Instead we verify:

1. The app file exists at the expected path.
2. ``import witness.ui`` exposes APP_PATH.
3. The CLI ``witness ui --print-path`` returns it.
4. The app file parses without syntax errors.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from click.testing import CliRunner

from witness.cli import cli


def test_app_path_exists() -> None:
    from witness.ui import APP_PATH

    assert APP_PATH.exists()
    assert APP_PATH.name == "app.py"


def test_app_module_parses() -> None:
    """Catch syntax errors in app.py without executing it (executing would need
    a running Streamlit context)."""
    from witness.ui import APP_PATH

    source = APP_PATH.read_text(encoding="utf-8")
    ast.parse(source)  # raises SyntaxError on bad code


def test_cli_ui_print_path() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["ui", "--print-path"])
    assert result.exit_code == 0
    p = Path(result.output.strip())
    assert p.exists()
    assert p.name == "app.py"


def test_cli_ui_streamlit_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """When streamlit isn't importable, the CLI should give a friendly error."""
    import sys

    # Pretend streamlit isn't there. We do this by interceping the import.
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "streamlit":
            raise ImportError("no streamlit")
        return real_import(name, *args, **kwargs)

    if isinstance(__builtins__, dict):
        monkeypatch.setitem(__builtins__, "__import__", fake_import)
    else:
        monkeypatch.setattr(__builtins__, "__import__", fake_import)

    runner = CliRunner()
    result = runner.invoke(cli, ["ui"])
    assert result.exit_code == 2
    assert "streamlit" in (result.output + (result.stderr or "")).lower()
