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
