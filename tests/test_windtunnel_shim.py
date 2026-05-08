"""The `windtunnel` package is a re-export shim of `witness`.

These tests confirm both `import windtunnel; windtunnel.observe(...)` and
`python -m windtunnel ...` work — the rebrand promised both forms in the
v0.3 release notes, but the actual shim only landed later.
"""
from __future__ import annotations

import subprocess
import sys


def test_windtunnel_re_exports_observe() -> None:
    import windtunnel
    import witness

    # Same callable, not just a same-named function
    assert windtunnel.observe is witness.observe
    assert windtunnel.diff is witness.diff
    assert windtunnel.replay is witness.replay
    assert windtunnel.Truncate is witness.Truncate
    assert windtunnel.__version__ == witness.__version__


def test_windtunnel_observe_decorator_works() -> None:
    import windtunnel

    @windtunnel.observe(name="t", save=False)
    def f(x: int) -> int:
        return x * 2

    out = f(7)
    assert out == 14
    trace = f.__witness_last_trace__  # type: ignore[attr-defined]
    assert trace is not None
    assert trace.agent_name == "t"


def test_python_dash_m_windtunnel_runs() -> None:
    """`python -m windtunnel --help` should exit 0 and print the CLI help."""
    result = subprocess.run(
        [sys.executable, "-m", "windtunnel", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    out = (result.stdout + result.stderr).lower()
    assert "windtunnel" in out
    # The help should advertise at least one of the canonical commands.
    assert "diff" in out or "perturb" in out
