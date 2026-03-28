# Auth And Refresh

## Credential Lookup Order

When you construct `ChatOpenAICodexOAuth`, the package resolves credentials in this order:

1. `CODEX_HOME/auth.json`
2. refresh of the file-backed token if it is close to expiry and a refresh token exists
3. macOS keychain copy, if present
4. guided login-required error

This matches the requested behavior: try existing auth first, and only ask for login if nothing reusable is available.

## Why Login Is Not Automatic In The Constructor

The constructor is intentionally not interactive.

If credentials are missing, the facade raises `CodexOAuthLoginRequiredError` and tells the caller to run:

```bash
codex login
```

This matters because the package is meant to work in automation-friendly contexts too. A constructor that suddenly opens an OAuth flow would be surprising in cron jobs, background tasks, or non-interactive developer tooling.

If the caller does want to trigger login explicitly, the package exposes:

```python
from xs2n.langchain_codex_oauth import run_codex_oauth_login

run_codex_oauth_login()
```

## Refresh Behavior

The refresh implementation is intentionally narrow.

It refreshes only the file-backed auth document because that state can be updated safely in place. If the current usable credential came from the keychain, the package reuses it as-is and does not try to mutate keychain state.

The refresh path:

- reads `refresh_token` from `CODEX_HOME/auth.json`
- posts to `https://auth.openai.com/oauth/token`
- uses the Codex CLI public client id
- updates:
  - `access_token`
  - `refresh_token` if a new one is returned
  - `id_token` if a new one is returned
  - `last_refresh`

## Why This Refresh Shape

This implementation was chosen because the local Codex CLI state already contains:

- `access_token`
- `refresh_token`
- `account_id`
- `last_refresh`

and because inspection of the installed Codex CLI binary confirmed the same refresh URL and client id are used there as well.

The package does not try to be clever beyond that. It follows the minimal path needed to keep a file-backed login reusable.

## Failure Mode

If refresh cannot produce a usable access token, the package falls back to the normal login-required path instead of inventing a second recovery mechanism. This keeps the boundary honest: lookup and refresh are supported; a full custom OAuth state machine is not.
