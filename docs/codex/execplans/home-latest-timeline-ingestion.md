# Home Latest Timeline Ingestion Mode

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can ingest the authenticated X account's `Home -> Following` latest timeline directly from the CLI, then feed that data into the digest pipeline. The new user-visible behavior is `xs2n timeline --home-latest --since <iso>` and `xs2n report latest --home-latest`. This closes the gap where the tool could only ingest per-account timelines (`--account`) or onboarded source lists (`--from-sources`), but not the platform feed users actually read.

## Progress

- [x] (2026-03-08 23:09Z) Confirmed baseline behavior and gaps by reading `src/xs2n/profile/timeline.py`, `src/xs2n/cli/timeline.py`, `src/xs2n/cli/report.py`, and related tests.
- [x] (2026-03-08 23:11Z) Pulled fresh Twikit docs from Context7 for `Client.get_latest_timeline()` and `Result.next()` pagination behavior.
- [x] (2026-03-08 23:23Z) Implemented home-latest timeline fetcher and sync wrapper in `src/xs2n/profile/timeline.py`.
- [x] (2026-03-08 23:28Z) Implemented CLI mode `--home-latest` with recovery + rate-limit handling in `src/xs2n/cli/timeline.py`.
- [x] (2026-03-08 23:30Z) Extended `xs2n report latest` with optional `--home-latest` routing in `src/xs2n/cli/report.py`.
- [x] (2026-03-08 23:34Z) Added/adjusted tests for profile fetcher, timeline CLI validation/orchestration, and report latest routing.
- [x] (2026-03-08 23:36Z) Updated `README.md` and `docs/codex/autolearning.md`.
- [x] (2026-03-08 23:40Z) Ran focused validation (`41 passed`), full suite (`91 passed`), and CLI help checks for `timeline` and `report latest`.

## Surprises & Discoveries

- Observation: The current timeline importer already supports one authenticated sentinel (`__self__`) for "my own profile tweets," which is different from the home latest feed and cannot satisfy platform-feed ingestion.
  Evidence: `import_timeline_entries(...)` branches on `AUTHENTICATED_ACCOUNT_SENTINEL` and still calls user-level feeds (`Tweets`, `Replies`) rather than `client.get_latest_timeline()`.

- Observation: Reusing the account-based importer for home feed data would misrepresent ownership unless each entry carries its own author as the source handle.
  Evidence: Digest thread loading marks source-authored tweets using `author_handle == account_handle`, so home feed entries need `account_handle` set per tweet author rather than one global account value.

- Observation: `--home-latest` can be added without breaking existing automation when report mode remains source-based by default.
  Evidence: Existing tests for `latest(...)` still pass with `home_latest=False`, and new tests confirm explicit opt-in routing.

## Decision Log

- Decision: Add a third explicit timeline mode (`--home-latest`) instead of overloading `--account` with special values.
  Rationale: Keeping mode selection explicit is clearer for users and keeps control flow readable in the CLI.
  Date/Author: 2026-03-08 / Codex

- Decision: Preserve existing default behavior of `xs2n report latest` (source-based) and add `--home-latest` as an opt-in.
  Rationale: This avoids breaking existing cron flows while enabling the new platform-feed mode.
  Date/Author: 2026-03-08 / Codex

## Outcomes & Retrospective

The new platform-feed ingestion path is implemented and validated. Users can now run `xs2n timeline --home-latest --since ...` and `xs2n report latest --home-latest` to produce digest-ready timeline data from the authenticated Home -> Following feed. Existing modes (`--account`, `--from-sources`) remain unchanged, and the default `report latest` behavior is still source-based to preserve existing cron expectations. Validation passed with focused tests (`41 passed`) plus full suite (`91 passed`).

## Context and Orientation

The timeline ingestion runtime lives in `src/xs2n/profile/timeline.py`. It transforms Twikit tweet objects into the internal `TimelineEntry` schema and returns `TimelineFetchResult` for CLI persistence. Today, this importer fetches per-user feeds by calling `user.get_tweets('Tweets'|'Replies')`.

The command surface lives in `src/xs2n/cli/timeline.py`. It currently accepts exactly one mode between `--account` and `--from-sources`, performs Cloudflare/cookie recovery, handles rate limits, and merges results into `data/timeline.json`.

The orchestrator command `xs2n report latest` in `src/xs2n/cli/report.py` currently always calls `timeline(..., from_sources=True, ...)` before running `run_digest_report(...)`.

Twikit provides `Client.get_latest_timeline(...)`, documented as the authenticated `Home -> Following` timeline with paginated `Result.next()` behavior. This plan uses that method directly for the new mode.

## Plan of Work

Implement a new importer pair in `src/xs2n/profile/timeline.py`: an async `import_home_latest_timeline_entries(...)` and sync wrapper `run_import_home_latest_timeline_entries(...)`. The importer will authenticate with existing helpers, fetch `client.get_latest_timeline(...)`, iterate pages, filter by `--since`, dedupe by tweet id, and map each tweet through existing normalization logic. For home-latest records, use each tweet author's handle as `account_handle` so downstream digest threading can treat each fetched tweet as source-authored signal.

Update `src/xs2n/cli/timeline.py` to add `home_latest: bool = typer.Option(False, '--home-latest', ...)` and enforce exactly one active mode among account, sources, and home latest. Add `import_home_latest_with_recovery(...)` with the same local-cookie/bootstrap and Cloudflare recovery behavior used for account mode. Reuse existing merge and summary output, with wording that makes home-latest runs obvious in terminal output.

Update `src/xs2n/cli/report.py` to accept `--home-latest` on `report latest`. When enabled, call `timeline(..., home_latest=True, from_sources=False, account=None, ...)`; otherwise keep current source-based path.

Add tests in `tests/test_timeline_fetching.py` for the new importer behavior (pagination, cutoff filtering, classification/field mapping), in `tests/test_timeline_cli.py` for mode validation and home-latest command flow, and in `tests/test_report_cli.py` for report routing when `--home-latest` is enabled.

Update user-facing docs in `README.md` and append a new milestone note in `docs/codex/autolearning.md` describing what changed and why.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, run:

    uv run pytest tests/test_timeline_fetching.py tests/test_timeline_cli.py tests/test_report_cli.py
    uv run pytest
    uv run xs2n timeline --help
    uv run xs2n report latest --help

Expected behavior after implementation:

    uv run xs2n timeline --home-latest --since 2026-03-08T00:00:00Z

prints a home-latest ingestion summary and persists merged entries to `data/timeline.json`.

    uv run xs2n report latest --home-latest --lookback-hours 24

first ingests the home latest timeline then renders a digest run.

Validation run in this implementation:

    uv run pytest tests/test_timeline_fetching.py tests/test_timeline_cli.py tests/test_report_cli.py
    # 41 passed

    uv run pytest
    # 91 passed

## Validation and Acceptance

Acceptance is behavioral:

1. CLI help includes `--home-latest` for both `timeline` and `report latest`.
2. `timeline` mode validation rejects ambiguous combinations (for example `--from-sources --home-latest`).
3. Home-latest ingestion writes timeline entries and reports counts without regressing existing account/source modes.
4. `report latest --home-latest` routes to the new ingestion mode and still runs digest generation.
5. Full test suite passes.

## Idempotence and Recovery

This feature is safe to rerun. Timeline storage is merge/dedupe based, and digest runs remain timestamped folders. If a run fails due to cookies, Cloudflare block, or rate limits, recover credentials and rerun the same command. No destructive migration is introduced.

## Artifacts and Notes

Primary files touched in this milestone:

- `src/xs2n/profile/timeline.py`
- `src/xs2n/cli/timeline.py`
- `src/xs2n/cli/report.py`
- `tests/test_timeline_fetching.py`
- `tests/test_timeline_cli.py`
- `tests/test_report_cli.py`
- `README.md`
- `docs/codex/autolearning.md`
- `docs/codex/execplans/home-latest-timeline-ingestion.md`

Context7 reference used:

- `/websites/twikit_readthedocs_io_en` documentation for `Client.get_latest_timeline()` and paginated `Result.next()` usage.

## Interfaces and Dependencies

`src/xs2n/profile/timeline.py` will expose:

    async def import_home_latest_timeline_entries(
        cookies_file: Path,
        since_datetime: datetime,
        limit: int,
        prompt_login: LoginPrompt,
        page_delay_seconds: float = 0.0,
    ) -> TimelineFetchResult:
        ...

    def run_import_home_latest_timeline_entries(
        cookies_file: Path,
        since_datetime: datetime,
        limit: int,
        prompt_login: LoginPrompt,
        page_delay_seconds: float = 0.0,
    ) -> TimelineFetchResult:
        ...

`src/xs2n/cli/timeline.py` will add:

- `home_latest: bool` command option in `timeline(...)`.
- `import_home_latest_with_recovery(...)` helper.

`src/xs2n/cli/report.py` will add:

- `home_latest: bool` command option in `latest(...)`.

Revision note (2026-03-08): Updated the plan after implementation to reflect shipped behavior, concrete validation evidence, and final decisions discovered during coding.
