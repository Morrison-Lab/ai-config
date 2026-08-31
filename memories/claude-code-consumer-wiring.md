# Wiring ai-config skills/memories into a consumer repo's Claude bots

How to make `Morrison-Lab/ai-config`'s skills and memories available
to the `claude`/`claude-code-review` bots in a downstream consumer repo,
and the shallow-clone and submodule-token caveats that come with it.
Split out of [`claude-code.md`](claude-code.md) (ai-config#694 pattern)
at the 1200-line gate.

## Wiring ai-config skills/memories into a consumer repo's `claude` bots

The modern standard is native plugin installation: `Morrison-Lab/gha`'s reusable workflows (like `run-claude-review-attempt` and `claude-code-review.yml`) install the `ai-config` plugin automatically for bot runs, and local sessions load it via plugin marketplaces or `.agents/plugins.json`.

If a repository uses `ai-config` (or any other tool) as both a native plugin and a git submodule, **remove the submodule** per [`remove-redundant-plugin-submodules.md`](../shared/workflow/remove-redundant-plugin-submodules.md).

Historically (prior to native plugins), consumer repos vendored ai-config as a submodule with a committed `.claude/skills` symlink (e.g. `d-morrison/rme#982`, later migrated off the submodule in `d-morrison/rme#1074`):

1. `git submodule add https://github.com/Morrison-Lab/ai-config.git .ai-config`
   in the consumer repo.
2. Replace any hand-copied `.claude/skills/<name>/SKILL.md` (these drift ---
   confirmed via `diff` against ai-config's canonical copy before removing)
   with a **committed symlink** `.claude/skills -> ../.ai-config/skills`, so
   all of ai-config's skills become discoverable, not just the one that was
   hand-copied.
   `.claude/commands/` was left as-is in both repos --- those
   were genuinely project-specific, not ai-config duplicates.
3. Check `.gitignore` for a blanket `.claude/*` ignore (rme had one, with an
   existing `!.claude/commands` exception already carved out for the same
   reason).
If it's there, add `!.claude/skills` alongside it, or `git add`
   silently skips the new symlink as ignored.
If `.claude/skills/` was
   already tracked as a real directory, also run
   `git rm -r --cached .claude/skills` first, to clear it from the index
   before the symlink can be staged in its place.
4. Confirm `checkout-submodules: true` (or an unconditional
   `git submodule update --init --recursive`, as in rme's bespoke `claude.yml`)
   is already set on both bot workflows --- both repos already had it, so no
   workflow edit was needed.

The committed symlink survives `claude-code-action`'s `restoreConfigFromBase`
(which wipes/restores `.claude/` from the base branch on PR-triggered runs)
because it's part of that committed base --- this is the same technique
ai-config's own repo already uses for its own `@claude` bot.
`memories/` and
`shared/` get no equivalent auto-load mechanism (Claude Code doesn't scan a
project memories folder the way it does skills), so they're just readable
on disk, not injected into context automatically --- unless the consumer's
own `CLAUDE.md` explicitly pulls specific files in with Claude Code's
`@path` include syntax, e.g. `@.ai-config/memories/tools.md` or
`@.ai-config/shared/workflow/ardi.md` (the path is `.ai-config/`-prefixed
in a consumer repo, unlike ai-config's own `@claude` bot, which resolves
`@shared/...` straight from the repo root --- see this repo's own
`README.md`, "Shared content (`shared/`)").

Two caveats a reviewer raised are worth pre-empting rather than leaving as
open questions.

A pinned submodule SHA that isn't `ai-config`'s current tip is still
fetchable with `git fetch --depth 1 origin <sha>` --- GitHub's shallow-clone
protocol supports fetching any reachable commit, not just branch tips.

**A `--depth 1` shallow clone gives a bogus merge-base, so a `git log A..B`
/ `git diff A..B` range against another branch shows the *entire* repo as
added.**
In a shallow clone the histories of two branches share no common
ancestor git can see (it's truncated), so `origin/main` and a feature branch
appear fully disjoint --- `git log <branch>..origin/main --stat` reports
hundreds of files / thousands of insertions that aren't real, and a real
`git merge origin/main` produces spurious mass conflicts.
Don't run
merge/diff-vs-main operations on a shallow clone.
What *is* reliable on a
shallow clone: single-tree reads (`git show origin/main:<file>`,
`git cat-file`) --- they read the fetched tip's tree directly, no merge-base
needed.

**The same truncation degrades classifiers built on file history, and how
badly depends on which question you ask -- so test the query rather than
assuming either that it works or that it doesn't.**
A bogus merge-base announces itself, with thousands of phantom insertions or a
merge that explodes into conflicts.
A history *query* just comes back empty, and empty is also a legitimate answer,
so it cannot be told apart from a real negative by looking at it.

Two questions that appear interchangeable behave very differently on a
shallow clone of this corpus:

- `git log --diff-filter=D -- <path>` ("was this ever deleted?") returned
  **zero for every candidate**, ours and foreign alike, at depth 50.
  A deletion that happened before the shallow window is simply not in it, so
  this question is unanswerable here while appearing answered.
- `git log --all -- <path>` ("has the repo ever touched this?")
  **did** discriminate, on the same clone at depth 55: zero for all seven Anthropic
  built-ins, against 6 for `ums`, 3 for `ardi` and 1 for `config-ai`.
  An actively maintained file gets touched inside almost any window, which is
  what makes the weaker question survive truncation.

The five commits gained between those two measurements are not what produced
the discrimination, which is the obvious objection and worth foreclosing:
none of them touches `skills/ums`, `skills/ardi` or `skills/config-ai`, and
every commit behind those three counts predates all five.
The second form would have separated the two classes at depth 50 as well.

The residual risk in the second form is a file that is genuinely ours but has
not been touched within the window, which reports as never-ours.
So the rule is not "history is useless when shallow" but: check
`git rev-parse --is-shallow-repository`, then **run the query against known
controls of both classes** before trusting it, and prefer a signal carried by
the file itself when one exists.
Note what "both classes" costs here, because this corpus could not supply it:
there was no deleted-but-still-installed skill to test against, so the
observed separation only shows the query telling *never ours* from *ours and
actively maintained*, never the class it claims to catch.
That is the same gap the residual risk above names, arrived at from the other
direction, and it is why the query is worth reporting to a human rather than
trusting.
[`ardi.md`](../shared/workflow/ardi.md)'s "test the class it distinguishes"
bullet is the review-time counterpart to this entry: this one says why a
history query fails on a truncated clone, that one says to confirm a true
positive of the class exists in what you tested before claiming the mechanism
separates the cases at all.
(ai-config#765/#770, 2026-07-28: separating our own deleted skills from
Anthropic-provided built-ins under `~/.claude/skills/`.
The `--diff-filter=D` form was measured first and its blanket zero suggested
history was unusable here; a bare `git log --all` over the same candidates in
the same shallow clone separated the two cleanly.
The file-borne signal that needs no history at all: the built-ins carry
`license: Proprietary. LICENSE.txt has complete terms`.)

A third mode --- `git log -S`, `--follow`, and `blame` naming a graft commit
as the introduction, which is neither self-announcing nor empty --- is in
[`git.md`](git.md).

`git fetch --depth N origin <branch>` deepens enough history to make
a real merge-base available if you must merge. (Hit resolving
UCD-SERG/serocalculator#503's altdoc chain, 2026-07: a `--depth 1` altdoc
clone made `recursive-qmd-search..origin/main` show 272 files / 14k
insertions, all an artifact; the `git show origin/main:R/utils.R` tree reads
in the same session were accurate.)

A fine-grained `SUBMODULES_TOKEN` scoped to a private submodule (e.g. rme's
`latex-macros`) also authenticates a newly-added *public* submodule, since
public repos need no authentication --- confirmed empirically by the PR's
own `claude-review` check (which runs with submodule checkout on) completing
successfully. (rme#982, epi204#359/#360, 2026-07-04.)
