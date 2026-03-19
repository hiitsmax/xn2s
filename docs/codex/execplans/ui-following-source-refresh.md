# CLI-First Following Source Refresh

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can refresh the stored source catalog from the currently authenticated X account's following list with one explicit CLI shortcut, and the desktop UI can trigger that same shortcut without duplicating business logic. The visible proof is that running the new CLI shortcut rewrites `data/sources.json` to match the current authenticated account's following list, and the UI exposes a matching action that launches the CLI and shows its transcript.

This work matters because the current CLI can only merge new handles into the source catalog through `xs2n onboard --from-following <handle>`. That is good for initial onboarding, but it cannot express "make my stored source list exactly match who I follow right now." The new behavior adds that missing "replace with current following" path while preserving the existing merge-oriented onboarding flow.

## Progress

- [x] (2026-03-18 00:00Z) Audited the existing onboarding, storage, and UI command-launch paths to find the smallest CLI-first integration point.
- [x] (2026-03-18 00:00Z) Confirmed with the user that the refresh behavior must be a full replacement of the source catalog, not an additive merge.
- [x] (2026-03-18 00:00Z) Confirmed the UI should not ask for a handle and should instead reuse the authenticated-current-account path plus a dedicated CLI shortcut.
- [x] (2026-03-18 00:00Z) Added a storage helper that replaces the entire sources document with a new handle list while keeping the persisted JSON shape stable.
- [x] (2026-03-18 00:00Z) Added a dedicated `xs2n onboard` shortcut for refreshing from the authenticated account's following list with full-replace semantics.
- [x] (2026-03-18 00:00Z) Added focused CLI tests for the new replace path, the authenticated-current-account shortcut behavior, the zero-following edge case, and the shared parameter sanitizer.
- [x] (2026-03-18 00:00Z) Added a desktop UI action that launches the new CLI shortcut and reuses the existing transcript/status machinery.
- [x] (2026-03-18 00:00Z) Added focused UI tests for the new launch action and the command-building helper introduced for it.
- [x] (2026-03-18 00:00Z) Updated `README.md` and `docs/codex/autolearning.md` with the new command and the architectural rationale.
- [x] (2026-03-18 00:00Z) Ran the focused test commands successfully and recorded the unrelated full-suite collection failures already present in this workspace.

## Surprises & Discoveries

- Observation: the current following-import path already supports "current authenticated account" behavior through a sentinel value in `src/xs2n/profile/following.py`.
  Evidence: `AUTHENTICATED_ACCOUNT_SENTINEL = "__self__"` and `if account_screen_name == AUTHENTICATED_ACCOUNT_SENTINEL: user = await client.user()`.

- Observation: the missing piece is not fetching the authenticated account's following list; it is the CLI and storage contract around replacement instead of merge.
  Evidence: `src/xs2n/cli/onboard.py` already fetches followings through `import_following_with_recovery(...)`, but always writes with `merge_profiles(...)`.

- Observation: the desktop UI already has a generic "run CLI in the background and show transcript" path, so the UI feature should stay thin.
  Evidence: `ArtifactBrowserWindow._start_command(...)` in `src/xs2n/ui/app.py` shells out through `subprocess.run(...)`, captures stdout/stderr, and refreshes the window afterward.

- Observation: the current source schema does not track which account produced a following import, so a scoped partial refresh is not honestly representable today.
  Evidence: `src/xs2n/storage/sources.py` persists only `handle`, `added_via`, and `added_at` for each profile row.

- Observation: replacement semantics must allow an empty following list to clear stale rows instead of failing.
  Evidence: `tests/test_onboard_cli.py::test_onboard_refresh_following_allows_empty_following_result` failed until the refresh branch stopped treating an empty imported handle list as an error.

- Observation: the current workspace contains unrelated incomplete features that prevent `uv run pytest` from collecting the full suite.
  Evidence: collection currently fails on missing modules such as `xs2n.cli.auth`, `xs2n.schemas.auth`, `xs2n.report_runtime`, `xs2n.cli.report_schedule`, and `xs2n.ui.auth_commands`.

## Decision Log

- Decision: implement this feature as a new shortcut on `xs2n onboard` instead of a new top-level command.
  Rationale: this keeps the mental model consistent with the existing onboarding surface and reuses the already-isolated following-import recovery logic.
  Date/Author: 2026-03-18 / Codex

- Decision: the shortcut must use the authenticated-current-account path and must not require a handle in the UI.
  Rationale: the user explicitly wants the UI to delegate to the CLI without an extra identity prompt, and the lower-level importer already supports this behavior.
  Date/Author: 2026-03-18 / Codex

- Decision: refresh semantics mean replacing the entire `sources_file`, not merging into it and not replacing only a subset.
  Rationale: the user explicitly chose full replacement, and the current schema cannot safely express per-origin subset replacement.
  Date/Author: 2026-03-18 / Codex

- Decision: keep the existing `--from-following <handle>` path as the explicit, advanced override for importing another account's following list.
  Rationale: this preserves existing behavior and keeps the new shortcut focused on the common "refresh my current account" action.
  Date/Author: 2026-03-18 / Codex

- Decision: in replace mode, `OnboardResult.added` means the deduplicated profile count written to disk.
  Rationale: replacement does not fit the old "net new versus duplicates" mental model, but the CLI still needs one compatible result type for the final stored count.
  Date/Author: 2026-03-18 / Codex

- Decision: keep the UI surface for this feature in the `Run` menu instead of adding a new preferences form or local onboarding logic.
  Rationale: the user asked for a CLI-first flow, and the existing background-command launcher already provides the right integration boundary.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

Implementation is complete for the scope of this plan. The result is a clear split between two onboarding modes: merge-oriented import for explicit handles and replace-oriented refresh for the authenticated current account. The main lesson was that replacement semantics only become trustworthy once the zero-following case is tested explicitly; otherwise it is easy to preserve a merge-era guard that prevents clearing stale rows.

## Context and Orientation

The relevant CLI entry point is `src/xs2n/cli/cli.py`, which registers `onboard`, `timeline`, `ui`, and `report`. The existing onboarding command lives in `src/xs2n/cli/onboard.py`. That file already knows how to normalize an optional handle, recover from Cloudflare and cookie failures, and fetch handles from X through `import_following_with_recovery(...)`.

The actual following fetcher lives in `src/xs2n/profile/following.py`. In this repository, "following" means "the accounts the authenticated X account follows," not "the accounts that follow the authenticated X account." That module already supports a special current-account mode through `AUTHENTICATED_ACCOUNT_SENTINEL`, which means "ask Twikit for the logged-in user directly."

The source catalog lives in `data/sources.json` and is read and written through `src/xs2n/storage/sources.py`. Today, the storage layer exposes `merge_profiles(...)`, which appends unseen handles and skips duplicates. It never removes stale rows. The new feature needs a second storage behavior: replace the stored `profiles` list with a fresh deduplicated list built from the latest following import.

The desktop app lives in `src/xs2n/ui/app.py`. It is not a general profile-management UI; it is a run-artifact browser with a menu bar and a compact command strip. The important fact for this plan is that the UI already knows how to launch CLI commands in a background thread, capture their terminal output, and show that output in the right-hand viewer. That means the UI should not reimplement any following refresh logic; it should only launch the new CLI shortcut.

The tests relevant to this feature are concentrated in `tests/test_following.py`, `tests/test_onboard_recovery.py`, `tests/test_onboarding.py`, `tests/test_onboard_cli.py`, `tests/test_cli_helpers.py`, `tests/test_ui_run_arguments.py`, and `tests/test_ui_following_refresh.py`. There is now direct happy-path coverage for `onboard()` orchestration in the dedicated `tests/test_onboard_cli.py` file.

## Plan of Work

Start in the storage layer. Add a helper in `src/xs2n/storage/sources.py` that accepts a fresh list of `ProfileEntry` rows and overwrites the stored `profiles` list with those rows. This helper must keep the JSON document shape stable, deduplicate by canonical lowercase handle, preserve the order produced by the importer, and write the file through the existing `save_sources(...)` path. The existing `merge_profiles(...)` helper must remain unchanged because it still serves paste onboarding and explicit merge-style imports.

Then update `src/xs2n/cli/onboard.py`. Keep the existing `--from-following <handle>` path and its merge behavior intact. Add a new explicit shortcut option on the same command, named for refresh rather than merge. The shortcut should call the same `import_following_with_recovery(...)` helper but pass the authenticated-current-account sentinel instead of a screen name. After fetching the handles, it should convert them to entries with `build_entries_from_handles(..., source="following_refresh")` and write them through the new replace helper. The success message should say that the source catalog was refreshed and should report the number of stored profiles written after replacement. If the imported list is empty, the command must still succeed and clear the stored profile list.

Because this repository treats readability as architecture, keep the orchestration readable from top to bottom inside `onboard()`. Do not add pass-through wrappers that only rename the replace operation. The shared onboarding sanitizer in `src/xs2n/cli/helpers.py` must also learn the new flag so `--refresh-following` is mutually exclusive with `--paste` and `--from-following`, records `last_mode = "following"`, and skips the interactive onboarding prompt entirely.

After the CLI path is in place, update the desktop UI. In `src/xs2n/ui/app.py`, add a new `Run` menu item that launches the new CLI shortcut through `_start_command(...)`. The label and tooltip must use "following," not "followers," so the UI matches the CLI and the underlying X concept. The UI action should not ask for any handle, because the CLI shortcut already implies "current authenticated account."

Finally, extend the tests and docs. Add a storage-level test proving replacement semantics, add CLI-level tests around the new shortcut and around the existing merge path remaining unchanged, add UI-callback tests that prove the new action launches the expected CLI arguments, and update `README.md` plus `docs/codex/autolearning.md` with the new command and its rationale.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the feature was implemented and validated with:

    uv run pytest tests/test_onboarding.py::test_replace_profiles_overwrites_stale_entries -v
    uv run pytest tests/test_onboard_cli.py::test_onboard_refresh_following_replaces_sources_for_authenticated_account -v
    uv run pytest tests/test_onboard_cli.py::test_onboard_refresh_following_allows_empty_following_result -v
    uv run pytest tests/test_cli_helpers.py::test_sanitize_cli_parameters_refresh_following_skips_prompt_and_sets_mode -v
    uv run pytest tests/test_ui_run_arguments.py::test_latest_run_arguments_build_following_refresh_command tests/test_ui_following_refresh.py::test_refresh_following_click_uses_preferences_window_command -v
    uv run pytest tests/test_onboarding.py tests/test_onboard_cli.py tests/test_cli_helpers.py tests/test_ui_run_arguments.py tests/test_ui_following_refresh.py -v
    uv run pytest

Observed results:

    1. The focused feature suite passed with `28 passed`.
    2. `uv run pytest` still fails during collection because this workspace already contains unrelated missing modules outside this feature.
    3. `uv run xs2n onboard --help` now shows `--refresh-following`.

For manual exercise after authenticating with a real X session:

    uv run xs2n onboard --refresh-following --cookies-file cookies.json --sources-file data/sources.json

Inspect the file:

    cat data/sources.json

Then start the UI:

    uv run xs2n ui

Use the new menu item or toolbar button and confirm that the viewer shows the CLI transcript and that the action does not ask for a handle.

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. Running the new CLI shortcut rewrites `data/sources.json` so it contains only the latest following-derived handles from the authenticated current account.
2. Running the existing `xs2n onboard --from-following <handle>` path still uses merge semantics and does not silently switch to replacement.
3. The CLI output clearly distinguishes refresh/replacement from import/merge so a human can tell which mode ran.
4. The desktop UI exposes a dedicated action for following refresh, and that action shells out to the new CLI shortcut without asking for a handle.
5. Focused tests for storage, onboarding, and UI all pass, and any remaining full-suite failure is outside this feature's scope.

The minimum proof for item 1 is `tests/test_onboarding.py::test_replace_profiles_overwrites_stale_entries` plus `tests/test_onboard_cli.py::test_onboard_refresh_following_allows_empty_following_result`. The minimum proof for item 4 is `tests/test_ui_following_refresh.py::test_refresh_following_click_uses_preferences_window_command`.

## Idempotence and Recovery

The new refresh command should be safe to run repeatedly. If the authenticated account's following list has not changed, rerunning the command should rewrite the same logical profile set and leave the catalog stable. Because the command is intentionally destructive with respect to stale rows, recovery is simple but explicit: if the wrong account was authenticated or the result is not what the user wanted, rerun the command after correcting authentication, or restore `data/sources.json` from version control or a backup.

The existing merge-style onboarding path remains the non-destructive option. That is the rollback-friendly path for users who want to add sources without removing any existing rows.

## Artifacts and Notes

The expected new CLI shape is intentionally small and explicit:

    uv run xs2n onboard --refresh-following --cookies-file cookies.json --sources-file data/sources.json

The expected success transcript should read like replacement, not merge. For example:

    Refreshed source catalog from the authenticated account's following list.
    Stored 187 profiles in the sources catalog.

The storage helper introduced by this plan should still write the same JSON structure:

    {
      "profiles": [
        {
          "handle": "alice",
          "added_via": "following_refresh",
          "added_at": "2026-03-18T..."
        }
      ]
    }

## Interfaces and Dependencies

Continue to use the existing dependencies already present in this repository: `typer` for CLI wiring, `twikit` for authenticated X access, stdlib `json` for source persistence, and `pyfltk` for the optional desktop UI.

At the end of this work, `src/xs2n/storage/sources.py` must expose both behaviors clearly:

    merge_profiles(new_entries: list[ProfileEntry], path: Path | None = None) -> OnboardResult
    replace_profiles(new_entries: list[ProfileEntry], path: Path | None = None) -> OnboardResult

`replace_profiles(...)` should return an `OnboardResult` compatible object so the CLI can report counts without inventing a second result type. In this feature, `added` means the deduplicated profile count written by the replacement operation.

`src/xs2n/cli/onboard.py` must continue to expose:

    def onboard(...) -> None

but with one additional explicit shortcut option for authenticated-current-account refresh. The implementation must still route through:

    import_following_with_recovery(account: str, cookies_file: Path, limit: int) -> list[str]

using `AUTHENTICATED_ACCOUNT_SENTINEL` from `src/xs2n/profile/following.py` for the current-account path.

The UI must keep using:

    ArtifactBrowserWindow._start_command(...)

as the one subprocess-launch boundary. Do not add a second background-process mechanism for the new button.

Revision note (2026-03-18): Created the initial living ExecPlan after confirming the user wants authenticated-current-account refresh plus a CLI shortcut, with full source-catalog replacement semantics.
Revision note (2026-03-18): Updated the plan after implementation with the zero-following refresh rule, the focused test evidence, and the unrelated full-suite collection failures present in this workspace.
