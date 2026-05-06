# Witness

[![tests](https://github.com/DefiDuck/Project-Witness/actions/workflows/tests.yml/badge.svg)](https://github.com/DefiDuck/Project-Witness/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> Capture, perturb, and diff LLM agent decisions. Make agent behavior under stress legible.

```
+---------+      +-----------+      +--------+
| Capture | ---> | Perturb   | ---> |  Diff  |
+---------+      +-----------+      +--------+
   trace          counterfactual     behavioral
   (JSON)         run (JSON)          delta
```

## The gap

| Tool                            | Captures traces? | Counterfactual replay? | Behavioral diff? |
|---------------------------------|------------------|-----------------------|------------------|
| LangSmith / Helicone / Arize    | yes              | no                    | no               |
| Garak / Promptfoo / DeepEval    | no               | partial (red-team)    | no               |
| LangGraph / CrewAI              | partial          | no                    | no               |
| **Witness**                     | **yes**          | **yes**               | **yes**          |

Today engineers ship agents and find out about edge cases in production. Witness lets you find them in dev.

## Install

```bash
pip install witness
# or with adapters
pip install "witness[anthropic]"
pip install "witness[openai]"
```

## 60-second demo

```python
import witness

@witness.observe(name="research_agent")
def research_agent(doc: str) -> str:
    # any agent code: Anthropic SDK, OpenAI SDK, custom loop, etc.
    ...

baseline = research_agent(doc="paper.pdf")          # captures trace
perturbed = witness.replay(                          # counterfactual
    baseline,
    perturbation=witness.perturbations.Truncate(fraction=0.5),
)
print(witness.diff(baseline, perturbed))             # behavioral diff
```

Or from the CLI:

```bash
# capture
python -m examples.research_agent --doc paper.txt              # writes baseline.json

# perturb (rerun the agent under truncation)
witness perturb baseline.json --type truncate                  # writes perturbed.json
#   --param fraction=0.5 by default; pass `--type truncate --param fraction=0.75` for more
#   pass `--no-rerun` to skip re-execution and write a perturbed-input snapshot only

# diff
witness diff baseline.json perturbed.json                      # color-coded diff
witness diff baseline.json perturbed.json --json               # structured JSON
```

> Invoke the example as a module (`python -m examples.research_agent`) so the
> trace's `entrypoint` is importable when `witness perturb` re-runs from a
> fresh process. Plain `python examples/research_agent.py` still captures
> traces fine but produces an unimportable `__main__:research` entrypoint.

## What you get

A trace JSON with a stable schema (`trace_v1`):

```json
{
  "schema_version": "1.0",
  "run_id": "01JABC...",
  "agent_name": "research_agent",
  "model": "claude-opus-4-7",
  "tools_available": ["search", "read_file"],
  "messages": [...],
  "decisions": [
    {"step_id": "s1", "type": "model_call", "input": {...}, "output": {...}},
    {"step_id": "s2", "type": "tool_call",  "input": {...}, "output": {...}}
  ],
  "final_output": "...",
  "wall_time_ms": 2840
}
```

A behavioral diff like:

```
=== witness diff ===
baseline:  research_agent  (8 decisions, 2.84s)
perturbed: research_agent  (5 decisions, 1.91s)  perturbation=truncate fraction=0.5

decisions: 8 -> 5  (-3)
  [s3] tool_call search REMOVED
  [s4] tool_call read_file REMOVED
  [s5] tool_call read_file REMOVED
tool calls: {search: 2, read_file: 2} -> {search: 1, read_file: 0}
final output: CHANGED
  - "Anthropic's Constitutional AI paper introduces..."
  + "I don't have enough context to summarize."
```

## Architecture

Three layers, independently usable:

```
witness/
  core/              # schema, capture decorator, JSON store
  perturbations/     # truncate, (more later)
  diff/              # behavioral diff logic
  adapters/          # auto-instrument Anthropic / OpenAI SDK calls
  cli.py             # `witness diff`, `witness perturb`
```

Capture only? `import witness; @witness.observe()`. No perturbations imported.
Diff only? `from witness.diff import diff_traces`. No SDKs imported.

## What Witness is *not*

- A new agent framework (it wraps yours)
- A trace storage backend (plain JSON, SQLite at most)
- A SaaS (library only)
- An LLM-judge (mechanical diff only — semantic comparison comes later)

## Behavioral fingerprint

```bash
witness fingerprint baseline.json \
    --run truncate:fraction=0.25 \
    --run truncate:fraction=0.5 \
    --run truncate:fraction=0.75 \
    --run prompt_injection
```

```
=== witness fingerprint ===
baseline:  run_c198b5f08e28
runs:      4

stability by decision type:
  final_output   [#####---------------] 0.25
  model_call     [#####---------------] 0.25
  tool_call      [--------------------] 0.00
  tool_result    [--------------------] 0.00

final output stability: [#####---------------] 0.25
overall stability:      [--------------------] 0.00
```

Tells you which decision types are weak under stress.

## Local LLM (Ollama)

Witness has no Ollama-specific code — Ollama exposes an OpenAI-compatible API,
so we point the `openai` SDK at it and the OpenAI adapter records everything.

```bash
pip install "witness[openai]"
ollama pull llama3.2:3b                                         # any tool-capable model
ollama serve                                                    # if not running

python -m examples.ollama_research_agent --do-replay            # capture + perturb + diff
python -m examples.ollama_research_agent --model qwen2.5:3b --perturbation prompt_injection --do-replay
```

The captured `baseline.json` is a real LLM trace — `witness diff`,
`witness fingerprint`, and every other tool work on it identically.

## Built-in perturbations

| Name              | What it does                                                 |
|-------------------|--------------------------------------------------------------|
| `truncate`        | Drop the trailing N% of context (default 50%)                |
| `prompt_injection`| Append a hostile instruction to doc-like inputs              |
| `model_swap`      | Replace the model identifier the agent will use              |
| `tool_removal`    | Remove a named tool (or all tools)                           |

`model_swap` and `tool_removal` only change behavior if your agent reads
`witness.replay_context()` during the run — Witness records the perturbation
either way, so a fingerprint can detect "this agent ignores model swaps" as
a stability fact.

```python
@witness.observe()
def my_agent(prompt: str) -> str:
    ctx = witness.replay_context()
    model = ctx.model if ctx else "claude-opus-4-7"
    tools = ctx.tools_available if ctx else DEFAULT_TOOLS
    ...
```

## JSON Schema

The on-disk trace format is published as
[`witness/schema/trace_v1.json`](witness/schema/trace_v1.json). Regenerate
from the live pydantic models with `witness schema --regenerate`, or
`witness schema` to print it on stdout.

## Status

v0.1 — MVP shipped. Single-process Python. Anthropic + OpenAI adapters.

Done:

- [x] `@observe` capture decorator (sync + async, contextvar-based)
- [x] Stable JSON trace schema, published as JSON Schema (`trace_v1.json`)
- [x] Perturbations: `truncate`, `prompt_injection`, `model_swap`, `tool_removal`
- [x] `replay()` (programmatic + CLI rerun via `entrypoint`)
- [x] Behavioral diff with LCS alignment (`witness diff`)
- [x] `witness fingerprint` — N-perturbation stability vector
- [x] CLI: `diff`, `perturb`, `inspect`, `perturbations`, `fingerprint`, `schema`

Roadmap:

- [ ] Temperature / role-inversion perturbations
- [ ] LangSmith / Helicone trace import/export
- [ ] Optional Streamlit UI for trace inspection
- [ ] LangGraph / CrewAI adapters

## License

MIT.
