# xs2n Autolearning Framework

## Current Surface

This branch intentionally reduced the repository to a minimal two-script surface:

- `scripts/codex_auth.py`
- `scripts/run_agentic_pipeline.py`

## Branch Note (2026-03-21)

- The extraction branch is deliberately not backward-compatible with the old wider CLI/UI product surface.
- Keeping only one final artifact on disk made the runtime contract much easier to reason about.
- The useful reusable code from the older repo was smaller than the full product shell:
  - Codex credential resolution
  - one thin structured-output model wrapper
  - two semantic pipeline steps
- When a branch is explicitly meant to become a minimal base, it is cheaper to prune aggressively than to keep "temporary compatibility" layers that nobody wants.

## Branch Note (2026-03-22)

- The minimal migration path to the OpenAI Agents SDK is to swap the `LLM` transport layer first and leave the digest pipeline orchestration readable and linear.
- The existing credential resolver still matters after the SDK migration because it provides the custom token and `base_url` needed for Codex-authenticated runs.
- Disabling tracing per run keeps the SDK focused on model execution and avoids leaking this minimal CLI into tracing-specific configuration work too early.
- Issue grouping became more reliable once the selection step owned the canonical issue slug and the write step stopped being able to silently fork the story.

## Branch Note (2026-03-25)

- The digest runtime sits under `src/xs2n/agents`, but shared infrastructure such as `credentials.py` stays at the package root when it is not specific to one agentic workflow.
- A flat `agents/` package is easier to scan than an extra `digest/` nesting for a repository that currently ships only one digest pipeline.

## Branch Note (2026-03-26)

- If `Thread` is the application's real domain model, it should be named `Thread` at the boundary where data enters the system, not `ThreadInput` deeper in the pipeline.
- `twitter.py` should return domain `Thread` objects directly; the digest pipeline should consume those objects instead of owning a private input-shaping layer.
- The public CLI feels simpler when it owns the fetch-first orchestration and the pipeline stays focused on digest semantics.
- `ntscraper`'s `since` filter expects a `YYYY-MM-DD` string, so passing a raw `datetime` through the fetch layer is the wrong contract.

## Branch Note (2026-03-28)

- A Codex OAuth facade for LangChain works best as an explicit additive package instead of mutating the existing digest-only LLM wrapper.
- The local `langchain-openai` version in this repo still routes `ChatOpenAI` through `chat.completions`, so a Codex-compatible facade has to replace the transport path, not just pass a different `base_url`.
- The Codex backend currently expects a stricter Responses contract than generic wrappers send by default: top-level `instructions`, list-based `input`, `store=False`, and `stream=True`.
- Injecting a small default instruction when no `SystemMessage` is present closes a real compatibility gap for `with_structured_output(...)` callers that otherwise send no top-level instructions at all.

## Branch Note (2026-03-28, later)

- For the first cluster-builder prototype, a tweet list should behave like a todo queue with explicit status transitions instead of as a passive batch input.
- Allowing `deferred` tweets inside the same run is a better fit for the clustering task than forcing immediate assignment or waiting for a future scheduled run.
- LangFuse should be integrated through the standard LangChain callback handler first; manual custom tracing would add complexity before the queue and cluster contracts are proven.
- The domain boundary should stay tool-first: the agent can reason freely, but queue state and cluster state should only change through explicit structured tools.
- DeepAgents bring automatic built-in tools, so the first safe strategy is to constrain domain work through prompt and tests rather than prematurely rewriting the runtime to remove those tools.
