"""Witness CLI: `witness diff`, `witness perturb`, `witness inspect`, `witness perturbations`.

The CLI is intentionally minimal — it's a thin wrapper over the library.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import click

from witness import __version__
from witness.adapters import install_all
from witness.core.replay import replay
from witness.core.store import load_trace, save_trace
from witness.diff.behavioral import diff as diff_traces
from witness.diff.fingerprint import fingerprint as build_fingerprint
from witness.diff.format import format_text
from witness.perturbations.registry import (
    PERTURBATION_REGISTRY,
    get_perturbation,
    list_perturbations,
)
from witness.schema import generate_schema_dict, schema_path, write_schema_file


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="witness")
def cli() -> None:
    """Witness — capture, perturb, and diff LLM agent decisions."""


# ---------------------------------------------------------------------------
# `witness diff`
# ---------------------------------------------------------------------------


@cli.command("diff")
@click.argument("baseline", type=click.Path(exists=True, path_type=Path))
@click.argument("perturbed", type=click.Path(exists=True, path_type=Path))
@click.option("--no-color", is_flag=True, help="Disable ANSI color output.")
@click.option("--json", "as_json", is_flag=True, help="Output a structured JSON diff.")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show unchanged decisions and full final-output bodies.",
)
def cmd_diff(
    baseline: Path,
    perturbed: Path,
    no_color: bool,
    as_json: bool,
    verbose: bool,
) -> None:
    """Compare two trace JSON files and print a behavioral diff."""
    base = load_trace(baseline)
    pert = load_trace(perturbed)
    d = diff_traces(base, pert)
    if as_json:
        click.echo(d.to_json())
        return
    color = (not no_color) and sys.stdout.isatty()
    click.echo(format_text(d, color=color, verbose=verbose))


# ---------------------------------------------------------------------------
# `witness perturb`
# ---------------------------------------------------------------------------


@cli.command("perturb")
@click.argument("baseline", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--type",
    "ptype",
    required=True,
    type=click.Choice(sorted(PERTURBATION_REGISTRY.keys()) or ["truncate"]),
    help="Perturbation type. Use `witness perturbations` to list.",
)
@click.option(
    "--param",
    "params_raw",
    multiple=True,
    metavar="KEY=VALUE",
    help="Perturbation parameter (repeatable). Values are parsed as JSON when possible.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=Path("perturbed.json"),
    show_default=True,
    help="Write the perturbed trace to this path.",
)
@click.option(
    "--no-rerun",
    is_flag=True,
    help="Do not actually re-run the agent; only write the perturbed input snapshot.",
)
def cmd_perturb(
    baseline: Path,
    ptype: str,
    params_raw: tuple[str, ...],
    output: Path,
    no_rerun: bool,
) -> None:
    """Apply a perturbation to a baseline trace and (by default) re-run the agent.

    The agent is dynamically imported from the trace's `entrypoint` field. If the
    trace has no entrypoint, or you don't want to re-run, pass --no-rerun and
    Witness will write a JSON snapshot of what *would* be fed to the agent.
    """
    base = load_trace(baseline)
    params = _parse_params(params_raw)
    perturbation = get_perturbation(ptype, **params)

    if no_rerun or not base.entrypoint:
        # Write a snapshot of the perturbed inputs, not a real perturbed trace.
        from witness.perturbations.base import ReplayContext

        ctx = ReplayContext.from_trace(base)
        ctx = perturbation.apply(ctx)
        snapshot: dict[str, Any] = {
            "perturbation": perturbation.record().model_dump(),
            "inputs": ctx.inputs,
            "messages": ctx.messages,
            "tools_available": ctx.tools_available,
            "model": ctx.model,
            "_note": (
                "no-rerun mode: this is a snapshot of what the agent WOULD see if re-run. "
                "Feed `inputs` back into your agent function to produce a perturbed trace."
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
        click.echo(f"wrote perturbed-input snapshot -> {output}")
        if not base.entrypoint:
            click.echo(
                "  (trace has no entrypoint; re-run was skipped automatically)",
                err=True,
            )
        return

    # Real re-run path.
    install_all()  # patch any importable SDKs
    try:
        perturbed = replay(base, perturbation)
    except Exception as e:
        click.secho(f"replay failed: {e}", fg="red", err=True)
        sys.exit(2)
    save_trace(perturbed, output)
    click.echo(f"wrote perturbed trace -> {output}")
    click.echo(
        f"  baseline: {len(base.decisions)} decisions, "
        f"perturbed: {len(perturbed.decisions)} decisions"
    )


# ---------------------------------------------------------------------------
# `witness inspect`
# ---------------------------------------------------------------------------


@cli.command("inspect")
@click.argument("trace_path", type=click.Path(exists=True, path_type=Path))
@click.option("--decisions", is_flag=True, help="Print the decision list.")
@click.option("--messages", is_flag=True, help="Print the message list.")
def cmd_inspect(trace_path: Path, decisions: bool, messages: bool) -> None:
    """Pretty-print key fields from a trace file."""
    t = load_trace(trace_path)
    click.echo(f"agent_name:       {t.agent_name}")
    click.echo(f"run_id:           {t.run_id}")
    click.echo(f"model:            {t.model}")
    click.echo(f"tools_available:  {t.tools_available}")
    click.echo(f"decisions:        {len(t.decisions)}")
    click.echo(f"messages:         {len(t.messages)}")
    click.echo(f"wall_time_ms:     {t.wall_time_ms}")
    click.echo(f"entrypoint:       {t.entrypoint}")
    if t.perturbation:
        click.echo(f"perturbation:     {t.perturbation.type} {t.perturbation.params}")
        click.echo(f"parent_run_id:    {t.parent_run_id}")
    if decisions:
        click.echo("\n--- decisions ---")
        for i, d in enumerate(t.decisions):
            click.echo(f"  {i:3d} [{d.step_id}] {d.type.value} duration={d.duration_ms}ms")
    if messages:
        click.echo("\n--- messages ---")
        for i, m in enumerate(t.messages):
            content_preview = (
                m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)
            )
            if len(content_preview) > 100:
                content_preview = content_preview[:97] + "..."
            click.echo(f"  {i:3d} {m.role.value:9s} {content_preview}")


# ---------------------------------------------------------------------------
# `witness perturbations`
# ---------------------------------------------------------------------------


@cli.command("perturbations")
def cmd_perturbations() -> None:
    """List registered perturbation types."""
    for name in list_perturbations():
        cls = PERTURBATION_REGISTRY[name]
        doc = (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else ""
        click.echo(f"  {name:20s}  {doc}")


# ---------------------------------------------------------------------------
# `witness fingerprint`
# ---------------------------------------------------------------------------


@cli.command("fingerprint")
@click.argument("baseline", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--perturbed",
    "perturbed_paths",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Existing perturbed trace JSON to include (repeatable). Use --run instead "
    "to generate perturbed traces on the fly.",
)
@click.option(
    "--run",
    "runs",
    multiple=True,
    metavar="TYPE[:k=v,...]",
    help=(
        "Generate a perturbed trace by re-running the agent. "
        "Format: 'truncate' or 'truncate:fraction=0.25'. Repeatable."
    ),
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("traces") / "fingerprint",
    show_default=True,
    help="Where to write any newly-generated perturbed traces.",
)
@click.option("--json", "as_json", is_flag=True, help="Print the fingerprint as JSON.")
def cmd_fingerprint(
    baseline: Path,
    perturbed_paths: tuple[Path, ...],
    runs: tuple[str, ...],
    output_dir: Path,
    as_json: bool,
) -> None:
    """Build a behavioral fingerprint from N perturbed runs of one baseline.

    Mix existing perturbed traces (`--perturbed`) and on-the-fly runs (`--run`).
    """
    base = load_trace(baseline)

    # 1. Generate any --run perturbations.
    generated: list[Path] = []
    if runs:
        install_all()
        output_dir.mkdir(parents=True, exist_ok=True)
        for spec in runs:
            ptype, params = _parse_run_spec(spec)
            perturbation = get_perturbation(ptype, **params)
            try:
                perturbed_trace = replay(base, perturbation)
            except Exception as e:
                click.secho(f"  [{spec}] replay failed: {e}", fg="red", err=True)
                continue
            out = output_dir / f"{perturbed_trace.run_id}.trace.json"
            save_trace(perturbed_trace, out)
            generated.append(out)
            click.secho(f"  [{spec}] -> {out.name}", err=True)

    all_paths = list(perturbed_paths) + generated
    if not all_paths:
        click.secho("no perturbed traces (need --perturbed and/or --run)", fg="red", err=True)
        sys.exit(2)
    perturbed_traces = [load_trace(p) for p in all_paths]
    fp = build_fingerprint(base, perturbed_traces)

    if as_json:
        click.echo(json.dumps(fp.summary(), indent=2, default=str))
        return

    color = sys.stdout.isatty()
    click.echo(_render_fingerprint(fp, color=color))


def _render_fingerprint(fp, *, color: bool) -> str:
    """Pretty terminal output for a fingerprint."""
    bold = "\033[1m" if color else ""
    reset = "\033[0m" if color else ""
    cyan = "\033[36m" if color else ""
    yellow = "\033[33m" if color else ""

    out = []
    out.append(f"{bold}=== witness fingerprint ==={reset}")
    out.append(f"baseline:  {fp.baseline_run_id}")
    out.append(f"runs:      {len(fp.runs)}")
    out.append("")
    out.append(f"{cyan}stability by decision type:{reset}")
    for dtype, score in sorted(fp.stability_by_decision_type().items()):
        bar = _stability_bar(score, width=20)
        out.append(f"  {dtype:14s} {bar} {score:.2f}")
    out.append("")
    fout = fp.final_output_stability()
    out.append(f"final output stability: {_stability_bar(fout)} {fout:.2f}")
    overall = fp.overall_stability()
    out.append(f"{yellow}overall stability:      {_stability_bar(overall)} {overall:.2f}{reset}")
    out.append("")
    out.append("per-run summary:")
    for r in fp.runs:
        params = " ".join(f"{k}={v}" for k, v in r.perturbation_params.items())
        delta = len(r.diff.perturbed.decisions) - len(r.diff.baseline.decisions)
        out.append(
            f"  {r.perturbation_type:20s} {params:30s}"
            f"  decisions {delta:+d}  "
            f"final={'CHANGED' if r.diff.final_output_changed else 'same'}"
        )
    return "\n".join(out)


def _stability_bar(score: float, width: int = 20) -> str:
    filled = int(round(score * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _parse_run_spec(spec: str) -> tuple[str, dict[str, Any]]:
    """Parse 'name' or 'name:k=v,k2=v2' into (name, params dict)."""
    if ":" not in spec:
        return spec, {}
    name, rest = spec.split(":", 1)
    params: dict[str, Any] = {}
    for kv in rest.split(","):
        if not kv.strip():
            continue
        if "=" not in kv:
            raise click.BadParameter(f"--run spec param must be k=v; got {kv!r}")
        k, v = kv.split("=", 1)
        try:
            params[k] = json.loads(v)
        except json.JSONDecodeError:
            params[k] = v
    return name, params


# ---------------------------------------------------------------------------
# `witness schema`
# ---------------------------------------------------------------------------


@cli.command("schema")
@click.option(
    "--regenerate",
    is_flag=True,
    help="Regenerate the on-disk trace_v1.json file from the live pydantic models.",
)
@click.option("--path", is_flag=True, help="Print the path to the on-disk schema file.")
def cmd_schema(regenerate: bool, path: bool) -> None:
    """Print or regenerate the trace JSON Schema."""
    if regenerate:
        p = write_schema_file()
        click.echo(f"wrote {p}")
        return
    if path:
        click.echo(str(schema_path()))
        return
    # Default: print the live schema (handy for piping into a validator).
    click.echo(json.dumps(generate_schema_dict(), indent=2))


# ---------------------------------------------------------------------------
# Param parsing
# ---------------------------------------------------------------------------


def _parse_params(raw: tuple[str, ...]) -> dict[str, Any]:
    """Parse `KEY=VALUE` pairs. Values try JSON first, fall back to string."""
    out: dict[str, Any] = {}
    for kv in raw:
        if "=" not in kv:
            raise click.BadParameter(f"--param expects KEY=VALUE; got {kv!r}")
        key, value = kv.split("=", 1)
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def main() -> None:
    """Entry point for the `witness` console script."""
    cli(prog_name="witness")


if __name__ == "__main__":
    main()
