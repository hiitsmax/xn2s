# Flatten Into Agents, Tools, Prompts, LLM, Schemas

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

`~/.agents/PLANS.md` governs this document and must be followed as implementation continues.

## Purpose / Big Picture

After this refactor, the repository should read like the actual product: fetch tweets, prepare queue state, and submit that work to one agent. The source tree under `src/xs2n/` should have a flatter root organized around `agents/`, `tools/`, `prompts/`, `llm/`, and `schemas/`, with no extra feature package nesting for code that does not own a separate product boundary.

The user wants the structure to stop implying a larger system than what exists today. This change moves the cluster-builder runtime into the agent package, moves operational helpers into tools, centralizes prompt assets in one folder, and removes stale runtime wording from the live repository surface.

## Progress

- [x] (2026-04-03 10:42Z) Mapped the current tree and confirmed the remaining bloat points: `cluster_builder/`, `sources/`, digest-specific `agents/` residue, and stale runtime wording in docs.
- [x] (2026-04-03 10:49Z) Moved the focused runner and store tests to the new root surfaces under `agents/`, `tools/`, and `llm/`, then confirmed the red state from missing modules.
- [x] (2026-04-03 10:56Z) Refactored the live runtime into `agents/cluster_builder_agent.py`, `tools/twitter.py`, `tools/cluster_state.py`, `prompts/cluster_builder.txt`, and `llm/{codex_auth,credentials}.py`.
- [x] (2026-04-03 11:02Z) Removed the live digest surface and rewrote the active docs around the smaller runtime.
- [x] (2026-04-03 11:09Z) Deleted the redundant packages and stale docs that still described removed runtime paths.
- [x] (2026-04-03 11:12Z) Verified the new structure with `uv run pytest -q`, `uv run xs2n --help`, `uv run xs2n-cluster-builder --help`, and `uv run xs2n-auth --help`.

## Surprises & Discoveries

- Observation: most of the current runtime is already simple; the bloat is mainly in where the files live and what the folders imply.
  Evidence: `src/xs2n/cluster_builder/run.py`, `src/xs2n/sources/twitter.py`, and `src/xs2n/sources/queue_builder.py` together already tell the whole real runtime story.

## Decision Log

- Decision: use `src/xs2n/agents/cluster_builder_agent.py` as the main agent module instead of keeping a nested `cluster_builder/` package.
  Rationale: the user wants `agents/` to contain the actual personalized agents, and today there is only one real agent surface.
  Date/Author: 2026-04-03 / Codex

- Decision: move tweet fetching and queue/cluster state helpers under `src/xs2n/tools/`.
  Rationale: these modules are operational helpers, not agents and not independent product areas.
  Date/Author: 2026-04-03 / Codex

- Decision: move the cluster-builder prompt asset to `src/xs2n/prompts/cluster_builder.txt`.
  Rationale: prompts should live in one dedicated place rather than inside a feature package.
  Date/Author: 2026-04-03 / Codex

## Outcomes & Retrospective

The new root package now matches the actual product much more directly. The model-driven runtime lives in `src/xs2n/agents/cluster_builder_agent.py`, operational code lives in `src/xs2n/tools/`, prompt text lives in `src/xs2n/prompts/`, and auth/model wiring lives in `src/xs2n/llm/`. The redundant feature packages, old digest surface, and stale docs are gone, so the repository now tells one coherent story from the top-level tree down to the CLI help text.

## Context and Orientation

In this repository, “agent” means the live model-driven loop that reads the queue and calls tools. “Tools” means the operational code that fetches tweets, prepares queue items, or mutates persisted queue/cluster state. “Prompt” means the static text instruction asset for the agent.

## Plan of Work

Start by moving the focused tests away from `cluster_builder.*` and `sources.*` imports so the first failing state points at the new flatter surfaces. Then create `src/xs2n/agents/cluster_builder_agent.py` by moving the current live agent/orchestration from `cluster_builder/run.py`. Move the queue/cluster operational helpers into `tools/`, merge the fetch bridge into `tools/twitter.py`, and move the prompt text into `prompts/`.

Once the imports all point at the flatter modules, delete the old `cluster_builder/` and `sources/` packages if no live code imports them. Finish by removing active stale docs and wording from the current README, autolearning note, tests, and CLI surfaces.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Update focused tests to import the new flatter modules and confirm the red state.

2. Move production code into:

   - `src/xs2n/agents/cluster_builder_agent.py`
   - `src/xs2n/tools/twitter.py`
   - `src/xs2n/tools/cluster_state.py`
   - `src/xs2n/prompts/cluster_builder.txt`

3. Re-run focused tests after each slice until green.

4. Delete old packages and remove stale docs/references.

5. Run full focused verification and CLI smoke checks.

## Validation and Acceptance

Acceptance is structural and behavioral. A `find src/xs2n -maxdepth 2` view should show the live code centered on `agents/`, `tools/`, `prompts/`, `llm/`, `schemas/`, and `cli/`. The main runtime should still work through the same queue and cluster JSON contracts, but the code should no longer require `cluster_builder/` and `sources/` as separate top-level concepts.

## Idempotence and Recovery

Move imports first, then delete packages. If a module move breaks a slice, keep the old package in place temporarily only until the focused tests for the new location pass; then remove the redundant path.

## Artifacts and Notes

Target end-state modules:

- `src/xs2n/agents/cluster_builder_agent.py`
- `src/xs2n/tools/twitter.py`
- `src/xs2n/tools/cluster_state.py`
- `src/xs2n/prompts/cluster_builder.txt`
