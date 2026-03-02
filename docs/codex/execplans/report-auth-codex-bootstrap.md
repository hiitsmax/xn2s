# Report Command Auth Bootstrap Via Codex

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the CLI includes a report-oriented entrypoint with a first authentication primitive: `xs2n report auth`. The command delegates to official Codex CLI authentication flows so users can sign in with their ChatGPT account and later reuse that authenticated model access inside the report pipeline.

## Progress

- [x] (2026-03-03 00:44Z) Confirmed current CLI topology and insertion point for a nested `report` Typer app.
- [x] (2026-03-03 00:45Z) Pulled fresh docs from Context7 (`/openai/codex`, `/fastapi/typer`) and verified official Codex auth commands.
- [x] (2026-03-03 00:48Z) Implemented `src/xs2n/cli/report.py` with `report auth` and codex command delegation.
- [x] (2026-03-03 00:49Z) Registered report sub-app in `src/xs2n/cli/cli.py`.
- [x] (2026-03-03 00:50Z) Added unit tests in `tests/test_report_cli.py`.
- [x] (2026-03-03 00:51Z) Updated `README.md` and `docs/codex/autolearning.md`.

## Surprises & Discoveries

- Observation: Codex supports ChatGPT OAuth in its own CLI, but there is no published third-party OAuth contract for arbitrary CLIs.
  Evidence: Official Codex authentication docs and command references.

- Observation: Typer subcommand callbacks only apply when the sub-app is registered with a name via `add_typer(..., name="...")`.
  Evidence: Context7 Typer docs (`subcommands/single-file` and callback behavior notes).

## Decision Log

- Decision: Implement `xs2n report auth` by delegating to the installed `codex` executable instead of reimplementing OAuth.
  Rationale: Uses official, supported auth flow and avoids brittle reverse-engineered login behavior.
  Date/Author: 2026-03-03 / Codex

- Decision: Keep one command with operational flags (`--status`, `--logout`, `--device-auth`) instead of introducing multiple nested auth verbs.
  Rationale: Delivers fast bootstrap value while preserving room to split into `report auth login/status/logout` later.
  Date/Author: 2026-03-03 / Codex

## Outcomes & Retrospective

The report command surface now exists and authentication bootstrap is in place for the upcoming agentic processing pipeline. Remaining work is to implement actual report-generation commands that consume authenticated model access and timeline data.
