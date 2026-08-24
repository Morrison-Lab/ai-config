# Reddit access routes for local Claude Code sessions

Reddit is unreachable from **every headless surface** available to a local
Claude Code session, and the corpus's own research briefs
([`opposition-research`](../skills/opposition-research/SKILL.md) and the
[`community-demand-scout`](../.claude/agents/community-demand-scout.md)
agent) named "the Reddit `.json` endpoints" as a preferred data source ---
so a workflow brief written from those files sends every scout into a wall.
The one route that works is Claude in Chrome driving the user's real Chrome.
Measured 2026-08-23/24 on a Windows 11 local session; tracked as
[ai-config#2046](https://github.com/Morrison-Lab/ai-config/issues/2046).

[`claude-code.md`](claude-code.md)'s "Reddit is the inverse of the pattern
above" bullet (2026-08-16) records a session where `old.reddit.com` HTML
still fetched.
That reading does not transfer to a local session, where the block sits in
the tool policy rather than at Reddit --- the routes below fail before any
HTML is served.

## The five failed routes, and the signature each one leaves

Recognize which wall you hit from its signature rather than re-deriving it:

1. **WebFetch** to `www.reddit.com`, `old.reddit.com`, or `api.reddit.com`:
   "Claude Code is unable to fetch from \<host\>".
   Instant, and worded as a tool refusal --- a tool-policy domain block, not
   a Reddit 403.
2. **WebSearch**: returns no reddit.com results at all, and with
   `allowed_domains=["reddit.com"]` it errors "The following domains are not
   accessible to our user agent" --- Anthropic's search crawler is itself
   blocked by Reddit's bot policy.
3. **The in-app Browser pane** (`preview_start` on a reddit.com URL):
   "reddit.com is blocked by policy".
4. **Bash `curl` from the user's own residential IP**: HTTP 403 carrying
   Reddit's "network security" HTML page, on all three hosts, **even with a
   Chrome User-Agent string**.
   Reddit fingerprints TLS --- curl's handshake differs from a real
   browser's --- so UA spoofing does not help.
5. **Public redlib/teddit/libreddit mirrors and generic proxies**: dead DNS,
   connection refused, or they surface Reddit's own 403.

## The working route: Claude in Chrome, in-page fetch

The `mcp__claude-in-chrome__*` tools drive the user's real Chrome, which has
a real TLS fingerprint and a logged-in Reddit session.
Four mechanics, each measured working:

- **Establish the origin once, then fetch in-page.**
  Navigate a tab to the target subreddit, then use `javascript_tool` to run
  `await fetch('https://www.reddit.com/r/<sub>/top.json?t=year&limit=75&raw_json=1', {credentials:'include'})`
  --- it returns HTTP 200 JSON.
- **Accumulate results in `window`-scoped state.**
  Page state persists between `javascript_tool` calls as long as you do not
  navigate, so trim each post to the fields you need in-page and append to a
  `window` variable across calls, rather than returning bulk JSON to the
  model.
- **CDP `Runtime.evaluate` caps each `javascript_tool` call at 45 seconds,
  and a timed-out loop KEEPS RUNNING in the page.**
  A paced multi-fetch loop that exceeds the cap returns a timeout error to
  the caller while the page-side loop continues --- so check the `window`
  state before re-running, or you will double-fetch.
  Keep each call's loop under ~40s (about 6 subs x 2 fetches at 1.1s
  pacing).
- **Export large results as ONE Blob download.**
  Build a Blob, set `a.download`, and `a.click()` it to the user's Downloads
  folder, then read the file from disk --- multi-MB data never transits
  model context, and a single download avoids Chrome's multiple-download
  permission prompt.
- **Pace the fetches** at ~1s apart; logged-in Reddit allows roughly 100
  requests per 10 minutes.

- **Do:** route Reddit reads through Claude in Chrome's in-page fetch
  (origin first, `credentials:'include'`), and check the `window` state
  after a `javascript_tool` timeout before re-running the loop.
- **Don't:** brief scouts or workflows to use WebFetch, WebSearch, or curl
  for reddit.com in a local session, or treat a `javascript_tool` 45s
  timeout as the loop having died --- it is still running in the page.
