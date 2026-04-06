# Wire Phoenix Tracing Into The OpenAI Agents Runtime

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

`~/.agents/PLANS.md` governs this document and must be followed as implementation continues.

## Purpose / Big Picture

After this change, the `xs2n` CLIs should emit OpenAI Agents SDK traces to the local Phoenix instance without requiring manual instrumentation code in every command. A user should be able to run the existing cluster builder CLIs, open Phoenix on `http://localhost:6006`, and see the agent run appear there.

The repository currently disables tracing for every cluster-builder run, so Phoenix cannot show anything even when the local collector is available. This plan adds one shared tracing bootstrap, keeps an explicit escape hatch to disable tracing, and documents the runtime contract.

## Progress

- [x] (2026-04-04 23:23Z) Confirmed the current runtime disables tracing per run in `src/xs2n/agents/cluster_builder_agent.py`.
- [x] (2026-04-04 23:24Z) Verified the official Phoenix integration path uses `phoenix.otel.register(auto_instrument=True)` with `openinference-instrumentation-openai-agents`.
- [x] (2026-04-04 23:27Z) Added failing tests for the shared tracing bootstrap and updated the cluster-builder agent contract to expect tracing to remain enabled.
- [x] (2026-04-04 23:31Z) Implemented `src/xs2n/llm/tracing.py`, enabled it from the cluster-builder agent builder, and removed the per-run tracing disable flag.
- [x] (2026-04-04 23:34Z) Added Phoenix/OpenInference dependencies, refreshed `uv.lock`, and updated `README.md` plus `docs/codex/autolearning.md`.
- [x] (2026-04-04 23:36Z) Verified the focused test slice with `uv run pytest tests/test_tracing.py tests/test_cluster_builder_agent.py tests/test_openai_client.py -q`, confirmed the tracing bootstrap returns `True`, and smoke-checked `uv run xs2n-cluster-builder --help`.

## Surprises & Discoveries

- Observation: the OpenAI Agents SDK package exposes a custom tracing processor system, but its built-in backend exporter targets the OpenAI ingest format instead of OTLP.
  Evidence: `.venv/lib/python3.12/site-packages/agents/tracing/processors.py` posts to `https://api.openai.com/v1/traces/ingest` with `OpenAI-Beta: traces=v1`.

- Observation: relying on the Phoenix environment variable alone let the runtime normalize to a different collector route than the one we wanted to document.
  Evidence: `configure_phoenix_tracing()` printed a collector route under `4317` until the code passed `endpoint=...` and `protocol="http/protobuf"` directly to `phoenix.otel.register(...)`.

## Decision Log

- Decision: use Phoenix's official `register(auto_instrument=True)` bootstrap instead of writing a custom OTLP bridge.
  Rationale: Phoenix already documents this as the supported OpenAI Agents SDK path, so the repository should prefer the official integration over custom transport code.
  Date/Author: 2026-04-04 / Codex

- Decision: keep tracing setup in one shared LLM-focused module instead of CLI-specific wrappers.
  Rationale: the repo has one real agent runtime today, but the tracing policy belongs to shared model/runtime wiring and should stay reusable.
  Date/Author: 2026-04-04 / Codex

## Outcomes & Retrospective

The repo now has one shared Phoenix tracing bootstrap in `src/xs2n/llm/tracing.py`, and the cluster-builder runtime calls it once before constructing the agent. That keeps tracing enabled by default for real runs, gives local Phoenix a stable HTTP OTLP target, and still provides `XS2N_DISABLE_TRACING=1` as the explicit off switch.

The focused test slice is green and the CLI surface still loads. The main remaining limitation is that I did not run a live model-backed agent call in this turn, so the final proof of a trace appearing in Phoenix is still an operator-visible runtime check rather than an automated test in the repo.

## Context and Orientation

In this repository, the live model-driven loop lives in `src/xs2n/agents/cluster_builder_agent.py`. The CLIs in `src/xs2n/cli/` both build that agent and then let it process a persisted tweet queue through local tools. Shared OpenAI/Codex auth and model wiring lives in `src/xs2n/llm/`.

“Phoenix tracing” here means OpenTelemetry-style trace data that Phoenix can display. The official Phoenix/OpenAI Agents integration uses the Phoenix Python package plus the OpenInference OpenAI Agents instrumentation package. The bootstrap call is `phoenix.otel.register(...)`, and with `auto_instrument=True` it instruments installed libraries automatically.

## Plan of Work

Start from tests so the desired tracing contract is explicit before changing runtime code. Add one focused test module for the shared tracing bootstrap and update the existing cluster-builder agent test to expect tracing to remain enabled unless explicitly disabled by environment.

Then add a new shared module under `src/xs2n/llm/` that configures Phoenix once per process. It should set a sensible local default collector endpoint, respect an explicit disable environment variable, and call the official Phoenix bootstrap lazily so imports stay honest and failures are easy to understand.

Finally, update the main README install/runtime notes and append a new autolearning note in `docs/codex/autolearning.md` so future work keeps Phoenix tracing initialization centralized.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Write the failing tests in `tests/test_tracing.py` and `tests/test_cluster_builder_agent.py`.
2. Run the focused test command and confirm the new tests fail for the missing bootstrap behavior.
3. Implement the tracing bootstrap in `src/xs2n/llm/tracing.py` and enable it from `src/xs2n/agents/cluster_builder_agent.py`.
4. Add the Phoenix/OpenInference dependencies to `pyproject.toml`, refresh `uv.lock`, and update docs in `README.md` and `docs/codex/autolearning.md`.
5. Re-run the focused tests, then run one small CLI/help verification pass.

## Validation and Acceptance

Acceptance is behavioral. After installing dependencies and running one cluster-builder command, Phoenix should be able to receive traces from the agent runtime. In tests, the cluster-builder run config must no longer force `tracing_disabled=True`, and the shared tracing bootstrap must call Phoenix registration with `auto_instrument=True` while setting a default local collector endpoint.

## Idempotence and Recovery

The tracing bootstrap must be safe to call more than once in a process. If Phoenix tracing needs to be disabled locally or in CI, the implementation should honor a dedicated environment variable so the runtime can fall back without code edits.

## Artifacts and Notes

Target files for this slice:

- `src/xs2n/llm/tracing.py`
- `src/xs2n/agents/cluster_builder_agent.py`
- `tests/test_tracing.py`
- `tests/test_cluster_builder_agent.py`
- `README.md`
- `docs/codex/autolearning.md`
