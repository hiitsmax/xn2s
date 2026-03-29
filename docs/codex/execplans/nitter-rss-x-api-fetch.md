# Nitter RSS + X API Fetch Layer

This ExecPlan is a living document covering the full rewrite of the Twitter fetch
layer completed on 2026-03-29.

## Purpose / Big Picture

Replace the previous scraping stack (`ntscraper`, `twscrape`, Playwright) with a
two-tier fetch layer that is reliable enough to run unattended in a cron job:

1. **Primary** — X internal GraphQL API authenticated with Chrome session cookies.
   Returns full tweet text, full `in_reply_to` chains, and works without any
   separate API keys or account management.
2. **Fallback** — Nitter RSS feeds (`/{handle}/rss`).  Browser-free, no auth
   required.  Returns the first tweet of each thread only; no chain reconstruction.

## Progress

- [x] (2026-03-29) Diagnosed root cause of Nitter HTML failures: all instances
  return `200 + empty body` for HTML endpoints when called programmatically,
  including via headless Playwright.  RSS endpoints are unaffected.
- [x] (2026-03-29) Removed `twitter_nitter.py`, `twitter_nitter_net.py`,
  `twitter_twscrape.py`, `twitter_cookies.py` (old version) and their tests.
- [x] (2026-03-29) Created `twitter_nitter_rss.py`: RSS-based fetcher using
  `feedparser` + `requests`.  Tries `NITTER_INSTANCES` in order; first instance
  with a non-empty feed wins.  Feeds items to `Thread`/`Post` schema.
- [x] (2026-03-29) Discovered the X REST v1.1 `statuses/user_timeline.json`
  endpoint is gone (`404` on both `api.x.com` and `x.com/i/api/1.1`).
- [x] (2026-03-29) Discovered the X web app bearer token changed; fetched the
  current one dynamically from `abs.twimg.com/responsive-web/client-web/main.*.js`.
- [x] (2026-03-29) Discovered current GraphQL query IDs by regex-scanning the
  same JS bundle: `UserByScreenName`, `UserTweets`, `TweetDetail`.
- [x] (2026-03-29) Created `twitter_cookies.py`: extracts `auth_token` + `ct0`
  from Chrome via `browser-cookie3`; raises `XCookiesMissing` when absent.
- [x] (2026-03-29) Created `twitter_x_api.py`: GraphQL fetch + thread
  reconstruction + auto-refresh of bearer token and query IDs from bundle.
- [x] (2026-03-29) Updated `twitter.py`: X API primary, Nitter RSS fallback,
  `XCookiesMissing` triggers the fallback automatically.
- [x] (2026-03-29) Validated live: 18 threads across 3 handles in 7 s; thread
  reconstruction via `in_reply_to` chains confirmed correct.
- [x] (2026-03-29) Updated and passing tests (5/5) in `test_twitter.py`.

## Surprises & Discoveries

- **Nitter HTML is fully blocked.** Even with a realistic User-Agent and a real
  Playwright session, all tested Nitter instances return `200 + 39-byte empty HTML`
  for profile and status pages.  Only the RSS endpoint is served without
  restriction.  This rules out any HTML scraping approach without instance-specific
  cookies.

- **X REST v1.1 is gone.** `api.x.com/1.1/statuses/user_timeline.json` returns
  `{"errors":[{"code":34,"message":"Sorry, that page does not exist"}]}`.  The
  internal path `x.com/i/api/1.1/statuses/user_timeline.json` returns the same
  error.  The bearer token and cookie auth still work; the endpoint itself was
  removed.

- **Bearer token and query IDs change with each deploy.** The bearer token
  hardcoded from 2019 documentation (`AAAAAAAAAAAAAAAAAAAAANRILgAAAAA...`) is no
  longer valid.  The current token and the `UserTweets` / `UserByScreenName` query
  IDs must be read from the deployed bundle to stay current.

- **GraphQL response shape: `timeline` not `timeline_v2`.** When `withV2Timeline`
  is omitted from the variables, the response uses `timeline.timeline.instructions`
  not `timeline_v2.timeline.instructions`.  Removing the flag produces the correct
  shape.

- **`TweetWithVisibilityResults` wrapper.** Some entries in the `UserTweets`
  response wrap the tweet result in a `TweetWithVisibilityResults` dict rather than
  placing the legacy tweet directly at `tweet_results.result`.  The parser must
  unwrap this before accessing `.legacy`.

## Decision Log

- **Decision:** Use the X internal GraphQL API instead of REST v1.1.
  **Rationale:** REST v1.1 user timeline endpoint was removed.  The GraphQL
  surface used by the web app is the only available authenticated path.
  **Date:** 2026-03-29

- **Decision:** Refresh bearer token and query IDs from the live JS bundle rather
  than requiring manual updates.
  **Rationale:** Query IDs change on every deploy.  A hardcoded value would break
  silently roughly monthly.  Fetching from the bundle on first use and on 400/404
  keeps the code self-healing without any operator intervention.
  **Date:** 2026-03-29

- **Decision:** Keep Nitter RSS as fallback rather than making X API mandatory.
  **Rationale:** The fetch layer must work in CI environments where Chrome is not
  present.  Nitter RSS requires only `requests` + `feedparser` and no auth.  Single-
  post threads from RSS are handled correctly by the digest pipeline.
  **Date:** 2026-03-29

- **Decision:** Reconstruct threads locally from the timeline batch rather than
  fetching each thread's status page separately.
  **Rationale:** One `UserTweets` call returns `in_reply_to_status_id_str` on every
  tweet.  A second per-thread request would multiply latency by the number of
  threads.  The local reconstruction covers all chains within the fetched window
  (up to 40 tweets) without additional HTTP calls.
  **Date:** 2026-03-29

- **Decision:** Remove `twitter_nitter_playwright.py` after confirming it cannot
  retrieve status page content.
  **Rationale:** Playwright returns the same `200 + empty body` as `requests` on
  all tested Nitter instances.  The overhead of launching Chromium for zero gain is
  not justified.
  **Date:** 2026-03-29

## Module Map

```
src/xs2n/
├── twitter.py               # Public API. Tries X API; falls back to Nitter RSS.
├── twitter_cookies.py       # Chrome cookie extraction via browser-cookie3.
├── twitter_x_api.py         # X internal GraphQL: UserByScreenName + UserTweets
│                            # + in_reply_to thread reconstruction.
│                            # Auto-refreshes bearer token and query IDs from bundle.
└── twitter_nitter_rss.py    # Fallback: Nitter RSS feed parsing via feedparser.
                             # Single-post threads; no chain reconstruction.
```

## Fetch Flow

```
get_twitter_threads(handles_path, since_date)
    │
    ├─► get_chrome_x_cookies()
    │       browser-cookie3 reads Chrome's cookie DB for .x.com
    │       → {"auth_token": ..., "ct0": ...}
    │       XCookiesMissing → skip to fallback
    │
    ├─► get_x_api_threads(handles, since_date, cookies)      [PRIMARY]
    │       for each handle:
    │         _resolve_user_id()   → UserByScreenName GraphQL
    │         _fetch_raw_tweets()  → UserTweets GraphQL (up to 40 tweets)
    │         _build_threads()     → reconstruct chains via in_reply_to
    │       auto-refresh bearer + queryId from bundle on 400/404
    │
    └─► get_nitter_rss_threads(handles, since_date)          [FALLBACK]
            for each handle:
              try NITTER_INSTANCES in order
              feedparser.parse(response.text)
              → one Thread per RSS entry (no chain)
```

## Maintenance Notes

### When X breaks the fetch (symptoms: 401, 400, 404)

1. **401** — Chrome session expired.  Open x.com in Chrome and log in again.
   The cookies are read fresh at each run; no code change needed.

2. **400 or 404 on GraphQL** — Query IDs changed.  The module retries once after
   auto-refreshing from the live bundle.  If the retry also fails, run:

   ```bash
   uv run python - <<'EOF'
   import re, requests
   js = requests.get(
       "https://x.com",
       headers={"User-Agent": "Mozilla/5.0"},
   ).text
   bundle_url = re.findall(
       r'"(https://abs\.twimg\.com/responsive-web/client-web/main\.[^"]+\.js)"', js
   )[0]
   bundle = requests.get(bundle_url, headers={"User-Agent": "Mozilla/5.0"}).text
   for qid, name in re.findall(r'\{queryId:"([^"]+)",operationName:"([^"]+)"', bundle):
       if name in ("UserTweets", "UserByScreenName", "TweetDetail"):
           print(name, qid)
   EOF
   ```

   Update `_DEFAULT_QID_USER_BY_SCREEN_NAME` and `_DEFAULT_QID_USER_TWEETS` in
   `twitter_x_api.py` with the new values.

3. **Bearer token invalid** — Same bundle script above also prints the current
   bearer (the `AAAA…` string).  Update `_DEFAULT_BEARER` in `twitter_x_api.py`.

### When Nitter RSS breaks (symptoms: empty threads from fallback)

Check if the current `NITTER_INSTANCES` list in `twitter_nitter_rss.py` still has
working instances.  Test with:

```bash
curl -s "https://nitter.net/NASA/rss" | head -30
```

Add or reorder instances in `NITTER_INSTANCES` to put the most reliable ones first.
Current list as of 2026-03-29:

| Instance | Status (2026-03-29) |
|---|---|
| `xcancel.com` | Returns entries but link URLs lack tweet IDs — effectively broken |
| `nitter.net` | RSS working; HTML endpoints blocked |
| `nitter.privacyredirect.com` | No response |
| `nitter.poast.org` | No response |
| `lightbrd.com` | No response |
| `nitter.space` | No response |
| `nitter.tiekoetter.com` | No response |
| `nitter.catsarch.com` | No response |

## Outcomes & Retrospective

The rewrite landed in one session.  The new stack is smaller (four modules instead
of six), has no external state files or account pools to manage, and requires only
that the user be logged in to x.com in Chrome — a condition that is trivially true
for the intended operator.

Thread reconstruction from the timeline batch works without per-thread requests and
covers all self-reply chains within the 40-tweet fetch window.  The fallback path
(Nitter RSS) ensures the digest can still run in environments without Chrome.
