# xs2n Autolearning Framework

## Current Surface

This branch currently exposes one runtime command plus the auth helper it depends on:

- `xs2n-auth`
- `xs2n`

## Branch Note (2026-04-03, flat root surface)

- Root folders should reflect the real jobs directly: `agents/`, `tools/`, `prompts/`, `llm/`, `schemas/`, and `cli/`.
- Only true model-driven loops belong under `agents/`. Fetchers, queue builders, and persisted state helpers belong under `tools/`.
- If the runtime is just “fetch posts, build queue, submit to one agent”, separate feature packages like `sources/` and `cluster_builder/` add more ceremony than clarity.
- Shared contracts should stay neutral under `schemas/`, and prompt assets should live in one dedicated `prompts/` folder.
- The safest large prune is: move tests first, flip imports to the new boundary, prove the new modules with focused tests, then delete the redundant paths.
- Package-native CLI entrypoints keep the repo surface smaller and more honest than standalone launcher files.

## Branch Note (2026-04-05, Codex-first auth precedence)

- When both Codex auth material and `OPENAI_API_KEY` exist, prefer Codex auth first and keep the API key only as an emergency fallback.
- Keep that precedence aligned across shared credential helpers and concrete OpenAI client builders so different call paths do not silently disagree.

## Branch Note (2026-04-05, Phoenix tracing bootstrap)

- Keep Phoenix tracing initialization in one shared runtime module instead of spreading `phoenix.otel.register(...)` across CLIs or agent files.
- The agent runtime should call that shared bootstrap once, keep a dedicated `XS2N_DISABLE_TRACING` escape hatch, and default the local collector endpoint to the self-hosted Phoenix instance when the environment is silent.

## Branch Note (2026-04-05, tool payload discipline)

- Keep list-style inspection tools lightweight by default. Return stable identifiers first and let the model opt into extra fields through an explicit `fields` argument when it really needs more context.
- Keep mutation tools terse. Return short acknowledgement messages with the key identifier instead of mirroring full state that read tools can fetch more accurately on demand.
- If a create mutation accepts initial membership like `tweet_ids`, persist that membership in the same write path and mention it in the acknowledgement so the tool response matches stored state.

## Branch Note (2026-04-05, single runner plus scaffold)

- `src/xs2n/cli/run.py` is now the only active orchestration file. It owns the fetch-versus-reuse branch directly so the runtime order stays readable top-to-bottom.
- `src/xs2n/agents/agents_sdk_scaffold.py` is intentionally a scaffold, not a finished domain runtime. It proves Agents SDK wiring, ChatGPT/Codex auth reuse, and one minimal queue-preview tool.
- The old cluster-builder runtime was removed instead of being kept around as misleading architecture while the real agentic redesign is still pending.
