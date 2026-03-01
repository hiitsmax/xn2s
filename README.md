# xs2n

`xs2n` is a baby-step CLI project to build a free-first timeline summarization pipeline.

Current milestone: onboarding profile sources via CLI.

## Modern Quickstart (`uv`)

```bash
uv sync --extra dev
```

Run the CLI:

```bash
uv run xs2n --help
```

Or use task aliases:

```bash
make setup
make run
make test
make wizard
```

## Onboard Profiles

Paste handles:

```bash
uv run xs2n onboard --paste
```

Import from who you follow (requires authenticated Twikit session):

```bash
uv run xs2n onboard --from-following your_screen_name --cookies-file cookies.json --limit 200
```

Interactive wizard (default if no mode is provided):

```bash
uv run xs2n onboard
uv run xs2n onboard --wizard
```

Quick task aliases:

```bash
make onboard-paste
make onboard-following HANDLE=your_screen_name
```

Profiles are stored in `data/sources.yaml`.

## Legacy Install (pip)

```bash
python -m pip install -e .[dev]
xs2n --help
```
