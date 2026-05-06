"""JSON Schema generation and CLI."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from witness.cli import cli
from witness.core.schema import SCHEMA_VERSION
from witness.schema import generate_schema_dict, write_schema_file


def test_generate_schema_dict_has_expected_top_level() -> None:
    schema = generate_schema_dict()
    assert schema["title"].startswith("Witness Trace")
    assert SCHEMA_VERSION in schema["title"]
    assert "$id" in schema
    assert "properties" in schema
    # Top-level required Trace fields are present
    for key in ("agent_name", "decisions", "messages", "schema_version"):
        assert key in schema["properties"]


def test_write_schema_file_round_trip(tmp_path: Path, monkeypatch) -> None:
    # Redirect _HERE so we don't clobber the real schema during tests
    import witness.schema as ws

    monkeypatch.setattr(ws, "_HERE", tmp_path)
    p = write_schema_file()
    assert p.exists()
    parsed = json.loads(p.read_text(encoding="utf-8"))
    assert parsed["title"].startswith("Witness Trace")


def test_cli_schema_default_prints_json() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["schema"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "properties" in parsed


def test_cli_schema_path_prints_path() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["schema", "--path"])
    assert result.exit_code == 0
    assert result.output.strip().endswith("trace_v1.json")
