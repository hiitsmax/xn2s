# Report Surface Simplification Implementation Plan

> Active source of truth: this plan describes the current report contract. Older digest-first plans in `docs/codex/execplans/` are historical context only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dead report/digest compatibility surface, unify duplicated runtime contracts, and harden the highest-risk persistence/UI seams while reducing the active report pipeline source area by at least 20%.

**Architecture:** This refactor is delete-first, not framework-first. The current repository has two overlapping stories: an older `report digest` surface and the newer `report issues` + `report html` + `report latest` flow. The work keeps the newer story, removes the stale one, and consolidates the duplicated argument, schedule, and presentation contracts so each behavior has one obvious home.

**Tech Stack:** Python 3.12, Typer, Pydantic v2, Twikit, FLTK/pyfltk, pytest, uv

---

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`. This document is self-contained and includes its own execution, validation, and progress-update rules.

## Purpose / Big Picture

After this change, a reader opening the report pipeline should see one honest flow: `report issues`, `report html`, `report latest`, and `report schedule`. The CLI, UI command forms, saved schedules, and digest package should all refer to the same active surface, without dead `digest` aliases, unused pipeline steps, or silently ignored settings.

The visible proof is:

1. `uv run xs2n report --help` and `uv run xs2n report schedule --help` expose only options that the runtime truly uses.
2. The active report/digest source area shrinks by at least 20% against the baseline listed below.
3. `uv run pytest -q` still passes, and new targeted smoke tests cover the main CLI boundaries.

## Progress

- [x] (2026-03-21 14:04Z) Measured the current source baseline and audited the highest-risk duplication clusters with 20 subagents.
- [x] (2026-03-21 14:04Z) Confirmed current repository baseline: `uv run pytest -q` passes with `230 passed`.
- [x] (2026-03-21 14:04Z) Confirmed active source baseline for the simplification KPI: `src/xs2n/agents/digest` = 1543 lines, report/runtime/schedule/UI-command cluster = 2759 lines, `src/xs2n/ui/app.py` = 1854 lines, combined target surface = 6156 lines.
- [ ] Milestone 1: Remove dead `report digest` compatibility surface and alias exports.
- [ ] Milestone 2: Unify latest/issues argument contracts across runtime, UI, and schedule.
- [ ] Milestone 3: Prune retired digest step files and stale schema surface.
- [ ] Milestone 4: Harden schedule persistence and overlap locking.
- [ ] Milestone 5: Simplify UI command runtime and auth/readiness coupling.
- [ ] Milestone 6: Make tests more hermetic at the CLI/UI/browser-cookie boundaries.
- [ ] Re-measure source lines after Milestones 1-6 and verify the 20% reduction target.

## Surprises & Discoveries

- Observation: The user’s rough “Enrico Fermi” estimate was directionally correct for source code, not for the whole repository.
  Evidence: The active report/digest/UI-app cluster is 6156 lines, which is about 47% of `src/xs2n` (13078 lines), but only about 22% of the full repo if docs and tests are counted.

- Observation: The project is not primarily failing because of broken tests.
  Evidence: `uv run pytest -q` passes with `230 passed`, while audit runs still found real brittleness in schedule persistence, UI test hermeticity, and stale compatibility paths.

- Observation: The highest-value reductions are deletions and contract consolidation, not new abstractions.
  Evidence: Independent audits converged on the same small set of issues: dead `report digest` surfaces, duplicated `LatestRunArguments`, stale schedule fields, and duplicated digest presentation logic.

## Decision Log

- Decision: Use the active `issues/html/latest` report vocabulary as the single canonical surface.
  Rationale: The README and current CLI already present this as the real product contract, while `digest` is mostly compatibility baggage.
  Date/Author: 2026-03-21 / Codex

- Decision: Measure the 20% reduction KPI against the active source refactor surface, not the whole repository including docs and tests.
  Rationale: The user’s intuition is about code that shapes behavior, not about archived plans or test fixtures. This keeps the KPI honest and achievable.
  Date/Author: 2026-03-21 / Codex

- Decision: Prefer delete-first refactors over framework extraction.
  Rationale: The main repository risk is duplicated/stale contracts, not a missing abstraction layer.
  Date/Author: 2026-03-21 / Codex

## Outcomes & Retrospective

This section must be updated after each major milestone. At completion, record:

- the final measured line-count delta against the 6156-line baseline,
- which compatibility surfaces were removed,
- which tests were added or tightened,
- which simplification candidates were intentionally deferred.

## Context and Orientation

The current report-related code is split across several overlapping layers:

- `src/xs2n/cli/report.py` owns the CLI commands for `issues`, `render`/`html`, and `latest`.
- `src/xs2n/report_runtime.py` owns the Python runtime for `report latest`, but still contains stale `report digest` command builders and duplicated argument models.
- `src/xs2n/ui/run_arguments.py` duplicates the runtime argument contracts for the desktop UI.
- `src/xs2n/report_schedule/` plus `src/xs2n/schemas/report_schedule.py` persist schedules, but they currently store both user intent and machine-local execution state.
- `src/xs2n/agents/digest/` is the active issue-report pipeline, but it still exports misleading `agents`/`digest` compatibility names and contains retired step modules that are no longer part of the real flow.
- `src/xs2n/ui/app.py` is the main FLTK shell. It is not over-abstracted, but it owns too many runtime details around subprocesses, selection state, and auth gating.

When this plan says “active report surface,” it means:

- `uv run xs2n report issues`
- `uv run xs2n report html`
- `uv run xs2n report latest`
- `uv run xs2n report schedule ...`

When this plan says “dead compatibility surface,” it means names or options that still exist in code, docs, or stored schedules but no longer affect real behavior, such as `report digest`, `run_digest_report`, or unused `parallel_workers` / `taxonomy_file` fields on latest-run paths.

## Plan of Work

First, make the current command vocabulary truthful. In `src/xs2n/report_runtime.py`, remove the stale `DigestRunArguments` path and collapse `LatestRunArguments` down to fields that `report latest` actually accepts and that `run_latest_report(...)` actually uses. In `src/xs2n/cli/report.py`, keep one canonical HTML render command and make the other a thin compatibility alias only if tests or user-facing stability still require it.

Second, make the argument contract single-source. Create or reuse one canonical latest/issues argument module and update `src/xs2n/ui/run_arguments.py`, `src/xs2n/report_runtime.py`, and `src/xs2n/report_schedule/catalog.py` / `src/xs2n/schemas/report_schedule.py` to use it. Do not add a generic command framework; the result should be one shared data contract plus very small adapters at the CLI/UI/storage boundaries.

Third, prune the digest package so it tells the truth. Remove or quarantine retired step files that are not called by the current pipeline, slim the public exports in `src/xs2n/agents/__init__.py` and `src/xs2n/agents/digest/__init__.py`, and keep exactly one honest entrypoint name for running issue reports. If package renaming is still needed after the deletions, do it as a small follow-up after the old compatibility names are gone.

Fourth, harden schedule persistence before touching cosmetic cleanup. Update `src/xs2n/storage/report_schedules.py` to save atomically and stop silently treating parse failure as an empty catalog. Update `src/xs2n/report_schedule/catalog.py` and `src/xs2n/report_schedule/runner.py` so schedule docs persist only user intent, not machine-local launcher state, and stale overlap locks can be detected and recovered safely.

Fifth, simplify the FLTK command runtime and auth coupling in `src/xs2n/ui/app.py`. The next edit should store the running subprocess handle explicitly, coalesce run refreshes, separate user selection from “currently running run id,” and stop basing auth gating on display labels. Keep the layout/theme code in place unless the file is still obviously too large after the runtime seam is extracted.

Sixth, tighten the test suite around the refactor seams. Add Typer smoke coverage for the real report CLI boundaries, add a render-failure test for `report latest`, add a shared FLTK stub for UI tests, and remove repeated fixture/setup blocks where a tiny helper would make intent clearer.

Seventh, make docs honest after the code is honest. Add one current “report contract” document under `docs/codex/`, update the README and autolearning notes to point to the current surface, and mark older digest-first execplans as historical context rather than active truth.

## Milestones

### Milestone 1: Delete The Dead Report Surface

This milestone removes names, flags, commands, and exports that no longer affect the active runtime. The repository should still expose the current `issues/html/latest/schedule` flow, but it must stop advertising `report digest`, dead latest-run fields, or stale alias exports as first-class behavior.

Acceptance for this milestone:

- `uv run xs2n report --help` shows only the active report commands.
- The runtime no longer constructs or serializes a dead `report digest` command path.
- The digest package exports one honest run entrypoint name plus any explicitly marked temporary compatibility shim.

### Milestone 2: Make The Latest/Issues Contract Single-Source

This milestone keeps only one canonical latest/issues argument representation across runtime, UI, and schedule persistence. Delete unused fields first. Only extract a shared contract if real duplication remains after the deletions.

Acceptance for this milestone:

- Runtime, UI, and schedule code agree on the same active latest/issues fields.
- Schedule persistence does not carry unused latest-run fields.
- No new command framework or adapter layer is introduced.

### Milestone 3: Prune Retired Digest Pipeline Artifacts

This milestone makes the digest package tell the truth. Any step modules, schema types, or render paths that are not part of the current issue-report runtime should be removed or explicitly marked historical and made unreachable from the active imports.

Acceptance for this milestone:

- The active pipeline files correspond to the real runtime steps only.
- No stale markdown-digest-only step remains on the active import path.
- Tests still cover the real `issues -> html` flow.

### Milestone 4: Harden Persistence And Runtime Seams

This milestone hardens the highest-risk operational boundaries without widening the architecture: schedule file writes, overlap locking, subprocess ownership in the UI, and auth/readiness seams that currently depend on string labels or duplicated cookie validation rules.

Acceptance for this milestone:

- Schedule file writes are atomic.
- A stale schedule lock can be detected or handled safely.
- The UI explicitly owns the running subprocess handle.
- Auth/readiness control flow no longer depends on user-facing label strings.

### Milestone 5: Tighten Test Hermeticity And Docs Truthfulness

This milestone removes environment-sensitive test assumptions and updates docs after code truth is established. The goal is not to rewrite the test suite or history, only to make the active contract and the proving commands honest and reproducible.

Acceptance for this milestone:

- UI tests can run without depending on a locally installed FLTK package.
- Targeted auth/timeline tests do not require implicit browser-cookie bootstrap from the host machine.
- The README and active docs describe the same current report surface as the code.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Record the baseline before edits:

       find src/xs2n/agents/digest -type f -name '*.py' -print0 | xargs -0 wc -l | tail -n 1
       wc -l src/xs2n/cli/report.py src/xs2n/report_runtime.py src/xs2n/cli/report_schedule.py src/xs2n/report_schedule/*.py src/xs2n/schemas/report_schedule.py src/xs2n/ui/run_arguments.py src/xs2n/ui/run_preferences.py src/xs2n/ui/auth_commands.py | tail -n 1
       wc -l src/xs2n/ui/app.py

   Expect:
   - digest package: `1543 total`
   - report/runtime/schedule/UI-command cluster: `2759 total`
   - UI app shell: `1854`

2. Verify repository baseline:

       uv run pytest -q

   Expect: `230 passed`

3. After each milestone, rerun the narrowest proving commands first, then the full suite:

       uv run pytest tests/test_report_*.py -q
       uv run pytest tests/test_ui_*.py tests/test_digest_browser_*.py -q
       uv run pytest tests/test_auth*.py tests/test_onboard*.py tests/test_timeline*.py tests/test_following.py tests/test_browser_cookies.py -q
       uv run pytest -q

4. Re-measure the source surface after the final milestone using the same line-count commands from step 1. Record the delta in `Outcomes & Retrospective`.

5. Failure-path proving commands that must exist before claiming the risky seams are hardened:

       uv run pytest tests/test_report_runtime.py -q
       uv run pytest tests/test_report_schedule.py tests/test_report_schedule_storage.py -q
       uv run pytest tests/test_ui_app.py tests/test_ui_app_rendering.py -q
       uv run pytest tests/test_auth.py tests/test_auth_cli.py tests/test_browser_cookies.py -q

   Expect: all targeted failure-path suites pass after their related milestones.

## Validation and Acceptance

Acceptance is behavioral and measurable.

1. `uv run xs2n report --help` should no longer imply dead or misleading report surfaces.
2. `uv run xs2n report latest --help` and `uv run xs2n report schedule create --help` should expose only arguments that the latest runtime truly uses.
3. A saved schedule created after the refactor should not persist stale machine-local launcher fields as part of the user intent contract.
4. The digest package should not export retired or misleading public names beyond any explicitly retained compatibility shim.
5. `uv run pytest -q` must pass after the refactor.
6. The measured active source baseline of 6156 lines must be reduced by at least 20%, which means the final count must be 4924 lines or fewer across the same measured file set.

## Idempotence and Recovery

This refactor should be safe to stage in small commits. Each milestone must leave the repository in a runnable state with passing tests before moving on.

If a compatibility alias cannot be removed safely in one step, it may stay temporarily only if it satisfies all three rules:

1. it is marked in code as compatibility-only,
2. it is not documented as the active surface,
3. it is listed explicitly in `Progress` with the reason it remains.

Allowed temporary residual shims are only:

- one report render alias if needed for backward CLI stability,
- one digest-package import shim while call sites migrate.

No other compatibility surfaces should survive Milestone 1.

Do not add a new abstraction layer as a workaround for risky deletion; revert to the smallest compatibility shim instead.

If a schedule or UI migration risks losing user data, preserve backward compatibility on read and write the new form forward.

## Artifacts and Notes

Key source files expected to change:

- `src/xs2n/cli/report.py`
- `src/xs2n/report_runtime.py`
- `src/xs2n/ui/run_arguments.py`
- `src/xs2n/ui/run_preferences.py`
- `src/xs2n/ui/app.py`
- `src/xs2n/agents/__init__.py`
- `src/xs2n/agents/digest/__init__.py`
- `src/xs2n/agents/digest/pipeline.py`
- `src/xs2n/agents/digest/steps/render_digest.py`
- `src/xs2n/agents/digest/steps/categorize_threads.py`
- `src/xs2n/agents/digest/steps/process_threads.py`
- `src/xs2n/report_schedule/catalog.py`
- `src/xs2n/report_schedule/runner.py`
- `src/xs2n/storage/report_schedules.py`
- `src/xs2n/schemas/report_schedule.py`
- targeted tests under `tests/`
- current-contract docs under `docs/codex/`

## Interfaces and Dependencies

At the end of this refactor:

- The runtime should have one canonical latest/issues argument contract, not separate conflicting models in runtime, UI, and schedule code.
- The report package should have one canonical run entrypoint name for issue generation.
- The schedule schema should persist cadence plus latest-run intent, not resolved launcher/cwd/log execution details.
- The UI command model should carry semantic run kind/readiness information instead of relying on label strings for control flow.
- The digest presentation layer should separate “load saved digest data” from “render this data as native UI or HTML export.”

Revision note (2026-03-21): Added this ExecPlan after a 20-agent audit found that the main simplification win is delete-first contract cleanup, not deeper abstraction. The line-count KPI is explicitly tied to the active source surface rather than the full repository.
