# Storage Package Refactor

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository follows the guidance in `/Users/mx/.agents/PLANS.md`, and this document must be maintained in accordance with that file.

## Purpose / Big Picture

After this change, all application-state persistence code lives under a dedicated `src/xs2n/storage/` package instead of being split between the package root and CLI helpers. A contributor can now find source-catalog persistence, timeline persistence, and onboarding-state persistence in one place, while the CLI and tests continue to behave the same way.

The user-visible behavior does not change: `xs2n onboard` still saves onboarding defaults, `xs2n timeline` still reads sources and writes timeline entries, and the same tests still pass. The observable improvement is structural: ownership of persistence code is now clear, and imports no longer mix storage concerns with unrelated CLI modules.

## Progress

- [x] (2026-03-07 11:45Z) Audited the repository for persistence-related code paths and confirmed three ownership targets: sources, timeline, and onboarding state.
- [x] (2026-03-07 11:56Z) Created `src/xs2n/storage/` and moved the actual persistence implementations into dedicated modules.
- [x] (2026-03-07 12:02Z) Updated CLI imports and tests to use the new storage package boundary.
- [x] (2026-03-07 12:10Z) Ran `uv run pytest` and confirmed the refactor keeps the full suite green (`67 passed`).

## Surprises & Discoveries

- Observation: onboarding-state persistence was not in a storage module at all; it was embedded in `src/xs2n/cli/helpers.py`.
  Evidence: the file contained `DEFAULT_ONBOARD_STATE_PATH`, `_load_onboard_state`, and `_save_onboard_state` alongside prompt logic.

- Observation: `xs2n.storage` could be preserved as the public import path even after converting it from a single module into a package.
  Evidence: moving `src/xs2n/storage.py` to `src/xs2n/storage/sources.py` and re-exporting from `src/xs2n/storage/__init__.py` keeps `from xs2n.storage import ...` valid.

## Decision Log

- Decision: create three focused storage modules: `sources.py`, `timeline.py`, and `onboard_state.py`.
  Rationale: these map directly to the three persisted JSON/YAML documents managed by the CLI and avoid hiding persistence helpers inside unrelated modules.
  Date/Author: 2026-03-07 / Codex

- Decision: keep `src/xs2n/timeline_storage.py` as a thin compatibility wrapper instead of deleting it immediately.
  Rationale: internal imports can move to `xs2n.storage`, while any external callers that still import `xs2n.timeline_storage` do not break during the refactor.
  Date/Author: 2026-03-07 / Codex

- Decision: leave browser-cookie file writers in the profile layer.
  Rationale: those helpers are part of authentication/browser-session acquisition, not application-state storage. Moving them would blur domain boundaries rather than clarify them.
  Date/Author: 2026-03-07 / Codex

## Outcomes & Retrospective

The refactor achieved the intended structural outcome without changing user-visible behavior. Storage code is now centralized under `src/xs2n/storage/`, the CLI layer no longer owns persistence internals for onboarding defaults, and the former timeline module remains as a compatibility import.

The full suite passed after the move (`67 passed in 6.60s`), which is strong evidence that the package boundary changed cleanly. One useful lesson from this change is that repo structure can often be improved without forcing a public API break if the new package root re-exports the stable interfaces contributors already use.

## Context and Orientation

The repository is a Python CLI project using a `src/` layout. The package root is `src/xs2n/`. Before this refactor, source-profile persistence lived in `src/xs2n/storage.py`, timeline persistence lived in `src/xs2n/timeline_storage.py`, and onboarding-state persistence lived inside `src/xs2n/cli/helpers.py`.

In this repository, “persistence” means code that reads and writes files on disk for CLI-managed state, such as `data/sources.json`, `data/timeline.json`, and `data/onboard_state.json`. The user asked for a `storage` folder so that these responsibilities are co-located and easier to understand.

The key files after the refactor are:

- `src/xs2n/storage/__init__.py`, which re-exports the public storage API.
- `src/xs2n/storage/sources.py`, which owns source-catalog load/save/merge and legacy YAML migration.
- `src/xs2n/storage/timeline.py`, which owns timeline load/save/merge.
- `src/xs2n/storage/onboard_state.py`, which owns onboarding wizard state load/save/path resolution.
- `src/xs2n/cli/helpers.py`, which now consumes onboarding-state storage instead of implementing it.
- `src/xs2n/cli/onboard.py` and `src/xs2n/cli/timeline.py`, which import storage concerns from the new package.

## Plan of Work

First, move the former `src/xs2n/storage.py` implementation into `src/xs2n/storage/sources.py` and create `src/xs2n/storage/__init__.py` so existing `xs2n.storage` imports still work. Then add `src/xs2n/storage/timeline.py` with the former timeline persistence implementation and reduce `src/xs2n/timeline_storage.py` to a compatibility wrapper.

Next, extract onboarding-state read/write/path helpers out of `src/xs2n/cli/helpers.py` into `src/xs2n/storage/onboard_state.py`. Update `sanitize_cli_parameters` to call the storage module instead of managing JSON directly.

Finally, update tests to follow the new storage boundary, add repository notes describing the refactor, and run targeted validation that proves the CLI-facing behavior is unchanged.

## Concrete Steps

Work from the repository root `/Users/mx/Documents/Progetti/mine/active/xs2n`.

Run the targeted test command:

    uv run pytest tests/test_onboarding.py tests/test_timeline_storage.py tests/test_cli_helpers.py tests/test_timeline_cli.py

Expected result:

    ======================= 67 passed, 215 warnings in 6.60s =======================

Optionally inspect the package layout after the move:

    rg --files src/xs2n/storage src/xs2n | sort

Expected result:

    src/xs2n/storage/__init__.py
    src/xs2n/storage/onboard_state.py
    src/xs2n/storage/sources.py
    src/xs2n/storage/timeline.py

## Validation and Acceptance

Acceptance is satisfied when:

1. `xs2n.storage` exposes the same source-persistence helpers as before and now also exposes timeline/onboarding-state helpers.
2. `sanitize_cli_parameters` still reads and writes onboarding state correctly, proven by `tests/test_cli_helpers.py`.
3. Timeline merge behavior is unchanged, proven by `tests/test_timeline_storage.py` and timeline CLI tests.
4. Source merge behavior is unchanged, proven by `tests/test_onboarding.py`.

## Idempotence and Recovery

This refactor is safe to re-run because it only changes Python module layout and tests. If an import path is missed, rerun the targeted tests to reveal the missing reference and update the import in place. The compatibility wrapper at `src/xs2n/timeline_storage.py` reduces rollback risk for callers that have not moved yet.

## Artifacts and Notes

Important structural note:

    `xs2n.storage` is now a package, not a single module file.
    `xs2n.timeline_storage` remains importable as a compatibility layer.

Validation artifact:

    $ uv run pytest
    ...
    ======================= 67 passed, 215 warnings in 6.60s =======================

Fresh packaging guidance was checked in Context7 from `/pypa/setuptools`, confirming that the existing `tool.setuptools.packages.find.where = ["src"]` configuration continues to discover regular subpackages under `src/` when they contain `__init__.py`.

## Interfaces and Dependencies

The end state must keep these importable interfaces:

    xs2n.storage.DEFAULT_SOURCES_PATH
    xs2n.storage.load_sources(path: Path | None = None) -> dict[str, Any]
    xs2n.storage.merge_profiles(new_entries: list[ProfileEntry], path: Path | None = None) -> OnboardResult
    xs2n.storage.DEFAULT_TIMELINE_PATH
    xs2n.storage.load_timeline(path: Path | None = None) -> dict[str, Any]
    xs2n.storage.merge_timeline_entries(new_entries: list[TimelineEntry], path: Path | None = None) -> TimelineMergeResult
    xs2n.storage.DEFAULT_ONBOARD_STATE_PATH
    xs2n.storage.load_onboard_state(path: Path | None = None) -> dict[str, str]
    xs2n.storage.save_onboard_state(state: dict[str, str], path: Path | None = None) -> None
    xs2n.storage.resolve_onboard_state_path(parameters: dict[str, Any], default_path: Path | None = None) -> Path

Revision note: created during implementation to document the storage-package refactor requested by the user and to keep the package-boundary reasoning discoverable for future contributors.
