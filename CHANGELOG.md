# Changelog

## v0.1.0 — initial release

The MVP from `BUILD.md` (capture / perturb / diff), plus everything in the
"stretch" list except the web UI and trace-import integrations.

### Capture
- `@witness.observe()` decorator — sync + async, contextvar-based, bare and parameterized forms
- `witness.record_decision()` for manual instrumentation
- Anthropic SDK adapter — auto-records `messages.create` calls (sync + async)
- OpenAI SDK adapter — auto-records `chat.completions.create` calls (sync + async)
- Stable JSON trace schema (`trace_v1`) with forward-compat `extra="allow"`
  on every model
- Schema published as JSON Schema at `witness/schema/trace_v1.json`

### Perturb
- `Truncate(fraction=...)` — drop trailing N% of context
- `PromptInjection(text=...)` — append a hostile instruction
- `ModelSwap(target=...)` — replace the model identifier
- `ToolRemoval(tool=...)` — remove a tool from `tools_available`
- `witness.replay_context()` — agents can honor model/tool overrides during replay
- `witness.replay()` — programmatic counterfactual replay with auto-save suppression

### Diff
- LCS-based decision alignment with `same` / `input_changed` / `output_changed` / `both_changed` / `added` / `removed` / `type_changed` classification
- Color-coded terminal renderer
- `witness.diff.fingerprint()` — N-perturbation behavioral signature
  with stability scores per decision type and an overall (geometric-mean) score

### CLI
- `witness diff baseline.json perturbed.json` (color or `--json`, `-v` for verbose)
- `witness perturb baseline.json --type ... --param k=v -o ...` (with optional `--no-rerun` snapshot mode)
- `witness inspect <trace>` — pretty summary of a trace
- `witness perturbations` — list registered perturbation types
- `witness fingerprint baseline.json --run truncate:fraction=0.25 --run prompt_injection`
- `witness schema [--regenerate|--path]`

### Tests
- 96 unit tests covering schema, store, capture, perturbations, diff, replay, fingerprint, schema export, CLI, and end-to-end demo flow
- Integration test suite (`tests/integration/`) gated on `RUN_INTEGRATION=1`
  with real Anthropic API call

### Docs
- README with the gap framing, CLI flow, perturbation table, JSON Schema location
- This changelog
- LICENSE (MIT)
