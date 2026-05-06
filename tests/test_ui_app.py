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


def test_cli_ui_subprocess_failure_emits_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the streamlit subprocess fails, the CLI should print an install hint."""
    import witness.cli as cli_mod

    # Force subprocess.call to return a non-zero code as if streamlit refused to start.
    def fake_call(args, **kwargs):
        return 1

    # The CLI imports `subprocess` lazily inside cmd_ui — patch the top-level module.
    import subprocess as _subprocess

    monkeypatch.setattr(_subprocess, "call", fake_call)

    runner = CliRunner()
    result = runner.invoke(cli_mod.cli, ["ui", "--no-browser"])
    assert result.exit_code == 1
    output = result.output + (result.stderr or "")
    # Either way, the user gets a hint that mentions streamlit + pip install.
    assert "streamlit" in output.lower()
    assert "pip install" in output.lower()
