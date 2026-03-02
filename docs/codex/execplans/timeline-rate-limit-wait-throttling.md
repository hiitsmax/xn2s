# Timeline Rate-Limit Waiting And Throttling

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, timeline ingestion can survive temporary X/Twikit rate limiting (`429`) by actively waiting and retrying, and users can intentionally slow scraping throughput to reduce the chance of repeated limits.

## Progress

- [x] (2026-03-02 23:40Z) Added automatic wait-and-retry wrapper for `TooManyRequests` in timeline CLI flow.
- [x] (2026-03-02 23:41Z) Added configurable throttling between accounts and between timeline page requests.
- [x] (2026-03-02 23:42Z) Threaded page-delay config into timeline fetch runtime.
- [x] (2026-03-02 23:43Z) Added tests for retry/wait behavior and slow-fetch controls.
- [x] (2026-03-02 23:50Z) Ran full tests and verified help output with the new CLI options.

## Surprises & Discoveries

- Observation: Twikit `TooManyRequests` exceptions expose `rate_limit_reset` and optional headers, so we can compute precise waits instead of fixed sleep windows.
  Evidence: Local inspection of `twikit.errors.TooManyRequests`.

## Decision Log

- Decision: Default to waiting and retrying on `429`.
  Rationale: Better unattended batch completion for large source catalogs.
  Date/Author: 2026-03-02 / Codex

- Decision: Keep fail-fast mode available via `--no-wait-on-rate-limit`.
  Rationale: Some workflows prefer immediate failure for external orchestration retries.
  Date/Author: 2026-03-02 / Codex

## Outcomes & Retrospective

This change improves long-running scrape reliability without hiding failures: users get explicit progress during waits, configurable retry limits, and optional throttling controls. The remaining tradeoff is longer wall-clock runs when rate limits are frequent, which is intentional for robustness.
