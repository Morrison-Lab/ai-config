# Git diffing

Diff-range selection, diff-scoped check pitfalls, and pathspec/glob/ref
pattern-matching mismatches -- what a `git diff`, `git ls-files`, or
`git rev-parse <ref>:<path>` call actually sees.
Split out of [`git.md`](git.md) (ai-config#694 pattern) at the 1200-line
gate.

## A diff-scoped local check silently no-ops on an empty/uncommitted diff --- commit before running it, not after

A repo's own pre-push check script can include steps that gate on `git diff
<merge-base> HEAD` (a comment-citation scanner, a units-convention linter, a
patch-coverage calculator) rather than the raw working tree.
If you run such
a script against **uncommitted** changes --- reasoning "let me verify before I
commit" --- the diff-scoped steps compare HEAD against itself (or whatever the
last commit was), see no changes, and silently report a clean pass ("no
GDScript changes in this diff") without having examined your actual edits at
all.
Only the disk-based steps in the same invocation (a plain test run, a
character-encoding scan of the working tree) give real signal; the
diff-scoped ones are pure no-ops that LOOK identical to a genuine clean
result in the printed summary.

This cost one delegated subagent roughly two hours and most of a million
tokens in one session: it wrote a real, working feature, then spent that
time re-running the full check suite (each pass ~15-20 minutes) against its
own uncommitted working tree, never noticing that three of the five
requested checks were quietly checking nothing.
The fix, once diagnosed,
was mechanical --- commit first, then re-run the checks against a real diff ---
but the diagnosis itself only happened after the orchestrating session
noticed a suspicious mismatch (two full turns and heavy token spend, yet
`git log`/`git status` showed no commits and no uncommitted changes) and
asked the agent directly why there was no visible progress.

**How to apply:** before trusting a "PASS" from any check step whose own
description implies it scopes to a diff (a comment scanner, a
units-convention check, coverage-of-new-lines), confirm there IS a
non-empty diff for it to have scanned --- commit (even a rough, uncommitted-
but-final draft) before the verification pass, not after.
When briefing a
subagent to implement-and-verify a feature, say so explicitly: "commit your
changes before running the diff-scoped checks (comments/units/patch_coverage
in this repo's `tools/check.sh`), not after --- they silently no-op against
an empty diff."
And when an orchestrating session sees a subagent burn
much more wall-clock/tokens than its own diff would justify, checking
`git log`/`git status` directly is a fast, decisive way to catch this class
of problem rather than trusting the subagent's own narration that it's
"still verifying." (Sparta `gii-mwc` session, 2026-07-19, `tools/check.sh`'s
`comments`/`units`/`patch_coverage` steps.)

**This is not only a subagent-scale failure --- it bites a single session
running one check by hand, and the ai-config corpus's own
`check-new-line-breaks` is one of these.**
Its script runs `git diff --unified=0 <base_ref>...HEAD`, so a working tree
full of uncommitted edits is invisible to it: on `main` with changes not yet
committed, `HEAD` *is* `origin/main`, the diff is empty, and it prints
`No lines missing semantic breaks.`
That message is indistinguishable from a genuine pass, and it is especially
seductive here because the check is *also* advisory (it warns and exits 0 ---
see [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md)), so
neither its exit code nor its output gives the game away.
The habit that actually works: `git checkout -b`, `git add`, `git commit`,
**then** run the diff-scoped checks, and only then push.
(ai-config#730 and #732, 2026-07-25, in the same session: both ran the check
against an uncommitted tree, both got a false clean, and both had the real
violations found afterward --- #730's by the check itself once the first
commit existed, #732's by a reviewer.
The second time is what makes this worth recording, since the entry above
already existed and was not applied.)

**Green on the push event is not green on the pull_request event, for a diff-scoped checker --- the two triggers diff different bases.**
Same commit, ai-config#2074, 2026-08-24: the push-event `new-line-breaks / check-new-line-breaks` run passed on three consecutive heads while the pull_request-event run failed each time, because that run diffs lines added since the merge-base, which is the set the PR is actually judged on.
Judge a branch by its pull_request-event runs.
A green push-event run of the same check name proves nothing about the PR verdict.
Since [ai-config#1730](https://github.com/Morrison-Lab/ai-config/issues/1730) this repository's `new-line-breaks` job is gated on `pull_request`, so its push-event run reports `skipped` rather than green;
the disambiguation above still applies to any diff-scoped check that lacks that guard.

## Picking the diff range: `..` vs `...` vs the working tree

Three forms answer three different questions, and reaching for the wrong one
produces a confident, wrong read of your own PR.

- `git diff origin/main..HEAD` (two dots) compares the two **tips**.
  When your branch is behind `main`, main's newer commits show up as
  **deletions** -- files your PR never touched look removed by it.
- `git diff origin/main...HEAD` (three dots) compares against the **merge
  base**, which is the PR's actual diff and what GitHub shows.
  Use this to reason about what the PR changes.
- `git diff origin/main` (no second ref) compares the **working tree**, so it
  includes uncommitted edits; both `..` and `...` see only committed work.

Both mistakes hit the same session (gha#318, 2026-07-26).
The two-dot form made #317's changelog fragment -- merged to `main` after the
branch was cut -- appear deleted by the PR, and it was nearly reported to the
user as a finding before `...` showed the real four-file diff.
Later, a non-ASCII/em-dash self-check run as `git diff origin/main...HEAD |
grep` printed clean while the em-dashes sat uncommitted in the working tree;
`git diff origin/main` found them immediately.

That second failure is the by-hand instance of the diff-scoped-no-op section
above, with a second fix available: when the edits are deliberately still
uncommitted, use the worktree-comparing `git diff origin/main` rather than
committing first just to make a check see them.
After you merge `main` into the branch, the merge base becomes `origin/main`
and all three forms agree on committed content -- which is exactly when it is
easiest to stop thinking about the distinction and get bitten by the next
stale-branch case.

**A reviewer can make this mistake against your PR, and the finding it
produces is far more convincing than the self-check version above.**
The cases above are you misreading your own diff, where the fix is just to
rerun the command.
Here someone else runs `git diff --stat origin/main HEAD` and reports, in
detail, that your branch deletes files you never touched.
Three things make it hard to dismiss.
It arrives itemized, as a table of real paths with real line counts, because
every one of those files genuinely does differ between the two tips.
It is internally consistent, so a count or an index that moved in the same
upstream commit corroborates the "deletions" and reads as deliberate intent.
And it invites a destructive repair: reverting those files from your branch
would actually revert whatever merged to `main` while your PR was open.

Check the base before believing the finding, and answer with the merge-base
diff rather than by arguing.
GitHub's own Changed Files panel is the tell, since it always diffs the merge
base, so a reviewer's file list that disagrees with the panel is a diff-range
artifact until shown otherwise rather than a defect in your branch.
Merging `main` in makes the two agree, which lets the rebuttal end with the
reviewer's own command reproducing the panel's numbers.
(ai-config#765, 2026-07-28: a review reported 20 changed files and 822
deletions against a 7-file PR, listed three skills, three Codex wrappers, a
shared fragment and four memory files as deleted, and asked whether to revert
them.
All of it was four commits that reached `main` after the branch was cut.
`skills.qmd`'s count reading `171+` against main's `175+` was the
corroborating detail, and it had moved in the same commit that added the
skills.
The next review round retracted the finding once `main` was merged in.)

## A `git diff` self-check is blind to untracked files, whatever range you pick

The section above chooses between `..`, `...`, and the bare worktree form.
None of the three sees a file git is not tracking yet.
So a self-check driven by `git diff` skips a PR's brand-new file entirely, and a new file is usually the one carrying the most unreviewed added lines.
`git add -N <path>` (or a plain `git add`) is what makes it visible;
`git status --short` marks with `??` exactly what a diff-based check is currently ignoring.

The failure runs in the direction that reads as a pass, so print a count of what the check examined rather than only its hits, per [`fail-fast`](../shared/principles/fail-fast.md)'s by-hand-check rule.
A scan reporting `0 banned-punctuation hits` looks identical whether it read the whole diff or nothing at all.
(ai-config#760, 2026-07-28: a pre-push scan for banned punctuation and multi-sentence lines printed `examined 11 added lines, 0 hits` on a PR whose new fragment ran to 85 lines.
The count was the only thing that gave it away;
staging first and re-running scanned all 85.)

## An untracked copy sitting where a tracked file lives on another branch runs instead of it

The entry above is about a check that cannot **see** an untracked file.
This is the inverse and the worse half: an untracked file you cannot help but
**run**.
A scratch copy of a script, left at the same relative path as the tracked
version that lives on some other branch, is what `./scripts/<name>.sh`
resolves to.
The inputs are fine, the invocation is right, and the binary is wrong.

Nothing at the call site distinguishes them.
Same path, same name, executable, plausible output.
`git status --short` marks it `??`, but an untracked file among a working
tree's other untracked files is unremarkable, and the checkout around it is
fresh --- which is what makes this harder to spot than an ordinary stale
checkout, where at least everything is stale together.

The failure is also **self-confirming**, not merely silent.
A stale copy's already-fixed bug presents as a genuine finding, so the wrong
binary generates apparently productive work: a diagnosis, a fix, a test.
A wrong *artifact* would eventually contradict something; this produces a
correct fix to a problem that no longer exists, and every step after the first
looks like progress.

One command settles it before you trust any behaviour you observed:

```bash
git ls-files --error-unmatch scripts/<name>.sh    # exit 0 = tracked here
```

Non-zero on a path you expected to be tracked is the tell.
Then ask the second question, which the first does not answer: **is this branch
the one that owns the file?**
A path untracked on `main` and tracked on a feature branch is exactly the
shape, so check the owning PR's copy before concluding anything about the
script's behaviour --- and diff the two rather than assuming yours is behind
only where you noticed.

`ucdavis/bcs`'s own `CLAUDE.md` already leans on this command for a different
purpose (deciding whether a path under `inst/extdata/` is restricted data), so
it is a cheap habit with two payoffs rather than a new one.

- **Do:** run `git ls-files --error-unmatch <path>` before treating a script's
  behaviour as the artifact's behaviour.
- **Do:** compare against the copy on the branch that owns the file, and read
  its version before writing a fix.
- **Don't:** read a fresh checkout as evidence that every file in it is the
  tracked one.
- **Don't:** trust a bug you found by running a script until you have confirmed
  which copy ran --- an already-fixed bug reads exactly like a new one.

(`ucdavis/bcs#530`, 2026-07-31: `scripts/resolve-version-conflict.sh` lives on
that PR's branch, and an untracked copy of an earlier revision sat at the same
path in the main checkout, where `git status` showed it as `??`.
Running it exercised the stale copy, whose final "still unmerged elsewhere"
guard counted the file it had just resolved --- it never staged it --- so it
exited 1 on its own success path.
That bug was diagnosed correctly, fixed, and tested in both directions, all of
it redundant: #530's copy already fixed it, and additionally guards on
`git rev-parse --is-inside-work-tree`, where the independently-written fix would
have aborted under `set -e` outside a work tree.
Running the same three-case fixture against #530's copy gave exit 0 on the
handled case, exit 1 naming the genuine second conflict, and exit 0 outside a
work tree.)

## A pattern resolved by `git ls-files` is a pathspec, not a shell glob -- `*.md` is recursive and `**/*.md` drops root-level files

Any tool that selects files by handing a pattern to `git ls-files -- <pattern>`
takes a **git pathspec**, and git's pathspec matching differs from shell and
globby matching in one load-bearing way: `*` matches `/` too.

The consequences invert the usual intuition:

- `*.md` matches at **any depth**, root-level files included.
  It is already recursive.
- `**/*.md` requires **at least one `/`**, so it matches nothing at the repo
  root.

Measured on `ucdavis/bcs`:

```console
$ git ls-files -- '*.md' | wc -l
28
$ git ls-files -- '**/*.md' | wc -l
23
$ git ls-files -- '**/*.md' | grep -v /     # any root-level hits?
```

The third command prints nothing at all: `**/*.md` matches no root-level file.
The five it loses are `NEWS.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, and
`LICENSE.md` -- in most repos, the ones that matter most.

**Why this is worth a section rather than a footnote: the wrong form fails
silently.**
`*.md` reads as non-recursive to anyone carrying shell intuition,
so "correcting" it to `**/*.md` looks like a straightforward fix.
Nothing turns red when it lands.
The linter still runs, still reports success, and still prints a file count --
just a smaller one -- so the repo's most important files stop being checked
with no signal that anything changed.

**The rule is "know which matcher you are feeding", not "never write
`**/*.md`".**
The same pattern behaves oppositely in the two engines, so a blanket ban would
break the globby-based configs it does not apply to.
Two files, one at the root and one nested, in the same repo:

```console
$ npx markdownlint-cli2 '**/*.md'      # globby
Linting: 2 file(s)

$ git ls-files -- '**/*.md'            # git pathspec
sub/nested.md

$ git ls-files -- '*.md'               # git pathspec
root.md
sub/nested.md
```

Globby's `**/*.md` finds both files; the identical pathspec finds only the
nested one, and `*.md` is the pathspec that matches what globby matched.

This corpus relies on both conventions at once, correctly: its own
`.markdownlint-cli2.jsonc` sets `"globs": ["**/*.md"]`, which is right because
`markdownlint-cli2` resolves globs with globby, while a gha workflow input
consumed by `git ls-files` needs `*.md` for the same coverage.

**Settle it by measuring, not by reasoning about glob semantics.**
Both forms through `git ls-files`, compare the counts, and look specifically
for root-level hits with `grep -v /`.
One command decides it, which is the
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) rule
applied to a question that otherwise invites a confident wrong answer.

This is not specific to one repo.
`Morrison-Lab/gha`'s `lint-markdown` and `lint-yaml` both resolve their `globs`
input this way (`_pathspec.mjs` / `_pathspec.py`, `trackedFiles()`) and
document it as "git pathspecs ... recursive by default", so every consuming
repo inherits the same trap.

(`ucdavis/bcs#445`, 2026-07-27: a review of the PR wiring `lint-markdown`
suggested changing `globs: '*.md'` to `'**/*.md'` "for recursive matching",
reasoning correctly from globby semantics and incorrectly assuming they
applied here.
Running both forms before replying is what caught it; applying the suggestion
would have silently un-gated all five root-level files, including the
`NEWS.md` whose merge-splice defect motivated the PR.)

## `git rev-parse <ref>:<path>` writes its own input to stdout when the path is absent

`git rev-parse` resolves `<ref>:<path>` to a blob SHA.
When that path does not exist in that ref it fails **and still writes to stdout** -- the literal input string, unchanged.
Verified on git 2.34.1, 2026-07-30:

```console
$ git rev-parse origin/main:not/a/real/path; echo "rc=$?"
fatal: path 'not/a/real/path' does not exist in 'origin/main'
origin/main:not/a/real/path
rc=128
$ git rev-parse origin/main:README.md; echo "rc=$?"
939ce89cb74324b1c783fe726a20a1d2b4d9b06b
rc=0
```

The two lines go to different streams, so a capture keeps the echoed input whichever way stderr is handled:

```console
$ out=$(git rev-parse origin/main:not/a/real/path 2>/dev/null); echo "[$out]"
[origin/main:not/a/real/path]
```

A capture that merges stderr with `2>&1`, or that ignores the exit status, therefore comes back non-empty with a value that reads as an ordinary answer.
It is also unequal to every real SHA, which is what makes it worse than an empty result.
A "does this path differ between two refs" check compares two such strings, finds them unequal, and reports **differs** when the true answer was **absent from one side**.
That is the by-hand-check shape [`fail-fast`](../shared/principles/fail-fast.md) describes, where the failure path and the pass path print the same kind of thing.

Test the exit status, or use `git cat-file -e "$ref:$path"`, which writes nothing to stdout at all:

```console
$ out=$(git cat-file -e origin/main:not/a/real/path 2>/dev/null); echo "rc=$? out=[$out]"
rc=128 out=[]
```

- **Do:** read `rc` from `git rev-parse <ref>:<path>`, or switch to `git cat-file -e` when only existence is in question.
- **Do:** treat an output that is not SHA-shaped as "the path was absent" rather than as a difference.
- **Don't:** pipe `git rev-parse <ref>:<path>` through `2>&1` into a comparison.
- **Don't:** compare two `git rev-parse <ref>:<path>` outputs for equality without first establishing that both resolved -- two absent paths echo two different strings, which reads as a difference.

(2026-07-30, a `ucdavis/bcs` branch sweep: a per-path comparison built this way reported that a branch was about to destroy another session's work, and that went out as a blocker.
The paths were absent on one side rather than different, and a real set-difference over the two file lists showed the branch was safe.)

## A ref pattern is not a pathspec: `*` does NOT cross a slash in `for-each-ref`, but DOES in `ls-files`

The section above establishes that a **pathspec** `*` matches `/` too.
Git's other pattern matcher does the opposite, with identical syntax, so the
intuition you just built is wrong one command over.

`git for-each-ref <pattern>` (and `git branch --list`, and a refspec's left
side) matches with `fnmatch` under `FNM_PATHNAME`, where `*` stops at a slash.
So `refs/remotes/origin/*` matches `origin/main` and misses
`origin/feat/anything`.

Measured together on git 2.34.1, in one repo, same syntax:

```bash
git for-each-ref --format='%(refname:short)' 'refs/remotes/origin/*'    # 8
git for-each-ref --format='%(refname:short)' 'refs/remotes/origin/**'   # 18
git ls-files -- 'skills/*'                                              # 180
git ls-files -- 'skills/**'                                             # 180
```

The ref matcher halves the result; the pathspec matcher cannot tell the two
patterns apart.

**The failure direction is a silent false all-clear, and it is biased toward
the refs that matter.**
Slash-named branches are exactly the conventional ones -- `feat/`, `fix/`,
`docs/`, `claude/` -- so a sweep keyed on the single star quietly omits every
branch anyone named properly, including the ones carrying open PRs, while
reporting a clean run over whatever is left.
Nothing errors and the count looks plausible.

Use `**` for ref patterns, or `git branch -r` / `git branch --list`, which
enumerate without a pattern.
And per [[algorithmatize-checks]], give any ref sweep a control: check that a
known slash-named branch appears in its output before trusting a total.

- **Do:** use `refs/remotes/origin/**` when you mean every remote branch.
- **Do:** confirm a known nested ref is in the result before quoting a count.
- **Don't:** carry pathspec intuition into `for-each-ref` -- the two matchers
  disagree on the one character that decides it.
- **Don't:** read a smaller-than-expected ref count as "this repo is tidy".

(2026-08-02, a `clean-branches` sweep on `Morrison-Lab/ai-config`: the single
star reported 17 of 34 `origin/**` refs and hid all five open PRs' branches.
Caught only because the open-PR column came back empty against a known count of
five.)

## `git grep` has no `-x` / `--line-regexp` -- do whole-line matching in the consuming code

`grep` supports `-x`/`--line-regexp` (match only lines the whole pattern covers).
`git grep` does not carry that flag forward, even though it accepts most of `grep`'s other switches and reads like a drop-in replacement scoped to a tree.

Measured 2026-08-27 on git 2.50.1 (macOS):

```bash
git grep -x 'some literal line'
# error: unknown switch `x'
# usage: git grep [<options>] [-e] <pattern> [<rev>...] [[--] <path>...]
# (exit 129)
```

For whole-line matching against a tree (not the working directory), get the matching lines out with `git grep -h -F -f <patterns-file> <tree>` and do the exact comparison in the consuming code instead of in the git invocation -- `-h` suppresses the filename prefix so each output line is the matched line verbatim, `-F` treats the patterns as fixed strings, and `-f` reads them from a file (one per line).
Exit code 0 means at least one match, 1 means none, anything else is a real error -- the usual three-way read, not a two-way one.

- **Do:** treat `git grep` as `grep` minus `-x`, and move whole-line comparison into the caller.
- **Do:** read `git grep`'s exit code as three-valued (0 / 1 / error), the same as any other grep-family tool.
- **Don't:** assume every `grep` flag that isn't obviously working-tree-only survived into `git grep` -- check `git grep -h` rather than porting a command by analogy.

## Commit a fix before mutation-testing it -- `git checkout -- <file>` restores to HEAD, not to your fix

The diff-scoped no-op section above says to commit before running a diff-scoped check, because the check reads the wrong population otherwise.
This is the same commit-first discipline for a different, more destructive reason: the restore step after a mutation test discards whatever is uncommitted, fix included.

The mutation-testing workflow this corpus already documents in [`algorithmatize-checks.md`](../shared/workflow/algorithmatize-checks.md) is edit the checker to inject a fault, confirm it is caught, then undo the edit and confirm a clean run passes.
That last "undo the edit" step is usually a `git checkout -- <file>`, and `git checkout -- <path>` restores the path from the index/HEAD, not from "however it looked a minute ago" -- it does not know or care that the pre-mutation state was itself uncommitted work rather than a committed baseline.

So mutation-testing an uncommitted fix and then running `git checkout -- <file>` to remove the mutation reverts straight past the fix to whatever HEAD held before it existed.
The fix is gone, not stashed, not reachable through the reflog (a working-tree edit that was never staged or committed leaves no object at all).

The safe order is: commit the fix first, apply the mutation on top, confirm it is caught, then `git checkout -- <file>` (or `git restore <file>`) to drop the mutation -- which now restores to the commit carrying the fix, because that is what HEAD points at.

- **Do:** commit the fix, then mutate, then restore with `git checkout --` (or `git restore`) -- in that order, every time.
- **Do:** treat any uncommitted state as gone the moment a restore command runs against its path, regardless of how recently it was written.
- **Don't:** mutation-test a fix before committing it -- the restore step cannot distinguish "revert my mutation" from "revert my fix" once both are uncommitted.
- **Don't:** assume `git checkout -- <file>` is reversible for uncommitted content;
  there is no object to recover it from.

(Measured 2026-08-27 in `Morrison-Lab/gha`: a working `check-new-line-breaks` implementation was mutation-tested before being committed, and the restore step's `git checkout -- <file>` reverted to pre-fix HEAD, wiping the implementation.
It had to be re-applied from the session transcript rather than recovered from git.
This exact failure recurred while drafting this entry: the drafting session ran `git checkout -- <file>` to test the semantic-line-breaks reformatter's default scope, wiping its own uncommitted additions described here and requiring a redo.)

## A "moved content" exemption keyed on base-tree membership is a bypass -- key it on the same diff's deleted lines

A diff-scoped checker that wants to exempt genuinely relocated content (a paragraph moved from one file to another, a function moved between modules) needs some test for "this new line is not new content, it just moved here".
The tempting test is membership: does this exact text already exist somewhere in the base tree?
If yes, treat it as moved and skip it.

That test is an exploitable bypass, not a moved-content detector.
"Exists verbatim anywhere in the base tree" is satisfied by any new line that happens to duplicate untouched content elsewhere in the repo -- by coincidence (two files independently containing the same boilerplate sentence), or deliberately (an author who wants a new line exempted copies it from somewhere else in the tree first).
Neither case is a move.
The base tree is not scoped to this diff at all, so the exemption's population is "everything that has ever existed", which is not what "moved" means.

True move semantics require the text to leave one place and arrive at another in the *same* diff: the exact text must also appear among that diff's own **deleted** lines, not merely exist somewhere in the base tree.
That is a strictly narrower, and strictly correct, test -- and it needs no extra git call beyond the diff the checker already has, since a unified diff already carries its own added and deleted lines together.

- **Do:** key a moved-content exemption on "this added line's text also appears in this same diff's deleted lines," never on "this text exists somewhere in the base tree."
- **Do:** treat the base-tree-membership test as a population question, the same way [`algorithmatize-checks`'s exclusion-clause section](../shared/workflow/algorithmatize-checks.md) treats an exclusion clause's population -- ask what else satisfies the test besides the case it was written for.
- **Don't:** ship a "moved" exemption without a case that exercises the bypass directly: a new line that duplicates unrelated, untouched content elsewhere in the tree, which must NOT be exempted.
- **Don't:** assume the narrower, correct form costs an extra pass over the tree;
  the diff already carries both its added and deleted lines.

(Measured 2026-08-27 on `Morrison-Lab/gha#700`: a round-1 adversarial review demonstrated the base-tree-membership bypass empirically, and the fix -- key the exemption on the diff's own deleted lines instead -- needed no extra git call, only a narrower test on data the checker already had.)

## A two-revision tool's "compare `HEAD` with itself" is not a self-comparison while the tree is dirty

The "Picking the diff range" section above is about choosing a range for `git diff`.
This is the same distinction reaching a tool that takes revisions as **arguments** --- a parity checker, a benchmark harness, a migration verifier --- where the working tree is one of the two sides by default and nothing says so.

Such a tool typically accepts `--base-rev` and resolves its other side to the current tree, so `--base-rev HEAD` reads as "compare `HEAD` against itself" and is not that.
With uncommitted changes present it compares committed `HEAD` against the **working tree**, which is a real diff of exactly the size of your edits.
The wrong reading is the plausible one: the run takes a while, produces divergences, and every number looks like a measurement rather than an artifact.

It matters most when a **no-op** is the expected answer.
A negative control for a two-revision comparison is normally "run it against identical revisions and confirm it reports zero", and that control is precisely what a dirty tree makes unreachable --- so a control that never once produced its own expected answer can be believed for an entire session, while CI, which always runs from a clean checkout, sees the true zero on its first attempt.
[`algorithmatize-checks.md`](../shared/workflow/algorithmatize-checks.md)'s "A control's patch point drifts" section carries the case where that gap hid a dead control.

Pass **both** revisions explicitly whenever the intent is a self-comparison, rather than naming one and letting the other default.
Read the tool's own `--help` for the second flag rather than guessing its name: `scripts/check-verdict-scan-parity.py` calls it `--candidate-rev`, whose help reads, in full, "Compare a committed revision instead of the working tree.
Use it to confirm the triage FLAGS a revision known to be fail-open, which is this tool's own negative control."
Note what the first of those two sentences does and does not say --- it names the working tree as the alternative, and leaves you to infer that omitting the flag selects it.
That inference is correct here, and reading a default off a help string is exactly the adjacent-artifact substitution this file warns about elsewhere, so confirm it in the source (`default=""`, then a branch on truthiness) rather than in the help.
When a tool has no second flag at all, commit or stash first, and prefer designing one that names both sides over one that silently adopts the tree --- an implicit side cannot be audited from the command line anyone pastes into a PR.

- **Do:** pass both revisions explicitly when the expected answer is "no difference", reading the second flag's name from the tool's `--help` rather than assuming it.
- **Do:** check `git status --short` before believing a two-revision tool's output, the same way you would before believing a `git diff` range.
- **Do:** give a tool of your own an explicit flag for each side, so the published command records what it compared.
- **Don't:** read `--base-rev HEAD` as a self-comparison;
  it is `HEAD`-vs-worktree unless the tree is clean.
- **Don't:** treat a non-zero result from such a run as evidence the tool discriminates --- your own uncommitted edits produce one.

(Measured 2026-08-28 on `scripts/check-verdict-scan-parity.py`, shipped by [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515).
Read from the source rather than the help: `--base-rev` carries `default="origin/main"`, and the other side is loaded from the working-tree copy of the checker unless `--candidate-rev` is non-empty.
So `--base-rev HEAD` over a dirty tree is `HEAD`-vs-worktree.)

## A check scoped to `A...HEAD` examines nothing before you commit, and prints nothing

The section above is a tool whose *other* side silently defaults to the working tree.
This is the inverse, and the commoner one: a check whose scope is a **commit range**, so the working tree is not one of the sides at all.

```bash
git diff origin/main...HEAD -U0 | grep '^+' | grep -P '[^\x00-\x7F]'
```

Run that before committing and it examines the diff between two commits.
Your uncommitted edits are in neither.
It prints nothing, exits 0, and is indistinguishable from a clean result --- so the moment you most want the check is the moment it cannot fail.

Two things make it worse than an ordinary blind spot.

**It is silent by construction.**
A grep that matches nothing and a grep with nothing to match produce identical output.
Nothing in the invocation reports the size of the search space, which is the general remedy [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) already prescribes: report what was examined, not only what was found.

**The obvious test passes.**
Edit a line the commit already added, re-run, and the check *does* fire --- because that line number is in the committed range.
So a first attempt to verify the theory refutes it, and the bug survives the verification.
Only a line the commit does not carry is invisible.

Either commit first, or scope to the working tree:

```bash
git diff origin/main -- <paths>     # two-dot: includes uncommitted work
git diff --cached                   # staged only
```

Note that the two-dot form also reports changes made on the base since you branched, which is usually noise here and occasionally the point;
the "Picking the diff range" section above covers the distinction.

- **Do:** commit before running a range-scoped check, or scope it to the working tree.
- **Do:** make any check you write report how many files and lines it examined, so a zero is distinguishable from a detector that never engaged.
- **Don't:** verify this class of bug by editing an already-added line --- that case is covered, and passing it proves nothing.
- **Don't:** treat "the ad-hoc grep I type by hand" as exempt;
  it has the same defect as the checker you would file an issue against.

(Measured 2026-08-28, twice in one session and in two independent instruments.
First in `scripts/vendor/gha-check-new-line-breaks.py`, whose `_added_line_numbers` scopes from `base...HEAD` while reading content from the working tree --- filed as [ai-config#2542](https://github.com/Morrison-Lab/ai-config/issues/2542) after a pre-commit run reported clean and CI failed on the same bytes.
Then, hours later, in my own non-ASCII sweep on [#2539](https://github.com/Morrison-Lab/ai-config/pull/2539), which reported clean over a literal em-dash a reviewer found immediately;
filed as [#2550](https://github.com/Morrison-Lab/ai-config/issues/2550), which also carries the reason CI missed it --- the non-ASCII gate scans `.qmd` and `.R`, and this repo is written in Python.
Having filed the first did not prevent the second, which is the argument for the rule rather than the incident.)
