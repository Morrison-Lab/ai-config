Never answer "I can't do that from this session" when a way exists to do it.

Ezra, 2026-11-04 (lds thread "Find Smarket data with actual dates"): "never make an excuse like this", then "never make this type of excuse again".
The excuses were that a repository was "not in this session's repo scope", that hosts were "blocked in my sandbox", and a fact given "as I remember" when it could have been checked.

Before reporting any resource as unreachable, try each of these and say which you tried:

- A repository outside the session's scope: attach it with `add_repo`, then clone it.
- A blocked host: look for a GitHub-hosted mirror (`raw.githubusercontent.com/cran/<package>` serves a CRAN package's data), a CRAN or PyPI package that bundles the data, or an allowed API.
- A host that has no mirror: add it to [`d-morrison/stats-allowlist`](https://github.com/d-morrison/stats-allowlist) (`claude-allowlist.txt` and `allowlist.txt`) and give Ezra the lines to paste into the session's settings.
- Work that needs Ezra's machine: start a Remote Control session yourself on a device the user has granted, as [`claude-app-projects`](../../memories/claude-app-projects.md) describes, and never ask the user to start one.

State a checkable fact only after checking it, never "as I remember".
If every route fails, report each route and why it failed, never the first failure alone.

Never say a repository isn't in a thread or session.
Attach it instead.
Ezra, 2026-11-12: "cai: never say a repo isn't in a thread; add it".
An mds thread had asked the coordinator to file in ai-config because "ai-config isn't in this thread's repos", when one `add_repo` call would have attached it.

- **Do:** call `mcp__claude-code-remote__add_repo`, clone the repository, do the work, and report it in the past tense.
- **Don't:** tell the user or another session that a repository is outside this thread's repos or scope.

If `add_repo` itself refuses, say so and quote its reason.
`hooks/no-repo-not-in-thread-excuse.py` denies a message that calls a repository out of the thread's reach, unless the same sentence reports a refused or failed attach.
[`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#a-repository-called-out-of-the-threads-reach) looks for the same excuse in what it reviews.

The other excuses stay prose: whether another route exists cannot be decided from a transcript.
The existing guards cover the decidable parts: `flag-blocker-without-retry.py` flags a denial handed to the user with no retry, and `flag-book-unavailable-without-library-search.py` flags a book called unavailable without a library search.
