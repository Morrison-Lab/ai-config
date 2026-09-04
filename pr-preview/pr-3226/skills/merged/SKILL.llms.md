# merged (alias for `wrap-up`)

This is a **synonym for [`wrap-up`](../../skills/wrap-up/SKILL.llms.md)** — invoking `/merged` runs the wrap-up procedure unchanged. The two are fully interchangeable for dispatch: any phrasing that fires `wrap-up` (“wrap up”, “finish up”, “are we done?”) fires `merged` too, and both run the same procedure. That is why this skill’s `description` repeats those triggers. The one extra affordance is the optional PR indication below.

**Do this:** read [wrap-up](../../skills/wrap-up/SKILL.llms.md) and follow its instructions exactly. Everything that skill says — verify the real state of every PR/issue/branch/working tree, report a linked final summary that surfaces anything still open, then run a UMS review to persist what was learned — applies unchanged.

Keep the logic only in `wrap-up`; this file is just the `/merged` entry point so the two names stay in sync.

## Optional: name the PR that just merged

In a multi-PR session, `/merged` can be given a specific PR — e.g. `/merged #74`, “merged 74”, or “merged the refactor PR”. Treat that PR as the **anchor** for the wrap-up:

- Confirm its merge actually landed first — `gh pr view <N> --json state,mergedAt,mergeCommit` (never assume).
- Lead the summary with it, since that merge is what prompted the wrap-up.
- Then run the rest of `wrap-up` over the **whole** session: other open PRs/issues, uncommitted work, unmerged branches, leftover worktrees, then UMS.

The named PR anchors the report; it does **not** narrow the wrap-up to that one PR. With no PR given, `/merged` is a plain session-level wrap-up.

> `/merged` routes to [`wrap-up`](../../skills/wrap-up/SKILL.llms.md), not [`post-merge`](../../skills/post-merge/SKILL.llms.md). `post-merge` wraps up a single just-merged PR; `wrap-up` closes the whole session.

Back to top
