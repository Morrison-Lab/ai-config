# wrap-up — verify state, report, then UMS

Close out a work session cleanly: confirm where everything *actually* landed, report it with clickable links (surfacing anything still open), and capture what was learned before the context is gone.

Synonyms: `done` — a plain “are we done?” entry point that routes here; and `merged` — routes here too, and can name the just-merged PR to anchor the summary (e.g. `/merged #74`). (Distinct from `post-merge`, which wraps up a single just-merged PR rather than the whole session.)

## When this fires

- “wrap up”, “wrap up the session”, “finish up”, “let’s close out”, “done”, “all done”, “are we done?”
- The end of a multi-PR / multi-issue session.

## Procedure

### 1. Verify state — never assume

Don’t report from memory or assume a merge did/didn’t happen — query each thing fresh (this is the **never assume; always verify** rule applied to closing out). Commands below are annotated with their abstract operation token — resolve to your model’s tool via [`tool-mappings.md`](../../tool-mappings.md) instead of the `gh` command shown if this session doesn’t have `gh`:

``` bash
gh pr list --state open --json number,title,headRefName,author,mergeable,mergeStateStatus,comments \
  --jq '.[] | "#\(.number) [\(.author.login)] \(.title) [\(.mergeable)]"'   # LIST_PRS
gh issue list --state open --json number,title --jq '.[] | "#\(.number) \(.title)"'   # LIST_ISSUES
git status --short                         # uncommitted work?
git worktree list                          # leftover worktrees (agent isolation / session-lock)?
git log --oneline -5 origin/main           # what actually landed on main
```

- For every PR/issue you touched, confirm its real state with `gh pr view <N> --json state,mergedAt` (or `gh issue view`; abstract tokens: `VIEW_PR` / `VIEW_ISSUE`). A PR you think you left open may have been merged by the user, and vice-versa.
- If the session touched **other repos** (e.g. an upstream dependency), check those too — `gh pr list --repo <owner>/<repo> --state open --json number,title,headRefName,author,mergeable,mergeStateStatus,comments` (`LIST_PRS`).
- **Merge conflict sweep.** Before closing out, check every open PR’s `mergeable` field. For each PR with `mergeable == "CONFLICTING"` **or `"UNKNOWN"`** (see `resolve-conflicts`, “Verify before you act” — `UNKNOWN` can mean GitHub hasn’t finished computing yet), verify with `git merge-tree --write-tree origin/main origin/<branch>` (git ≥ 2.38) before acting, then check claim status (most recent comment) and fix confirmed conflicts using the cascade procedure in `post-merge` step 1.5 (claim → isolated worktree → merge main → `resolve-conflicts` skill → push → unclaim). Don’t leave conflicting PRs behind when wrapping up — they block whoever works the queue next.

### 2. Surface anything still open or dangling

List, don’t bury:

- **Open PRs** — every one, linked. Flag any you didn’t expect (e.g. a `@claude`-bot-opened PR) instead of silently passing over it.
- **Open issues**, **uncommitted working-tree changes**, **unmerged local branches**, and any **deferred follow-up issues** filed this session.
- **Leftover git worktrees** — agent isolation and `session-lock` leave worktrees behind (esp. ones whose PR already merged). Flag them and offer to run `clean-worktrees` (`cw`) to sweep the dead ones.
- Never report “all done” while something is open — name it and say whose call it is (e.g. “PR \#25 is the bot’s; yours to merge or close”).

### 3. Report a linked final summary

- **Run the `pr-status-all` skill** to produce the report’s PR table. This is a standing user mandate (2026-08-25): every session end or clean stopping point gets a whole-queue dashboard, not just a list of the PRs this conversation happened to touch. Respect that skill’s own Safety Cap — a queue over 10 open PRs gets its condensed table, not a skipped one.
- Every PR/MR/issue number in the table is a markdown link (repo policy — never a bare `#N`).
- A Pacific-time timestamp (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`; the explicit `TZ` enforces PT on a machine set to any other zone) so “as of when” is unambiguous when the user re-reads it later.

### 4. Run a UMS review, then close with the right signal

Run the full `ums` procedure (invoke the `ums` skill by name): scan the session for mistakes-corrected, new user preferences, tool quirks, and skill gaps — including whether `spot-skill-opportunities` flagged a recurring pattern during the session that’s still unbuilt; update the relevant memory files and skill definitions; commit via a **branch + PR** (not direct to `main`). If nothing durable emerged, say so explicitly rather than manufacturing edits.

#### Closing checklist

**Pause point: after the UMS pass above, before the closing signal or any `/clear` flag.** Do-Confirm; per [`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md). It sits here rather than in step 3 because every item confirms work from an *earlier* step — a checklist placed before the step it checks is a forward reference, not a confirmation.

**Killer item: step 1’s state sweep actually ran** — the open-PR and open-issue queries per repo, `git status`, local branches, worktrees — and the step 3 report was built from *its output*, not from recollection. Marked because recollection covers only the PRs and branches this conversation created, which is precisely the blind spot: a bot-opened PR, a leftover harness branch, or another session’s PR in the same repo never entered the conversation, so nothing about them feels outstanding. The recorded failure is a clean stopping point flagged twice on the strength of “my three PRs are merged”, with the sweep then finding a stale draft PR and an unused branch.

Everything the sweep surfaced is named in the report, including anything unexpected, with whose call it is.

The UMS pass above ran, or nothing durable emerged and that is stated explicitly — a `/clear` flag that has to mention an owed UMS pass is a flag raised too early.

**Then close the reply with an explicit stopping-point statement (the last message you post before stopping should always state whether or not this is a clean stopping point for the session):**

- **Clean stopping point reached** (nothing open or pending) — end with an explicit stopping-point statement, e.g. `**Stopping Point**: Clean stopping point reached` (“This session is at a good stopping point.”). A silent trailing summary leaves the user unsure whether you’re actually done or just paused.
- **Not a clean stopping point** (something open or in flight) — an ambiguous review item, a deadlock needing a human reviewer, pending CI/review jobs, unmerged PRs, or a choice only the user can make — state explicitly `**Stopping Point**: Not a clean stopping point — [reason/open items]`, and end the reply **with the open question(s) / pending tasks**, last and clearly visible.

## Relationship to other skills

- **`record-learnings`** (continuous) and **`ums`** (the learnings checkpoint, which this embeds as step 4) — `wrap-up` is their session-level bookend.
- **`spot-skill-opportunities`** — step 4’s UMS pass checks whether it flagged a recurring pattern during the session that’s still unbuilt.
- **`pr-status-all`** — step 3’s PR table comes from this skill, not from a hand-built list of the session’s own PRs. See its Safety Cap for what happens on a large open-PR queue.
- **`checkpoint`** / **`compress-session`** — narrower-scoped snapshots taken *during* a session (a task-phase snapshot, a pre-compaction distillation); `wrap-up` is the full session-level close-out these feed into, not a replacement for them.

## Notes

- Wrap-up reports PR/issue state and, where needed, resolves merge conflicts in unclaimed conflicting PRs (step 1). It does **not** merge PRs — merging stays the user’s call unless they ask.

Back to top
