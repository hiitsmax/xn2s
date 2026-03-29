# Langfuse Local Setup

## Purpose

This repository already imports the Langfuse Python SDK for tracing, but it did not yet ship a local self-hosted Langfuse stack. The local setup now lives in:

- `docker-compose.langfuse.yml`
- `.env.langfuse` for the self-hosted stack secrets and headless bootstrap
- `.env.langfuse.project` for the local Python client credentials

## Why This Shape

- The compose topology mirrors the official `langfuse/langfuse` Docker Compose setup so we stay close to the upstream support path.
- On this Apple Silicon machine, `langfuse-worker:3` needs `platform: linux/amd64` because the pulled `arm64` image ships `./worker/entrypoint.sh` as an empty file and fails with `Exec format error`.
- The application-facing credentials are split into `.env.langfuse.project` so local CLI runs can source only the tracing variables they need.
- The Python SDK in this repo should prefer `LANGFUSE_BASE_URL`; `LANGFUSE_HOST` is kept alongside it for compatibility with older examples and integrations.

## Start

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml up -d
```

## Stop

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml down
```

## Verify HTTP

```bash
curl -I http://localhost:3000
```

## Verify SDK Auth

```bash
set -a
source .env.langfuse.project
set +a

uv run python - <<'PY'
from langfuse import Langfuse

client = Langfuse()
print(client.auth_check())
PY
```

## Daily Use

Before running local scripts that should emit traces, export the project variables:

```bash
set -a
source .env.langfuse.project
set +a
```
