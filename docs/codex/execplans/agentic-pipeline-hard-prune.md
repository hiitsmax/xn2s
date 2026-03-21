# Agentic Pipeline Hard-Prune

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the repository becomes a minimal Python base for one job only: authenticate against Codex and run one agentic digest pipeline over an input JSON file of preassembled threads. A user should be able to run one auth script, then run one pipeline script, and receive exactly one final artifact on disk: `digest.json`.

## Progress

- [x] (2026-03-21 18:13Z) Confirmed the current branch is clean and created the extraction branch `codex/agentic-pipeline-hard-prune`.
- [x] (2026-03-21 18:18Z) Pulled fresh official docs context for Codex auth and OpenAI structured outputs.
- [x] (2026-03-21 18:27Z) Wrote the new minimal contract tests for auth and pipeline behavior and watched them fail on missing modules.
- [x] (2026-03-21 18:34Z) Implemented the minimal package and the two public scripts.
- [x] (2026-03-21 18:41Z) Removed obsolete UI, ingestion, tracing, report-surface code, and old test/doc surfaces from the branch.
- [x] (2026-03-21 18:44Z) Rewrote `README.md`, minimized `pyproject.toml`, and refreshed the lockfile.
- [x] (2026-03-21 18:46Z) Verified the pruned branch with `uv run pytest -q`, script help output, and a live `python scripts/codex_auth.py status`.

## Surprises & Discoveries

- Observation: The current repository already contains the two hard requirements in reusable form: Codex auth resolution and a thin structured-output model wrapper.
  Evidence: `src/xs2n/agents/digest/credentials.py` and `src/xs2n/agents/digest/llm.py`.

- Observation: Direct script execution needed explicit `src/` path bootstrapping after the repo was reduced to standalone scripts.
  Evidence: `python scripts/run_agentic_pipeline.py --help` and `python scripts/codex_auth.py --help` work only because both scripts prepend the repository `src` directory to `sys.path`.

## Decision Log

- Decision: Treat this branch as an extraction branch, not as a backward-compatible refactor.
  Rationale: The explicit goal is to remove everything except the minimal Codex auth path and the agentic digest pipeline starter.
  Date/Author: 2026-03-21 / Codex

- Decision: Keep exactly two public scripts, but allow a tiny internal package behind them.
  Rationale: The user-facing surface stays brutally small while the implementation remains readable and testable.
  Date/Author: 2026-03-21 / Codex

- Decision: Write only the final digest artifact to disk.
  Rationale: The user explicitly rejected intermediate tracing and artifact fan-out for this branch.
  Date/Author: 2026-03-21 / Codex

## Outcomes & Retrospective

The branch now matches the requested shape closely: one Codex auth script, one pipeline runner script, one tiny internal package, and one final on-disk artifact contract. The biggest practical win from the prune is that the repository intent is now obvious at a glance. The main tradeoff is deliberate: this branch is no longer compatible with the previous broader product surface, but that was the point of the extraction.

## Context and Orientation

The current repository grew around a broader CLI, ingestion flow, UI, and saved artifact browser. This branch intentionally throws almost all of that away. The surviving behavior will be:

- `scripts/codex_auth.py`: login, status, logout, and optional device auth through the installed Codex CLI.
- `scripts/run_agentic_pipeline.py`: read a JSON file containing thread data, call the model through Codex-backed auth or `OPENAI_API_KEY`, and write one final `digest.json`.

The internal package will stay Python-first and minimal. It will include a credentials module, one thin model wrapper, shared schemas, and the pipeline steps needed to filter threads and group them into issues.

## Plan of Work

First, write tests for the new target contract instead of adapting the old report surface. The tests should prove three things: credentials can resolve from Codex auth, the pipeline can produce a final digest shape from thread input using a fake model wrapper, and the public auth script builds and delegates the expected Codex CLI commands.

Second, replace the old package surface with a minimal package. Keep only the code needed for credentials, model calls, schemas, and the pipeline orchestration. Remove UI modules, timeline ingestion, report runtime code, tracing logic, and broad CLI surfaces.

Third, add the two public scripts under `scripts/` and rewrite `README.md` around them. The pipeline script should accept an input path and output path and should never write intermediate files.

Finally, prune the repository to the new minimal shape and rerun the focused tests.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Write the failing tests for the new contract and run them directly.
2. Implement the minimal package and scripts until the tests pass.
3. Prune obsolete files from the branch.
4. Run:

       uv run pytest tests/test_codex_auth.py tests/test_pipeline.py -q

   Expect all focused tests to pass.

5. Run:

       uv run pytest -q
       python scripts/codex_auth.py --help
       python scripts/run_agentic_pipeline.py --help
       python scripts/codex_auth.py status

   Expect the test suite to pass, both scripts to expose the intended interface, and the Codex status call to delegate successfully when the local Codex CLI is installed and already logged in.

## Validation and Acceptance

Acceptance is behavioral.

Run:

    python scripts/codex_auth.py status

The script should delegate to the installed Codex CLI status flow.

Then run:

    python scripts/run_agentic_pipeline.py --input-file sample_threads.json --output-file digest.json

The script should read the supplied thread input, call the model with structured outputs, and write one final `digest.json` file. No intermediate artifacts should be created.

## Idempotence and Recovery

The auth script is safe to rerun because it delegates to Codex. The pipeline script is safe to rerun because it overwrites only the explicitly chosen output file. If the branch prune removes something needed by mistake, recover by checking the branch history or restoring from the parent branch.

## Artifacts and Notes

The only runtime artifact created by the minimal pipeline is the final output file:

- `digest.json`

## Interfaces and Dependencies

The internal package must expose:

    def resolve_model_credentials(api_key: str | None = None) -> ResolvedModelCredentials

    class DigestLLM:
        def run(self, *, prompt: str, payload: Any, schema: type[BaseModel]) -> BaseModel: ...

    def run_digest_pipeline(*, input_file: Path, output_file: Path, model: str, api_key: str | None = None) -> DigestOutput

The scripts must expose:

    python scripts/codex_auth.py login [--device-auth]
    python scripts/codex_auth.py status
    python scripts/codex_auth.py logout
    python scripts/run_agentic_pipeline.py --input-file ... --output-file ...

Revision note (2026-03-21): Created this ExecPlan to guide the extraction branch that strips the repository down to a two-script Codex-authenticated digest pipeline base.

Revision note (2026-03-21, later): Updated the living sections after implementing the prune, minimizing the dependency graph, and verifying the new branch surface.
