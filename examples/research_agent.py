"""End-to-end Witness demo.

Captures a baseline run of a small research agent that summarizes a document,
then perturbs and diffs.

Two modes
---------
- ``--mock``  (default)
    Deterministic. No network. Uses a fake LLM that simulates tool calls based
    on the document length. Perfect for the README demo and CI.

- ``--real``
    Calls the Anthropic API. Requires ``ANTHROPIC_API_KEY`` and the
    ``anthropic`` extra installed (`pip install "witness[anthropic]"`).

Usage
-----
    # capture baseline
    python examples/research_agent.py --doc anthropic_paper.txt

    # then in shell:
    witness perturb baseline.json --type truncate --param fraction=0.5 -o perturbed.json
    witness diff baseline.json perturbed.json

    # or all in Python:
    python examples/research_agent.py --doc anthropic_paper.txt --do-replay
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import witness
from witness.adapters import install_all
from witness.core.schema import DecisionType


# ---------------------------------------------------------------------------
# Mock LLM — deterministic, used by default and by tests
# ---------------------------------------------------------------------------


def _mock_summarize(doc: str) -> str:
    """Deterministic 'summary': first sentence of each paragraph, capped at 3."""
    paras = [p.strip() for p in doc.split("\n\n") if p.strip()]
    sentences = []
    for p in paras[:3]:
        sentence = p.split(".")[0].strip()
        if sentence:
            sentences.append(sentence + ".")
    if not sentences:
        return "I don't have enough context to summarize."
    return " ".join(sentences)


def _mock_search(query: str, doc: str) -> list[dict[str, str]]:
    """Pretend search: returns the first 2 paragraphs that contain the query word."""
    q = query.lower().strip().split()[0] if query.strip() else ""
    if not q:
        return []
    paras = [p.strip() for p in doc.split("\n\n") if p.strip()]
    hits = [{"para": p[:120]} for p in paras if q in p.lower()][:2]
    return hits


# ---------------------------------------------------------------------------
# Mock agent loop. Records the same kinds of decisions a real adapter would.
# ---------------------------------------------------------------------------


def _mock_agent_loop(doc: str) -> str:
    """Simulates: model_call -> tool_call(search) -> tool_result -> tool_call(read) ->
    tool_result -> model_call -> final_output.

    Witness records these via record_decision(), so the resulting trace looks like
    a real instrumented run.
    """
    # Round 1: model decides to call search.
    witness.record_decision(
        DecisionType.MODEL_CALL,
        input={"model": "mock-claude", "prompt": "Summarize this document"},
        output={"text": "I'll search the document first."},
        duration_ms=12,
        metadata={"sdk": "mock"},
    )
    witness.record_decision(
        DecisionType.TOOL_CALL,
        input={"name": "search", "args": {"query": "main argument"}},
        output={},
        duration_ms=1,
        metadata={"sdk": "mock"},
    )
    hits = _mock_search("main argument", doc)
    witness.record_decision(
        DecisionType.TOOL_RESULT,
        input={"name": "search"},
        output={"hits": hits},
        duration_ms=2,
        metadata={"sdk": "mock"},
    )

    # Round 2: model decides to read more if doc is long enough.
    if len(doc) > 200:
        witness.record_decision(
            DecisionType.TOOL_CALL,
            input={"name": "read_document", "args": {"start": 0, "len": min(500, len(doc))}},
            output={},
            duration_ms=1,
            metadata={"sdk": "mock"},
        )
        witness.record_decision(
            DecisionType.TOOL_RESULT,
            input={"name": "read_document"},
            output={"text": doc[: min(500, len(doc))]},
            duration_ms=2,
            metadata={"sdk": "mock"},
        )

    # Final synthesis.
    witness.record_decision(
        DecisionType.MODEL_CALL,
        input={"model": "mock-claude", "prompt": "Synthesize"},
        output={"text": _mock_summarize(doc)},
        duration_ms=15,
        metadata={"sdk": "mock"},
    )
    final = _mock_summarize(doc)
    witness.record_decision(
        DecisionType.FINAL_OUTPUT,
        input={},
        output={"text": final},
        metadata={"sdk": "mock"},
    )
    return final


# ---------------------------------------------------------------------------
# Real Anthropic agent. Uses the SDK; the adapter records automatically.
# ---------------------------------------------------------------------------


def _real_agent_loop(doc: str) -> str:
    install_all()  # patch the Anthropic SDK
    import anthropic  # type: ignore

    client = anthropic.Anthropic()
    tools = [
        {
            "name": "search",
            "description": "Search the document for a query.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    ]
    messages = [
        {
            "role": "user",
            "content": (
                "Summarize this document in 2-3 sentences. Use the `search` tool "
                f"if you need to find specific passages.\n\n<doc>\n{doc}\n</doc>"
            ),
        }
    ]
    final_text = ""
    for _ in range(4):  # safety cap
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            tools=tools,
            messages=messages,  # type: ignore[arg-type]
        )
        # Walk content blocks for tool_use; if any, run the tool and feed result back.
        tool_uses = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                tool_uses.append(block)
            elif getattr(block, "type", None) == "text":
                final_text = getattr(block, "text", "")
        if not tool_uses:
            break
        # Append the assistant message and the tool results to the conversation.
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for tu in tool_uses:
            if tu.name == "search":
                hits = _mock_search(tu.input.get("query", ""), doc)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": str(hits)}
                )
                witness.record_decision(
                    DecisionType.TOOL_RESULT,
                    input={"name": "search", "tool_use_id": tu.id},
                    output={"hits": hits},
                )
        messages.append({"role": "user", "content": tool_results})
    return final_text


# ---------------------------------------------------------------------------
# The @observe-wrapped entrypoint
# ---------------------------------------------------------------------------


@witness.observe(name="research_agent", output_path="baseline.json")
def research(doc: str, *, mode: str = "mock") -> str:
    if mode == "real":
        return _real_agent_loop(doc)
    return _mock_agent_loop(doc)


# ---------------------------------------------------------------------------
# Demo CLI
# ---------------------------------------------------------------------------


_SAMPLE_DOC = """\
Constitutional AI is a method for training AI assistants to be helpful, harmless, and honest.

The approach uses a set of principles, called a constitution, to guide the model's behavior.
Rather than relying solely on human feedback, the model critiques and revises its own outputs.

This technique reduces the burden on human annotators while still producing aligned behavior.
The result is a model that explains its reasoning and refuses harmful requests transparently.
"""


def _load_doc(doc_arg: str | None) -> str:
    if doc_arg is None:
        return _SAMPLE_DOC
    p = Path(doc_arg)
    if p.exists():
        return p.read_text(encoding="utf-8")
    # Treat as inline text if it doesn't look like a path.
    return doc_arg


def main() -> int:
    ap = argparse.ArgumentParser(description="Witness end-to-end demo: research agent.")
    ap.add_argument(
        "--doc",
        help="Path to a text doc to summarize (or inline text). Defaults to a built-in sample.",
    )
    ap.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="mock = deterministic, no network. real = uses Anthropic API.",
    )
    ap.add_argument(
        "--do-replay",
        action="store_true",
        help="After capturing baseline, also run the truncate perturbation and print the diff.",
    )
    ap.add_argument(
        "--fraction",
        type=float,
        default=0.5,
        help="Truncation fraction for the replay (default 0.5).",
    )
    args = ap.parse_args()

    doc = _load_doc(args.doc)
    print(f"[witness demo] capturing baseline (doc length={len(doc)})...")
    final = research(doc=doc, mode=args.mode)
    print(f"[witness demo] baseline final output: {final!r}")

    baseline_path = Path("baseline.json").resolve()
    print(f"[witness demo] wrote {baseline_path}")

    if args.do_replay:
        from witness.diff.format import format_text

        print(f"\n[witness demo] running truncate(fraction={args.fraction}) perturbation...")
        baseline_trace = witness.load_trace(baseline_path)
        perturbed = witness.replay(
            baseline_trace,
            witness.Truncate(fraction=args.fraction),
            agent_fn=research,
            output_path="perturbed.json",
        )
        print(f"[witness demo] wrote perturbed.json (run_id={perturbed.run_id})")
        print()
        d = witness.diff(baseline_trace, perturbed)
        print(format_text(d, color=sys.stdout.isatty()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
