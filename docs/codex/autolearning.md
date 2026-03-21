# xs2n Autolearning Framework

## Current Surface

This branch intentionally reduced the repository to a minimal two-script surface:

- `scripts/codex_auth.py`
- `scripts/run_agentic_pipeline.py`

## Branch Note (2026-03-21)

- The extraction branch is deliberately not backward-compatible with the old wider CLI/UI product surface.
- Keeping only one final artifact on disk made the runtime contract much easier to reason about.
- The useful reusable code from the older repo was smaller than the full product shell:
  - Codex credential resolution
  - one thin structured-output model wrapper
  - two semantic pipeline steps
- When a branch is explicitly meant to become a minimal base, it is cheaper to prune aggressively than to keep "temporary compatibility" layers that nobody wants.
