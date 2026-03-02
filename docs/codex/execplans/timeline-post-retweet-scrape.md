# Timeline Post/Retweet Scraping Pipeline

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document is maintained in accordance with `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, we can ingest all posts and retweets from an account since a cutoff datetime in one command run, persist normalized records for downstream processing agents, and recover gracefully from common authentication and Cloudflare blockers.

The user-visible outcome is a new `xs2n timeline` command that writes timeline entries to disk and prints a concise run summary.

## Progress

- [x] (2026-03-02 00:00Z) Collected current codebase context and onboarding/recovery patterns.
- [x] (2026-03-02 00:01Z) Pulled fresh Twikit docs from Context7 for timeline fetch methods and tweet fields.
- [x] (2026-03-02 00:02Z) Spawned parallel sub-agents for Twikit strategy, repo integration points, and ExecPlan drafting.
- [x] (2026-03-02 00:06Z) Implemented Twikit timeline fetcher with cutoff filtering and retweet classification.
- [x] (2026-03-02 00:07Z) Implemented timeline storage merge layer with dedupe.
- [x] (2026-03-02 00:09Z) Added `xs2n timeline` command with recovery flow.
- [x] (2026-03-02 00:12Z) Added tests for timeline fetcher, storage, and CLI behavior.
- [x] (2026-03-02 00:13Z) Updated README and autolearning notes.
- [x] (2026-03-02 00:14Z) Ran full test suite (`45 passed`) and command help smoke checks.
- [ ] Commit atomically with conventional commits.

## Surprises & Discoveries

- Observation: Twikit provides a direct user timeline fetch path with pagination (`User.get_tweets("Tweets")` + `Result.next()`), so this can reuse the same authenticated session flow as following import.
  Evidence: Context7 docs from Twikit readthedocs and module references.

- Observation: Retweet detection is available directly on tweet objects via `retweeted_tweet`, avoiding brittle text-prefix parsing.
  Evidence: Twikit `Tweet` attribute docs in Context7.

- Observation: The `Tweets` feed can still include reply-shaped entries in edge cases, so explicit reply filtering is safer for strict posts+retweets ingestion.
  Evidence: Local unit tests and defensive branch in timeline mapper (`in_reply_to` filter).

## Decision Log

- Decision: Add a dedicated top-level CLI command `xs2n timeline` rather than overloading `onboard`.
  Rationale: Keeps source onboarding and content ingestion clearly separated while preserving existing command style.
  Date/Author: 2026-03-02 / Codex

- Decision: Persist timeline entries in a separate file (`data/timeline.json`) with idempotent merge by tweet id.
  Rationale: Safe incremental runs and easy downstream consumption without touching `data/sources.json`.
  Date/Author: 2026-03-02 / Codex

- Decision: Reuse existing Cloudflare/browser-cookie recovery pattern in the new timeline command.
  Rationale: Consistent user experience and lower implementation risk.
  Date/Author: 2026-03-02 / Codex

## Outcomes & Retrospective

Feature implementation is complete and validated by tests. We now have a dedicated, recoverable timeline ingestion path that reads posts+retweets since a user-defined cutoff and persists deduplicated records for downstream processing. The main tradeoff is file growth in `data/timeline.json`; if volume increases, the next iteration should move to append-only per-account storage.

## Context and Orientation

Existing onboarding and auth flows live in:

- `src/xs2n/cli/onboard.py`
- `src/xs2n/profile/following.py`
- `src/xs2n/profile/auth.py`

This feature introduces timeline ingestion without changing onboarding behavior.

## Plan of Work

1. Add timeline domain types and a storage module for deduped persistence.
2. Add Twikit fetcher logic for account timelines with:
   - authenticated client bootstrap,
   - pagination,
   - cutoff filtering,
   - retweet/post classification.
3. Add `xs2n timeline` command with recovery behavior mirroring onboarding.
4. Add deterministic tests for fetching, persistence, and command flow.
5. Document usage and autolearning notes.

## Validation and Acceptance

Acceptance criteria:

1. `xs2n timeline --account <handle> --since <iso-datetime>` runs and persists entries.
2. Stored records include both posts and retweets from at or after cutoff.
3. Re-running with overlapping windows skips duplicates deterministically.
4. Existing onboarding tests keep passing.
5. Full test suite passes.

## Idempotence and Recovery

- Storage merge is idempotent by tweet id.
- Local browser cookie import is attempted before API fetch when cookies file is missing.
- Cloudflare 403 errors trigger local-cookie retry and optional Playwright browser bootstrap retry.

## Interfaces and Dependencies

- Twikit (timeline fetch): `Client.get_user_by_screen_name`, `User.get_tweets`, `Result.next`, `Tweet.retweeted_tweet`, `Tweet.created_at_datetime`.
- Typer for CLI options and parameter validation.
- JSON persistence for timeline records.
