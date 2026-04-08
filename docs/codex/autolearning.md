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

## Branch Note (2026-04-08, compact routing contracts)

- If a model step only needs to classify pre-shaped items, keep the transport local and compact: use short local ids, one fixed row grammar, and a strict parser that validates completeness and uniqueness before any downstream step trusts the output.
- When a new agent needs richer tweet context than the current queue carries, widen the persisted queue contract additively with neutral fields such as `quote_text`, `image_description`, and `url_hint` instead of hiding the missing data behind prompt magic.
- Keep new agent paths observable from the CLI early, even if they are incremental. A thin `--route-text` mode that prints the strict grouped output is more truthful and testable than shipping only internal helper modules.

## Branch Note (2026-04-08, honest prompt-specific entrypoints)

- If a prompt-specific path only differs by fixed prompt text and fixed model settings, prefer one exported domain function that builds the shared model wrapper locally over adding a dedicated subclass plus builder.
- Keep the public entrypoint named after the real job, such as `route_tweet_rows(...)`, so the call site shows the domain action directly instead of forcing readers through one-off agent types.

## Branch Note (2026-04-09, feature-local helper ownership)

- When helper code only exists to support one prompt-specific path, keep it inside that feature package instead of under a generic `utils/` module. The file path should tell the truth about ownership.
- Split a feature into `main.py` plus one small `utils.py` before inventing more file layers. Move to finer-grained files only after the helper module stops being easy to scan.

## Branch Note (2026-04-09, issue organizer output discipline)

- When a model step groups already-filtered tweets into issues, keep the first iteration stateless and one-shot: filtered rows in, one validated JSON object out.
- Put the grouping contract in a neutral schema module and make the parser enforce full tweet coverage, uniqueness, and known ids so prompt drift fails loudly instead of leaking bad state downstream.
