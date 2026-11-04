Never answer "I can't do that from this session" when a way exists to do it.

Ezra, 2026-11-04 (lds thread "Find Smarket data with actual dates"): "never make an excuse like this", then "never make this type of excuse again".
The excuses were that a repository was "not in this session's repo scope", that hosts were "blocked in my sandbox", and a fact given "as I remember" when it could have been checked.

Before reporting any resource as unreachable, try each of these and say which you tried:

- A repository outside the session's scope: attach it with `add_repo`, then clone it.
- A blocked host: look for a GitHub-hosted mirror (`raw.githubusercontent.com/cran/<package>` serves a CRAN package's data), a CRAN or PyPI package that bundles the data, or an allowed API.
- A host that has no mirror: add it to [`d-morrison/stats-allowlist`](https://github.com/d-morrison/stats-allowlist) (`claude-allowlist.txt` and `allowlist.txt`) and give Ezra the lines to paste into the session's settings.
- Work that needs Ezra's machine: start a Remote Control session, which is standing-approved.

State a checkable fact only after checking it, never "as I remember".
If every route fails, report each route and why it failed, never the first failure alone.

Why this is prose and not a hook: whether another route exists cannot be decided from a transcript.
The existing guards cover the decidable parts: `flag-blocker-without-retry.py` flags a denial handed to the user with no retry, and `flag-book-unavailable-without-library-search.py` flags a book called unavailable without a library search.
