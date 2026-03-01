# Build CLI Onboarding For Timeline Sources

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not yet include a local `PLANS.md`; implementation follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can run one CLI command and onboard source profiles in two ways: paste a list of profile handles, or import handles from the account they follow. The result is a persisted source catalog in `data/sources.yaml` that can be used by later scrape and summary stages. The behavior is observable immediately by running `xs2n onboard`, selecting a mode, and inspecting the output file.

## Progress

- [x] (2026-03-01 20:56Z) Created project scaffold (`pyproject.toml`, `src/xs2n`, `tests/`, `docs/codex/`).
- [x] (2026-03-01 20:57Z) Implemented onboarding parsing and normalization logic in `src/xs2n/onboarding.py`.
- [x] (2026-03-01 20:58Z) Implemented YAML persistence and dedupe merge in `src/xs2n/storage.py`.
- [x] (2026-03-01 20:59Z) Implemented CLI command `xs2n onboard` with paste and following-import modes in `src/xs2n/cli.py`.
- [x] (2026-03-01 21:00Z) Added tests for parse and merge behavior in `tests/test_onboarding.py`.
- [x] (2026-03-01 20:58Z) Ran dependency install and test suite in this workspace (`python3 -m pip install -e '.[dev]'` and `pytest`).
- [ ] Validate an end-to-end CLI run transcript for following-import mode with a real authenticated account.
- [x] (2026-03-01 20:58Z) Validated end-to-end paste-mode transcript and corrected CLI routing so `xs2n onboard` is exposed as a subcommand.

## Surprises & Discoveries

- Observation: The Context7 MCP endpoint is currently unavailable.
  Evidence: `tool call failed for context7/resolve-library-id ... Transport closed`.

- Observation: Twikit provides direct methods for this feature without needing browser automation first.
  Evidence: `Client.get_user_by_screen_name`, `User.get_following`, and paginated `Result.next()` are present in the upstream source.

- Observation: This workspace is not an initialized Git repository.
  Evidence: `git status` returns `fatal: not a git repository`.

- Observation: Typer defaulted to single-command execution, which hid `onboard` as a subcommand.
  Evidence: running `xs2n onboard --paste` initially returned `Got unexpected extra argument (onboard)`.

## Decision Log

- Decision: Use a single `onboard` command with two entry paths (`--paste` and `--from-following`) instead of separate commands.
  Rationale: Keeps baby-step UX simple while still scriptable.
  Date/Author: 2026-03-01 / Codex

- Decision: Normalize handles to lowercase and store canonical values in `data/sources.yaml`.
  Rationale: Prevent duplicate sources (`@Alice` vs `alice`) and simplify downstream joins.
  Date/Author: 2026-03-01 / Codex

- Decision: Keep import-from-following authenticated through Twikit cookies with interactive fallback login.
  Rationale: Avoid paid API while still supporting direct import in one command.
  Date/Author: 2026-03-01 / Codex

- Decision: Add a root callback in `src/xs2n/cli.py` to force command-group behavior.
  Rationale: Ensure CLI UX matches documented command shape (`xs2n onboard ...`).
  Date/Author: 2026-03-01 / Codex

## Outcomes & Retrospective

Implementation is complete for the onboarding milestone itself: data parsing, persistence, CLI UX, local install, tests, and paste-mode runtime validation are in place. Remaining work is one operational validation item for following-import mode against a real authenticated account. The design intentionally keeps complexity low and defers pipeline ranking/summarization to the next milestone.

## Context and Orientation

This repository starts from an empty directory and now contains a minimal Python package under `src/xs2n`. The CLI entry point is `src/xs2n/cli.py`. Onboarding logic and Twikit integration live in `src/xs2n/onboarding.py`. Source-file persistence logic lives in `src/xs2n/storage.py` and writes to `data/sources.yaml`. Tests for deterministic behavior are in `tests/test_onboarding.py`.

In this plan, "onboarding" means collecting profile handles that will later be scraped for timeline-like digest generation. "Following import" means retrieving the accounts followed by a specific authenticated X account using Twikit without official X API keys.

## Plan of Work

Create a minimal installable project with a CLI entry point and stable data model. Implement a parser that accepts raw pasted text and extracts valid handles from both `@handle` and `x.com/handle` forms. Implement persistence with idempotent merge semantics so repeated onboarding does not duplicate entries.

Implement an authenticated Twikit importer that loads cookies when available, falls back to interactive login only when cookies are missing, and paginates followings until a user-defined limit is met. Integrate both paths into one `onboard` command and print concise outcomes.

Finally, add tests for parsing and merging, then run installation and tests so behavior is demonstrated end-to-end.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n` run:

    python3 -m pip install -e '.[dev]'
    pytest

For paste onboarding run:

    xs2n onboard --paste --sources-file data/sources.yaml

Then paste handles, press Enter on an empty line, and inspect:

    cat data/sources.yaml

For following import run:

    xs2n onboard --from-following <your_screen_name> --cookies-file cookies.json --limit 200

If `cookies.json` is absent, the command prompts for login details once and writes cookies for reuse.

## Validation and Acceptance

Acceptance is met when:

A user runs `xs2n onboard --paste`, pastes handles with duplicates/invalid tokens, and sees a result message reporting added and skipped counts while `data/sources.yaml` contains normalized unique handles.

A user runs `xs2n onboard --from-following <screen_name>` with a valid authenticated session and sees imported-following counts with dedupe applied.

`pytest` passes and confirms parsing plus merge semantics.

## Idempotence and Recovery

`merge_profiles` is idempotent for handle duplicates. Running onboarding repeatedly with overlapping handles only increases the duplicate count and preserves existing rows.

If following import fails because authentication expires, delete `cookies.json` and rerun to regenerate credentials. If malformed YAML exists, delete `data/sources.yaml` and rerun onboarding to rebuild a clean file.

## Artifacts and Notes

Key upstream methods used from Twikit:

    Client.get_user_by_screen_name(screen_name)
    User.get_following(count=...)
    Result.next()

Key output file shape:

    profiles:
      - handle: alice
        added_via: paste
        added_at: 2026-03-01T...

## Interfaces and Dependencies

The project depends on `typer` for CLI wiring, `PyYAML` for source persistence, and `twikit` for free, no-official-API account data collection.

`src/xs2n/onboarding.py` must expose:

    normalize_handle(raw: str) -> str | None
    parse_handles(text: str) -> tuple[list[str], list[str]]
    build_entries(handles: Iterable[str], source: str) -> list[ProfileEntry]
    run_import_following_handles(account_screen_name: str, cookies_file: Path, limit: int, prompt_login: callable) -> list[str]

`src/xs2n/storage.py` must expose:

    load_sources(path: Path = DEFAULT_SOURCES_PATH) -> dict[str, Any]
    merge_profiles(new_entries: list[ProfileEntry], path: Path = DEFAULT_SOURCES_PATH) -> OnboardResult

Revision note (2026-03-01): Added initial full implementation details and adjusted scope to a baby-step onboarding milestone after user requested paste-list plus following-import CLI first.
Revision note (2026-03-01): Updated plan with execution evidence (install/tests/paste transcript), recorded Typer command-group routing fix, and narrowed remaining validation to real-account following import only.
