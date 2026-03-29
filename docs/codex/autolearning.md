# xs2n Autolearning Framework

## Current Surface

This branch currently exposes two automation surfaces plus the auth helper they depend on:

- `scripts/codex_auth.py`
- `scripts/run_cluster_builder.py`
- `scripts/run_agentic_pipeline.py`

## Branch Note (2026-03-28)

- A Codex OAuth facade for LangChain works best as an explicit additive package instead of smearing Codex transport rules into the cluster builder runner.
- The local `langchain-openai` version in this repo still routes `ChatOpenAI` through `chat.completions`, so a Codex-compatible facade has to replace the transport path, not just pass a different `base_url`.
- The Codex backend currently expects a stricter Responses contract than generic wrappers send by default: top-level `instructions`, list-based `input`, `store=False`, and `stream=True`.
- Injecting a small default instruction when no `SystemMessage` is present closes a real compatibility gap for `with_structured_output(...)` callers that otherwise send no top-level instructions at all.

## Branch Note (2026-03-28, later)

- For the first cluster-builder prototype, a tweet list should behave like a todo queue with explicit status transitions instead of as a passive batch input.
- Allowing `deferred` tweets inside the same run is a better fit for the clustering task than forcing immediate assignment or waiting for a future scheduled run.
- LangFuse should be integrated through the standard LangChain callback handler first; manual custom tracing would add complexity before the queue and cluster contracts are proven.
- The domain boundary should stay tool-first: the agent can reason freely, but queue state and cluster state should only change through explicit structured tools.
- DeepAgents bring automatic built-in tools, so the first safe strategy is to constrain domain work through prompt and tests rather than prematurely rewriting the runtime to remove those tools.
- Iterator-style queue access is the wrong contract for this task; paginated queue inspection with `limit` and `offset` gives the model enough local context without burning tokens on repeated "next item" calls.
- For this clustering workflow, one well-scoped cluster builder agent is preferable to a second triage subagent when the subagent does not unlock a truly separate capability.
- DeepAgents tool binding is stricter than plain Python helpers: callable tools need descriptions or docstrings, otherwise the runtime fails before the first real step.
- For `create_cluster`, requiring the model to invent a new `cluster_id` is the wrong boundary; the store should generate the id deterministically when the mutation omits it.
- Deferred queue items need an explicit exit rule. Letting a deferred tweet be deferred again creates an easy infinite loop; treating the second defer as `done` without cluster closes the state machine safely for the first prototype.
- If queue completion and cluster membership updates are separate concerns at the prompt level, the model can close the queue while forgetting to add `tweet_ids`; binding that consistency into the completion tool keeps the final state coherent.

## Branch Note (2026-03-29)

- The product boundary matters more than branch history. Once `cluster_builder` became the main product, keeping the digest runtime around turned the repository into two overlapping systems instead of one clear tool.
- Removing whole dead paths is cheaper than carrying "maybe useful later" code, tests, and docs that force every reader to ask which runtime is real.
- With setuptools package discovery configured as `where = ["src"]`, removing old packages does not require switching to an explicit package list; the discovery rule still tracks the surviving packages cleanly.

## Branch Note (2026-03-29, later)

- The automatic digest fetch path is still a real runtime, not dead code. Pruning it just because `cluster_builder` is the main product boundary removes a workflow the user still depends on.
- When two automations share infrastructure but have different jobs, the simpler boundary is to keep both runners and make the README truthful, not to delete one and force the other to pretend to cover both use cases.
- For very large authenticated Twitter/X fetch runs, a small fixed handle window plus per-handle timeout and retry limits is a better first move than adding a queue or persistence layer.
- Persistent handle failures in a one-shot terminal run should become an explicit operator decision (`retry`, `go on`, or `stop`) after the current window finishes, not an automatic all-or-nothing abort.

## Branch Note (2026-03-29, fetch-layer rewrite)

- `ntscraper` + `twscrape` were removed entirely. Both relied on finding working Nitter instances for HTML scraping or managing an authenticated account pool via `twscrape`'s SQLite state; neither was reliable enough to run unattended.
- Nitter public instances (including nitter.net) return `200 + empty body` for all HTML endpoints when called programmatically — even with a real browser User-Agent via Playwright. The RSS endpoint (`/{handle}/rss`) remains served without restriction because it is designed for automated clients.
- The new primary fetch path is the X internal GraphQL API (`x.com/i/api/graphql/`) authenticated with the session cookies from the user's own Chrome browser. `browser-cookie3` reads `auth_token` and `ct0` from Chrome's SQLite store at runtime, so no separate credential management is needed.
- The X REST v1.1 `statuses/user_timeline.json` endpoint has been removed from `api.x.com`. The correct internal path is the GraphQL `UserTweets` operation under `x.com/i/api/graphql/`.
- GraphQL query IDs and the bearer token are embedded in X's deployed JS bundle and change with every frontend deploy. The fetch layer caches them in-process, falls back to known-good defaults, and automatically refreshes from the live bundle on 400/404 responses so the code stays current without manual maintenance.
- Thread reconstruction is done locally: `UserTweets` returns `in_reply_to_status_id_str` on every tweet, so a single timeline fetch is enough to reconstruct all self-reply chains within the fetched window without additional per-thread requests.
- Nitter RSS (`twitter_nitter_rss.py`) is kept as a fallback for environments where Chrome cookies are unavailable. It returns one Thread per tweet with no chain reconstruction; the digest pipeline handles single-post threads correctly.
- The Playwright-based scraper (`twitter_nitter_playwright.py`) was removed because even headless Chromium receives empty pages from Nitter status endpoints, making it equivalent to a plain `requests` call with more overhead.
