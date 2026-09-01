Before scaffolding a new AI tool — a skill, an agent, or any other
harness-registered file (`skills/<name>/SKILL.md`, `.claude/agents/<name>.md`,
etc.) — check **open PRs**, not just local branches and worktrees, for an
in-progress draft that already covers the concern.

A local branch/worktree scan misses work another session already pushed and
opened a PR for. Check both this repo's and (when the corpus spans repos, as
`Morrison-Lab/ai-config`'s skills do) any sibling repos in scope:

```bash
gh pr list --state all --search "<keywords> in:title,body"
```

**`--state all`, not `--state open`** --- see "Both checks come back empty when
the work is already DONE" below for why.
The prescribed query has to carry the fix as well as the prose, or a reader
who copies the command never reaches the explanation.

In a remote/web session without `gh`, use the GitHub MCP equivalent
(`mcp__github__list_pull_requests` / `mcp__github__search_pull_requests` —
see `tool-mappings.md`).

If an open PR already adds or extends the thing you were about to build,
**don't duplicate it.** Instead:

- If the PR looks stalled or abandoned, offer to pick it up and finish it
  (check it out, continue the work, push to the same branch) rather than
  opening a competing one.
- If it's clearly active (recent commits, an assigned session), redirect the
  caller to that PR — name it, link it, and stop. Don't build a second draft
  of the same tool.

This is the open-PR counterpart to the branch/worktree scan: a branch can be
unpushed and invisible to `gh pr list`, but a PR can also be pushed and
invisible to a branch-only scan if you never fetch it. Do both checks.

## Both checks come back empty when the work is already DONE

The paragraph above pairs two blind spots, and both are about work **in
flight**.
There is a third case it does not reach, and it is the commonest reason the
thing you are about to build already exists: the work is **finished**.

Completion removes both artifacts at once.
A merge takes the PR out of `--state open`, and the same merge auto-deletes
the head branch in any repo configured that way.
So for anything cleaned up on completion, **absence is the expected result of
success** --- and a query filtered to live state inverts the signal.

The error direction is the expensive one.
It reports the work as missing, which prompts you to do it again;
the opposite error merely prompts a redundant check.

Name the whole population rather than the live slice:

```bash
gh pr list --state all --search "<keywords> in:title,body"   # did anyone already do this?
gh pr list --state all --head "<branch>"                     # did this branch ever have a PR?
```

**Do not predict the branch name either.**
Searching for the name you *expect* the work to be under is the same failure
one axis over: it enumerates one guessed member instead of deriving the
population, per
[`algorithmatize-checks`](algorithmatize-checks.md)'s "never predict which
case will fail; enumerate the class".
A search over titles and bodies finds the work whatever it was called;
`git ls-remote origin refs/heads/<guess>` finds it only if you guessed right.

- **Do:** search `--state all` before concluding that work has not been done.
- **Do:** search on keywords rather than on a predicted branch name, so the
  query names the population instead of one member of it.
- **Do:** read an absent branch as "merged and cleaned up" until a query that
  can see merged work says otherwise.
- **Don't:** read `--state open` returning nothing as evidence that nobody did
  this --- that is the answer a *completed* PR produces.
- **Don't:** read `git ls-remote` returning nothing as evidence a branch was
  never pushed;
  a merge deletes it, which is
  [`use-existing-pr-branch`](use-existing-pr-branch.md)'s auto-delete case
  read in the absence direction rather than the presence one.

**The two states are byte-identical under every liveness-filtered query, which
is worth measuring rather than arguing.**
Run each query against a merged branch and against one that never existed:

| branch | `--state open` | `ls-remote` | `--state all` |
|---|---|---|---|
| `ums/relocation-dangling-refs` (merged) | 0 | 0 | `1444:MERGED,1442:MERGED` |
| `ums/definitely-never-existed-xyz` | 0 | 0 | `[]` |

Only `--state all` discriminates, and that is the negative control this
whole section rests on.
Name the column rather than counting to it:
a positional reference is read against a table anyone can add a column to,
and a reader who counts from the header lands on `ls-remote`,
which is one of the two queries the table exists to rule out.

**Two standing remedies for a suspicious zero cannot fire here, so do not wait
for either to save you.**

Reporting the denominator is
[`fail-fast`](../principles/fail-fast.md)'s general answer to a zero that might
be vacuous, and here it does not discriminate: both rows above share it, since
zero open PRs and zero refs are the true counts in each.
The filter is applied **before** the population is formed, so a completed
artifact sits outside what the check examined rather than inside it and
unmatched.

Re-running is the other reflex, and it makes matters **worse** rather than
better.
A stale query is fixed by asking again later; a liveness-filtered one grows
*less* accurate over time, because every minute raises the chance the work
finished and was cleaned up.

**The class is wider than PRs and branches.**
Any query scoped to a current set behaves this way: `ps` for a process that
exited, `docker ps` without `-a`, `gh run list --status in_progress`, an
open-file-handles check.
Before reading an empty result as "it never happened", ask whether completion
removes the thing being queried.

(`Morrison-Lab/ai-config#1447`, 2026-08-13.
A delegated agent opened [#1442](https://github.com/Morrison-Lab/ai-config/pull/1442)
at `04:59:48Z` and it merged at `05:24:04Z`.
Checking afterwards with this fragment's own prescribed query returned
nothing, as did `git ls-remote` on the branch, so the work was reported lost
and re-pushed as
[#1444](https://github.com/Morrison-Lab/ai-config/pull/1444) at `05:31:47Z`.
That PR merged with an empty diff ---
`git diff --stat 29532758^1 29532758` returns nothing --- and
[#1443](https://github.com/Morrison-Lab/ai-config/issues/1443) was filed as a
duplicate tracking issue for work already done.
Neither command was wrong.
Both answered "is this in flight?" when the question was "did this happen?".
The predicted-name half is from the immediate sequel: a second check for
`refs/heads/ums/liveness-filter-blindspot` also returned nothing, because the
agent had used `ums/liveness-filtered-queries`, and only a filesystem
collision on its worktree path revealed the branch at all.)
