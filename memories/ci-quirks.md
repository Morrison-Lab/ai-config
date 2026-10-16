# CI and reviewer quirks seen in the course repos

Measured in the Machine Learning course project's repos (lds, mlg, macros, pds, sds), 2026-10-12 to 2026-10-16.
Merge mechanics are in [`cloud-session-merge-gate.md`](cloud-session-merge-gate.md).

## Every Actions job fails in seconds

- Every workflow failed in 2-3 s with zero steps and a 404 on the log URL, on main and PRs alike (lds, 2026-10-16 about 08:24 UTC;
  lds#1058 at about 01:30 PDT).
  A one-line comment edit failed while the previous head had passed 15 minutes earlier.
  It is an account or Actions-side limit that Ezra fixes ("try again", 08:38 UTC), not a code defect, so no push fixes it.
- `rerun_failed_jobs` failed the same way for about 10 minutes.
  A full `gh api -X POST repos/OWNER/REPO/actions/runs/ID/rerun` on each run succeeded once Actions recovered.
- **Do:** confirm the jobs have no steps, post one PR comment saying so, re-run each failed run once, then retry promptly when Ezra says "try again".
- **Don't:** push commits to "kick" CI, or schedule a long wait.

## Claude review after a quota failure

When the gha `Claude Code Review` run hits a 429 quota, the `claude-review` job "succeeds" with a quota-exhausted result and only `require-clean-verdict` fails.
`rerun_failed_jobs` then re-runs just the verdict job against that stale result (`QUOTA_EXHAUSTED=true`), which fails again at once.

- **Do:** use `rerun_workflow_run` (the whole run) after a quota reset or token rotation, or push a new commit (pds#177 to #184, sds, 2026-10-16).
- **Do:** compare a caller's `permissions:` with the reusable workflow's, since a reusable job cannot exceed its caller (sds#238 lacked `actions: read` for `cleanup-pr-previews`).
- **Do:** after pushing review fixes, comment `/review` again, because a Claude verdict is tied to a head SHA.

## Flakes in `check-student-copy.yml` (mlg, 2026-10-13)

- The `check` job can fail on a 403 from GitHub's releases API while installing TinyTeX.
- The `pages` job can fail in about 2 s with no steps.
- `rerun_failed_jobs` once cleared both.
  A `pages` failure on a main push does not mean the render failed; read the `check` job.

## Cross-harness review tooling

- OpenCode `kimi-k3` returns empty text for very large diffs (91 KB on mlg#99) and sometimes for 25-40 KB parts.
  Split by file and treat an empty reply as "no review", not "no findings".
  Where it did answer on mlg it found three real slips in the reports.
- OpenCode Go via curl needs `--max-time` of at least 1500 s for reasoning models;
  400 s cut off reasoning-only streams (2026-10-15).
- OpenCode Go has a weekly limit (see [`delegate-to-opencode`](../skills/delegate-to-opencode/SKILL.md)).
  Look at the raw SSE file before blaming a model: an exhausted quota returns `GoUsageLimitError` in about 2 s with zero bytes parsed.
  A 502 "upstream request failed" is flaky, so retry other models;
  free OpenCode models refuse calls from outside the OpenCode app.
  The fallback that worked was routing the head to the Argon Remote Control session through the coordinator.
- Recurring kimi-k3 false positives on pds and sds PRs are rebutted in a PR comment, not prompted away: the `pds/_subfiles/...` include "mismatch" (pds is a symlink to the repo root), a "graded-answer leak" (those repos have no graded items), and inline `{r}` calls.
  Its real nits were worth fixing: softened overclaims, values computed in the visible chunk rather than a hidden one, and `which.min` ties.
- Every head change, even a main merge, needs a fresh cross-harness review of the shipping head.
  Batch nit fixes into one push, then bring the branch level with main last (`update_pull_request_branch` pinned with `expectedHeadSha`).
  Check `git rev-list --count origin/<branch>..origin/main` after fetching the branch ref, since a stale local ref gives a false "behind".
- After a merge, the auto-mode classifier ("Merge Without Review") refused even read-only curl polls of main's check runs on macros.
  Use MCP tools or ask the coordinator instead of retrying.

## Smaller tool quirks

- `mcp__github__actions_list` ignores `per_page` and returns very large output; prefer `get_check_run` on a known id.
- Resolving a review thread from a cloud session is recorded in [`github-remote-sessions`](github-remote-sessions.md) (CCR route).
- MathJax lacks `\providecommand`, so a macro-equivalence harness must map it to `\newcommand` and convert definitions line by line.
- Slide decks: a theorem subfile included right under a section heading must not start with a slide break, or the heading gets an empty slide (pds#154).
- A shared macro added to `Morrison-Lab/macros` does not move a consumer's `latex-macros` gitlink, and PR previews skip the PDF. lds main went red on the PDF publish ("Undefined control sequence \dataset", 2026-10-15) until lds#999 bumped the pin.
  When a PR uses a recent macro, check the pin contains it (`git -C latex-macros merge-base --is-ancestor <macro-commit> HEAD`), and read the publish run on every merge commit.
- The lds `Build / build` job takes about 40 minutes and the fully-clean gate stays red until it ends, so wait for the check-suite wake rather than polling.
- A new header partial in a repo whose `.gitignore` lists `*.html` needs a `!name.html` line, or it silently never commits (sds#217).
