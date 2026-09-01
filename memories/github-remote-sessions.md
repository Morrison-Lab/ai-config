# GitHub access from bash in remote/web sessions

What a remote or web session can reach on GitHub from bash when `gh`/`glab` are absent: session-scope 403s, the MCP-then-`add_repo`-then-`git ls-remote` ladder, the proxy's push-but-not-delete rule, and GitHub Pages policy denials.
Split out of [`github.md`](github.md) (ai-config#694 pattern) at the 1200-line gate.

- There is no `gh`/`glab` CLI in these sessions, so `mcp__github__*` is the normal path for anything the API would answer.
  - **The REST API itself is not necessarily unreachable from bash, though --- it can be scope-limited instead, so test rather than assume.**
    This entry asserted flatly that no REST API was reachable from a Bash/Monitor script until 2026-07-26, when a session found otherwise.
    A plain `curl` to `api.github.com` went through the agent proxy and answered normally for a repo in that session's GitHub scope:
    ```
    $ curl -sS -o /dev/null -w '%{http_code}\n' \
        https://api.github.com/repos/d-morrison/altdoc
    200
    ```
    For a repo outside the scope it returned `403`, with a body naming the scope as the reason rather than a generic denial:
    ```
    $ curl -sS https://api.github.com/repos/actions/checkout
    {"message":"GitHub access to this repository is not enabled for this
     session. Use add_repo to request access. ..."}
    ```
    Sandbox policy varies, so the older claim may well have been true of the environment it was written in --- which is the point: check the behavior in the sandbox you are actually in.
    The consequence bullet below, that a background Monitor cannot poll PR state, rests on the same assumption and deserves the same re-check before you rely on it either way.
  - **A repo the REST API refuses may still be reachable through `mcp__github__*` --- measure both surfaces rather than assuming one scope.**
    They shared a scope in the session that wrote this and did not in a later one;
    see [`github-mcp-tools.md`](github-mcp-tools.md)'s org-gate entry.
    `git ls-remote https://github.com/<owner>/<repo>` works against any public repo whatever the scope is, because it is a git operation and the proxy passes those through unchanged.
    That answers every ref question the REST API would have --- which tags and branches exist, and which shas they point at --- and that is usually the whole reason an out-of-scope repo came up.
    So the ladder is: MCP tools, then `add_repo` if the repo genuinely needs API or write access, then `git ls-remote` for anything that is only a ref lookup.
    See [`git-tags.md`](git-tags.md)'s "Resolving a tag to a COMMIT sha" for the exact refspec form to ask for. (d-morrison/altdoc#65, 2026-07-26: SHA-pinning seven third-party actions needed tag shas from `actions/`, `r-lib/`, `r-hub/`, `quarto-dev/`, and `JamesIves/`, none of them in session scope, and `add_repo` would have been five pointless scope grants for five ref lookups.)
  - **The `github.com` web host 403s on scope exactly as `api.github.com` does, so `curl -I https://github.com/<owner>/<repo>` answers nothing about whether the repo exists.**
    The bullet above covers the API host;
    the web host is the one reached for when the question is existence rather than data, and it is the likelier mistake because a `403` there reads as GitHub refusing rather than as the proxy refusing.
    Both hosts return the proxy's verdict on **session scope**, so a repo can be public, healthy, and 403 --- and the same probe returns 200 for a repo that is merely in scope, which makes the pair look like a real signal about the repos rather than about the allowlist.
    `git ls-remote` is the instrument, per the ladder above, and it discriminates every case.
    Measured 2026-08-09, from a session scoped to `Morrison-Lab/ai-config` and `Morrison-Lab/wai`:

    | repo | `curl -I` | `git ls-remote <url> HEAD` |
    |---|---|---|
    | `d-morrison/ai-config` | 403 | `7d843650...` |
    | `Morrison-Lab/ai-config` | 200 | `7d843650...` |
    | `d-morrison/macros` | 403 | `8ce5d0cf...` |
    | `Morrison-Lab/macros` | 403 | `fatal: could not read Username` |

    Read the `curl` column as a table of the allowlist and nothing else: the one 200 is `ai-config`, which is in scope.
    Two things the `ls-remote` column settles that no `curl` here could.
    An **identical HEAD under two owner spellings** is consistent with a live rename redirect and, paired with the 403/200 split in the `curl` column above, is strong circumstantial evidence for one --- but it is not proof by itself: two independently reachable repos (a fork, a mirror) can share the same HEAD object ID with neither URL redirecting to the other.
    Confirming an actual redirect still needs separate HTTP evidence (a 3xx/canonical-URL response, or `gh repo view <old-slug> --json nameWithOwner` per [`github.md`](github.md)'s "gh --- stale remote URL causes cryptic `gh pr create` failure" detector).
    The advantage over the `raw.githubusercontent.com` probe in [`gh-cli.md`](gh-cli.md)'s "`raw.githubusercontent.com` FOLLOWS repository-rename redirects" bullet is narrower than "proof": that probe has to be run under the *new* name with a known-moved control or it answers backwards, whereas comparing two shas needs no control at all --- it just settles less on its own.
    And `fatal: could not read Username for 'https://github.com'` is how an **absent or private** repo presents on an anonymous read: git falls back to asking for credentials rather than reporting a 404.
    Set `GIT_TERMINAL_PROMPT=0` so that case fails immediately instead of blocking on a prompt.
    Note the pair `d-morrison/macros` resolving while `Morrison-Lab/macros` does not --- the opposite direction from `ai-config`, which is why a blanket owner rewrite across both would break a working reference.
    (`Morrison-Lab/wai#54`, 2026-08-09: a `.gitmodules` still naming `d-morrison/ai-config` resolved only through the rename redirect, so nothing was visibly broken;
    `macros` was correctly left pointed at `the repository owner`.)
- **The proxy allows branch creation/push but BLOCKS branch deletion.**
  Pushing a *new* branch (even one other than the harness-assigned `claude/...`) works, but a delete push --- `git push origin --delete <b>` or `git push origin :<b>` --- is rejected.
  Observed verbatim: "send-pack: unexpected disconnect" / "remote end hung up", then a misleading "Everything up-to-date" (the proxy returns that no-op message instead of a normal `failed to push some refs` error), but the command still exits non-zero.
  So a throwaway branch (e.g. a push-capability probe) can't be cleaned up from the session;
  delete it via the GitHub UI/API, or just leave it if it's identical to `main` and has no PR. (Seen on ai-config, 2026-06-28.)
- **GitHub Pages sites (`<owner>.github.io`, incl. `rossjrw/pr-preview-action` PR-preview links) are policy-blocked in at least some sandboxes** --- both WebFetch and a direct `curl`/CONNECT through the agent proxy get a `403` (`gateway answered 403 to CONNECT (policy denial)`, confirmed via `curl -sS "$HTTPS_PROXY/__agentproxy/status"`).
  Don't retry or assume it's transient --- treat it the same as an unavailable preview and fall back to rendering the chapter locally (rme's own CLAUDE.md already names this fallback for "no preview has deployed yet");
  it also applies when the preview exists but the sandbox can't reach it.
  - **But try the `gh-pages` branch first --- the deployed HTML is usually readable through the authenticated MCP tools even when the served site isn't.**
    `rossjrw/pr-preview-action` commits each build to `gh-pages` (the action's `preview-branch` input) under `pr-preview/pr-<N>/` (its `umbrella-dir` input, with `pr-preview` and the triggering PR's number as the built-in defaults), so `mcp__github__get_file_contents` with `ref: refs/heads/gh-pages` and `path: pr-preview/pr-<N>/<page>.html` returns the exact bytes the blocked URL would have served **on a repo using the action's defaults**.
    A repo that overrides `preview-branch`, `umbrella-dir`, `pr-number`, or `pages-base-path` needs the same values read from its own workflow file first --- the defaults are a starting guess, not a guarantee.
    That reaches the *real rendered artifact*, which a local re-render only approximates, and it needs no Quarto toolchain.
    Large pages exceed the tool's token cap and get spilled to a file --- grep that file rather than reading it whole, and diff byte counts across two fetches to confirm you're looking at a genuinely new build rather than an unchanged one.
    Check the branch's own commit log (`mcp__github__list_commits` with `sha: gh-pages` --- the `LIST_COMMITS` operation in [`tool-mappings.md`](../tool-mappings.md), verified by use in the session below) to see which build is actually deployed before drawing conclusions;
    a preview comment's timestamp can precede the deploy of the commit you care about. (`UCD-SERG/serocalculator#392`, 2026-07-25: used this to verify six new topics appeared in a rendered altdoc sidebar, counting occurrences before and after the fix, after both `curl` and `WebFetch` 403'd.)
- **[`gh-cli.md`](gh-cli.md)'s "A session's egress proxy can block GraphQL entirely" bullet is not `gh`-specific -- the same 403 answers a raw `curl` to `https://api.github.com/graphql` in a session with no `gh` binary at all.**
  Measured 2026-09-01, no `gh` on `PATH`: `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/repos/Morrison-Lab/wai/pulls/173` returned `200`, while the same token against `https://api.github.com/graphql` returned the identical `403` body that bullet quotes.
  So this is not a quirk of the `gh` client, it is a property of the session's egress policy, and it confirms the mechanism in exactly the session class -- remote/web, no `gh` -- where `gh api graphql` was never available to test it with.
  Since `gh pr view --json` depends on GraphQL fields for several of them, it is unavailable here even indirectly, not merely absent as a binary; don't assume plain REST shares its fate, since the REST call above succeeded in the same session.
  `scripts/build-pr-payload.py` (ai-config#2908) assembles a `check-pr-fully-clean.py` `--from-json` payload from REST alone for exactly this case -- run it instead of hand-transcribing MCP tool output into the payload JSON, which is slow and error-prone:
  ```
  python3 scripts/build-pr-payload.py OWNER/REPO N out.json
  python3 scripts/check-pr-fully-clean.py N -R OWNER/REPO --from-json out.json
  ```
- Consequence: you CANNOT poll PR review/CI state from a background Monitor.
  Rely on `mcp__github__subscribe_pr_activity`, which delivers review comments and CI *failures* --- but NOT CI success, new pushes, or merge-conflict transitions.
  A self-check-in scheduler may be absent: rme's instructions reference `send_later` (from the `claude-code-remote` MCP server), and the harness may expose its own (e.g. `ScheduleWakeup`) --- but in this remote rme session ToolSearch surfaced neither, so you can't arm the safety re-poll the watch-guidance suggests.
  Say so rather than implying it's armed.
- rme runs TWO review workflows per push: `claude-code-review.yml` (sticky comment, gives the "ready to merge" verdict) and `claude.yml` agent post-step (separate findings).
  They can DISAGREE --- one says clean while the other finds nits.
  Reconcile BOTH before calling a PR clean;
  the agent post-step tends to drip 1-2 pre-existing cosmetic nits per round.
  That drip is a reason to keep iterating, never a reason to stop or to ask whether to stop --- see `skills/ardi/SKILL.md`, "Stopping conditions".
