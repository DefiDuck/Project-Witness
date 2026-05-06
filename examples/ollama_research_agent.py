"""End-to-end Witness demo using a local Ollama model.

Witness has no Ollama-specific code — Ollama exposes an OpenAI-compatible API at
``http://localhost:11434/v1``, so we point the ``openai`` SDK at it and the
OpenAI adapter records everything automatically.

Requires
--------
    pip install "witness[openai]"
    ollama serve                        # if not already running
    ollama pull llama3.2:3b             # or any tool-capable model

Usage
-----
    # Quick demo (mock summary doc):
    python -m examples.ollama_research_agent --do-replay

    # Real doc:
    python -m examples.ollama_research_agent --doc paper.txt --do-replay

    # Different model:
    python -m examples.ollama_research_agent --model qwen2.5:3b --do-replay

The captured ``baseline.json`` and ``perturbed.json`` are real Ollama traces —
``witness diff`` / ``witness fingerprint`` work on them just like any other.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import witness
from witness.adapters import install_all


_SAMPLE_DOC = """\
Constitutional AI is a method for training AI assistants to be helpful, harmless, and honest.

The approach uses a set of principles, called a constitution, to guide the model's behavior.
Rather than relying solely on human feedback, the model critiques and revises its own outputs.

This technique reduces the burden on human annotators while still producing aligned behavior.
The result is a model that explains its reasoning and refuses harmful requests transparently.
"""


def _ollama_client(base_url: str):
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "openai SDK is not installed. Run: pip install 'witness[openai]'"
        ) from e
    # Ollama doesn't check the API key, but the SDK requires one.
    return OpenAI(base_url=base_url, api_key="ollama")


@witness.observe(name="research_agent_ollama", output_path="baseline.json")
def research(
    doc: str,
    *,
    model: str = "llama3.2:3b",
    base_url: str = "http://localhost:11434/v1",
) -> str:
    """Summarize ``doc`` via a local Ollama model.

    The OpenAI adapter (auto-installed below) records each ``chat.completions.create``
    call as a ``model_call`` decision, plus any ``tool_call`` decisions if the
    model emits tool_use blocks.
    """
    install_all()  # patches the openai SDK
    client = _ollama_client(base_url)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a careful summarizer. Output a 2-3 sentence summary of the "
                "document the user provides. Be terse and stick to the facts."
            ),
        },
        {
            "role": "user",
            "content": f"Summarize this document:\n\n<doc>\n{doc}\n</doc>",
        },
    ]

    resp = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=256,
        temperature=0.0,  # determinism-ish; helpful for diffing
    )
    return (resp.choices[0].message.content or "").strip()


def _load_doc(arg: str | None) -> str:
    if arg is None:
        return _SAMPLE_DOC
    p = Path(arg)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return arg  # treat as inline text


def main() -> int:
    ap = argparse.ArgumentParser(description="Witness demo against a local Ollama model.")
    ap.add_argument("--doc", help="Path to a text doc, or inline text. Default: built-in sample.")
    ap.add_argument("--model", default="llama3.2:3b", help="Ollama model name.")
    ap.add_argument(
        "--base-url",
        default="http://localhost:11434/v1",
        help="OpenAI-compatible Ollama endpoint.",
    )
    ap.add_argument(
        "--do-replay",
        action="store_true",
        help="Capture, then run the truncate perturbation, then diff.",
    )
    ap.add_argument(
        "--fraction", type=float, default=0.5, help="Truncation fraction (0..1)."
    )
    ap.add_argument(
        "--perturbation",
        choices=["truncate", "prompt_injection"],
        default="truncate",
        help="Which perturbation to apply when --do-replay is set.",
    )
    args = ap.parse_args()

    doc = _load_doc(args.doc)
    print(f"[ollama] capturing baseline (doc length={len(doc)}, model={args.model})...")
    final = research(doc=doc, model=args.model, base_url=args.base_url)
    print(f"[ollama] baseline output: {final!r}")
    print("[ollama] wrote baseline.json")

    if args.do_replay:
        from witness.diff.format import format_text

        if args.perturbation == "truncate":
            pert = witness.Truncate(fraction=args.fraction)
        else:
            pert = witness.PromptInjection()

        print(f"\n[ollama] running {pert.name} ({pert.record().summary})...")
        baseline = witness.load_trace("baseline.json")
        perturbed = witness.replay(
            baseline,
            pert,
            agent_fn=research,
            output_path="perturbed.json",
        )
        print(f"[ollama] perturbed output: {perturbed.final_output!r}")
        print()
        d = witness.diff(baseline, perturbed)
        print(format_text(d, color=sys.stdout.isatty()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
