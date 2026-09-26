# Git fetch

Fetch-specific behavior: what `git fetch` writes to `FETCH_HEAD`, which ref a later read resolves to, and how a fetch that fails or is dry-run differs from one that succeeds.
Split out of [`git.md`](git.md) (ai-config#694 pattern) at the 1250-line gate.

## `FETCH_HEAD` is a file git replaces, and `rev-parse` reads its FIRST line

Measured git 2.43.0.

A multi-ref fetch writes every ref, one per line, in the order named, and `git rev-parse FETCH_HEAD` returns the **first**.
So name the ref you want first; a multi-ref fetch is not itself the hazard.
A **later** fetch is, because it replaces the file.

Each line is `<sha>` TAB `[not-for-merge]` TAB `<description>`, so `cut -f2` reaches the middle field rather than the description.

A fetch naming a missing ref truncates `.git/FETCH_HEAD` to zero bytes, and `rev-parse --verify` then fails loudly rather than returning a stale value --- the safe direction, and where the routine `couldn't find remote ref` case after a squash-merge auto-delete lands.

`--dry-run` is the unsafe one: it prints `* branch <ref> -> FETCH_HEAD` and writes nothing, so a read afterwards answers the *previous* fetch while git has just said otherwise.
`--no-write-fetch-head` also preserves the prior value, but claims nothing.

Resolve and **print** the SHA in the same command as the fetch, then use the printed value: [`fully-clean`](../shared/workflow/fully-clean.md) records that a shell variable does not survive into a later tool call.

[`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)'s "A ref that resolves to a different commit than it did a moment ago" carries the worked case and the pattern/anti-pattern pair (ai-config#3704).
