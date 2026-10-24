# Git commit and push

Commit and push mechanics: shell quoting in commit and PR-comment bodies,
`git commit` edge cases (`--amend` after a merge, `-F -` in a compound
command), a pre-push guard falling back to command-text matching, and
`git push`'s option-argument grammar.
Split out of [`git.md`](git.md) (ai-config#694 pattern) at the 1200-line gate
(ai-config#1066).

## `git commit -m "..."` runs backtick spans as shell commands

A commit message passed through a double-quoted `-m` goes through the shell
first, so any backtick span inside it is command substitution: the shell
*runs* the backticked text and drops it from the message.
``git commit -m "fix the `slast` guard"`` commits `fix the  guard` --- the
`slast` span is gone, and whatever running `slast` printed (usually nothing,
often an error to stderr) is spliced in where it stood.
Nothing errors on the commit itself, and the corrupted message is what lands in
history.

This is the bash counterpart of `CLAUDE.md`'s "PowerShell CLI Command Safety"
backtick warning, by a different mechanism: PowerShell treats the backtick as
an escape character, bash treats it as command substitution.
The remedy is the same either way.
Use `git commit -F <file>` with a body file, or a single-quoted `-m '...'`,
whenever the message carries backticks --- Markdown code spans, identifiers,
paths.
Write that body file to the session scratchpad,
not to the worktree and not to a bare `/tmp` path:
`git add -A` stages one written inside the worktree,
and `/tmp` is shared with every other concurrent session.
See [`shell.md`](shell.md)'s heredoc section for both hazards.
([Morrison-Lab/ai-config#1042](https://github.com/Morrison-Lab/ai-config/issues/1042), 2026-08-03:
a `-m` commit message lost its backtick spans this way;
the message landed at `97bf7d4` with the spans executed and deleted.)

## `gh pr comment` / `gh api ... -f body="..."` run backtick spans too

The identical bash mechanism corrupts any `gh` command that takes a body
through a double-quoted argument, not just `git commit -m`.
`gh pr comment <N> --body "..."`, `gh issue comment`, and
`gh api .../comments -f body="..."` / `.../replies -f body="..."` pass the body
through the shell first, so a backtick span is command substitution: the shell
runs the backticked text and splices its output (usually nothing) where the
span stood, and the corrupted comment lands on someone else's thread reading as
though you wrote it that way.

The remedy is `CLAUDE.md`'s "Use body files" rule, extended past PR
descriptions and past PowerShell: write the body to a file and pass
`--body-file <file>` (`gh pr comment`, `gh issue comment`) or `-F body=@<file>`
(`gh api`), for comment and review-reply bodies too, in any shell.

- **Do:** pass a backtick-carrying comment or review-reply body through
  `--body-file` / `-F body=@<file>`, exactly as for a PR description.
- **Don't:** inline a double-quoted `--body "..."` / `-f body="..."` that
  contains a code span or identifier --- bash runs it as a command and drops it.

(Morrison-Lab/gha#425, 2026-08-05: a `gh api .../replies -f body="..."` review
reply carried a `ms.` code span; the posted comment ran that span as a command
and dropped it, so the thread lost the identifier entirely.)

## A pre-push guard whose sibling module fails to load falls back to matching the command text, and a heredoc that quotes `git push` trips it

`hooks/no-push-without-self-review.py` imports `no-unreviewed-pr.py` as a
sibling module.
When that import fails, the guard cannot parse the command.
It was observed from a worktree where the guard's error path showed it running from `<worktree>/.claude/hooks/`, a copy with no sibling beside it.
Which registration selected that copy, and whether `CLAUDE_PLUGIN_ROOT` resolved there, is what [ai-config#2981](https://github.com/Morrison-Lab/ai-config/issues/2981) leaves open.
The guard then degrades to a narrow heuristic regex over the raw command text.
That regex is not a substitute push parser.
The hook uses it only to decide whether to report the broken installation and deny the command when the text looks like a `git ... push` invocation.
The regex is deliberately narrow:
`grep push` and `git commit -m "push the button"` do not trip it,
and the hook's own suite pins that.
It reads the whole command string, though,
so a heredoc body that quotes a literal `git push -u origin <branch>` line is read as command text.
It then matches exactly as a real push would.
A `printf` body matches only when the character before `git` is not a quote (a backtick, in the measured case).
`printf '%s' 'git push ...'` passes.
Measured 2026-09-01 while writing an issue body,
and again while posting the correction to that issue.
Tracked as [ai-config#2981](https://github.com/Morrison-Lab/ai-config/issues/2981).

- **Do:** write a comment or issue body that quotes a push command to a file
  with your harness's file-writing tool (Claude Code's `Write`, or its
  equivalent elsewhere), then post it with `--body-file` (or
  `-F body=@file`), rather than composing it inside a Bash heredoc.
- **Do:** reserve `ALLOW_UNREVIEWED_PUSH=1` for the one command that is an
  actual `git push`, and state why in the same turn.
- **Don't:** read the guard's block on a body-writing command as a real
  self-review gap --- it is the sibling-import fallback reading quoted text.
- **Don't:** export `ALLOW_UNREVIEWED_PUSH=1` for the whole session to work
  around the false positive; that also waives the guard for the real push.

## `git push`'s option-argument grammar: required vs optional vs boolean vs clustered

Measured on git 2.50.1 while writing `hooks/flag-conflict-with-base.py`'s
argument parser (ai-config#3175).
Four distinct shapes, and confusing them misresolves which token is the
option's value and which is the positional remote:

1. **Required argument.**
   Accepts the space form even where the manual's synopsis prints only the
   `=` form.
   `--recurse-submodules on-demand` consumes `on-demand` as the value; the
   manual shows `--recurse-submodules=check|on-demand|only|no` and nowhere
   shows the space form, but git's `parse-options` accepts it for every
   option whose argument is required.
   Reading the manual's synopsis alone and concluding the space form is
   invalid is the trap: the discriminator is required-vs-optional, not what
   the page happens to print.
2. **Optional argument.**
   Takes a value only in its `=` form; the space form does not attach it, so
   the next token is read as something else entirely (typically the
   positional remote).
   `--force-with-lease` and `--signed` are both this shape: `git push
   --force-with-lease origin main` targets `origin`, not
   `--force-with-lease`'s own value.
3. **Pure boolean.**
   Takes no value in any form, and is not a variant of the optional-argument
   case even though both never consume a following token.
   `--[no-]force-if-includes` is this shape --- git's own synopsis marks it
   `[--force-if-includes]` with no `=` anywhere, unlike
   `--force-with-lease[=<refname>[:<expect>]]` right beside it.
4. **Clustered short options.**
   A short option can arrive bundled with others in one token, and a
   value-taking letter consumes the rest of that token (or the next token,
   if it ends the cluster).
   `-fo ci.skip` is git's own parse of `-f -o ci.skip`; a check for the exact
   token `-o` misses it, since `-o` never appears as its own argv entry.

- **Do:** classify a `git push` option as required-argument,
  optional-argument, or pure-boolean before deciding whether it can take a
  space-separated value --- the manual's synopsis alone under-determines the
  first case and over-determines the third.
- **Do:** walk a short-option cluster letter by letter when parsing `git
  push` argv, so a bundled value-taking letter is not read as a bare flag.
- **Don't:** assume an option prints its exact accepted forms in the
  manual's synopsis line --- `--recurse-submodules=check|on-demand|only|no`
  omits a form git actually accepts.
- **Don't:** treat `--force-if-includes` as a third instance of the
  optional-argument shape merely because it also takes no space-separated
  value; it has no `=` form at all, which the other two do.

(Measured 2026-09-05, `Morrison-Lab/ai-config#3175`: two review rounds each
corrected one of these confusions in the same parser --- `--recurse-submodules`
was first excluded from the value-consuming set on the false belief that only
its `=` form was valid, then `--force-if-includes` was grouped with the
optional-argument options it does not share a grammar with.)

## `git commit --amend` after a merge amends the MERGE, and the result reads as a duplicate commit

Reword a commit, then merge `main` in, then reword again, and the second `--amend` retargets the merge commit rather than the commit you meant.
Measured 2026-09-03 on ai-config#3023.

Nothing errors and nothing warns.
The merge silently takes the fix commit's subject line, so `git log --oneline` shows two consecutive commits with the same title and no visible merge:

```text
de4e3620 fix(shellcmd): three false verdicts in the heredoc scanner and strip_env
4cbb896b fix(shellcmd): three false verdicts in the heredoc scanner and strip_env
```

That reads as an accidental duplicate commit, which invites exactly the wrong remedy --- dropping one of them, which would drop the merge.
`git rev-list --parents -n1 HEAD` is what tells them apart: three hashes means the top one is a merge whatever its subject says.

The trap is that `--amend` is almost always used seconds after the commit it targets, so "the commit I just wrote" and "HEAD" coincide and the distinction never comes up.
A merge lands between them here, and the habit does not notice.

**The recovery is a rewrite, so prove it changed no content.**
Reset to the real commit, amend it, and redo the merge:

```bash
TREE_BEFORE=$(git rev-parse HEAD^{tree})
git reset --hard <fix-commit>
git commit --amend -F /path/to/session-scratchpad/message.txt   # not /tmp, not the worktree
git merge origin/main --no-edit
[ "$TREE_BEFORE" = "$(git rev-parse HEAD^{tree})" ] && echo "TREES IDENTICAL"
```

The tree-hash comparison is the point rather than ceremony.
A message-only rewrite must leave the tree byte-identical, so an inequality means the reset or the redone merge lost something --- and that is a class of loss no test suite can see, since the tests run on whatever tree survives.
Capture `TREE_BEFORE` before the reset, not after.

Where the amend also changes content, the equality no longer holds and `git diff <old-head> HEAD` is the check instead: it must show your intended edit and nothing else.

- **Do:** read `git rev-list --parents -n1 HEAD` before `--amend` when a merge may have landed since the commit you mean to fix.
- **Do:** assert tree-hash equality across a message-only rewrite.
- **Don't:** read two same-titled consecutive commits as a duplicate to drop;
  check the parent count first.

## Probing git's own argument parsing in-session: `git push --dry-run` is exempt from the self-review guard; `-h` is not

`hooks/no-push-without-self-review.py` reuses `no-unreviewed-pr.py`'s
`_argv_push`/`_push_re_heads` classification, which excludes `--dry-run`/`-n`
and `--delete`/`-d` outright: neither re-heads a branch, so there is nothing
for a self-review to have covered, and the guard never even reaches the
verdict check for them.
That makes `git push --dry-run` (optionally against a scratch repository, or
`--repo=/nonexistent` to guarantee no network contact) the sanctioned way to
observe git's own push behaviour --- which remote it resolves, which option
consumes a value --- from inside a session that has not yet dispatched a
self-review, without needing the override or a real push.
The guard's own docstring uses exactly this form to document its measurements
(`git push --dry-run --repo=/nonexistent origin main`).

`-h`/`--help` is not on that exclusion list.
It prints usage and touches no ref, so it is exempt for the same reason
`--dry-run` is, but the classifier does not special-case it, so a bare `git
push -h` with no prior clean verdict in the transcript is blocked exactly
like a real push.

`man git-push` is not a safe substitute for measuring, either.
Its synopsis for `--recurse-submodules` prints only the `=` form
(`--recurse-submodules=check|on-demand|only|no`), while git's `parse-options`
accepts the space form for any required-argument option --- see this file's
"`git push`'s option-argument grammar" section.
A manual read settles what an option *means*; only running the command settles
what forms it *accepts*.

- **Do:** use `git push --dry-run` (against a scratch repository or a
  nonexistent path when network contact must be avoided) to measure git's own
  push-argument behaviour in-session, ahead of a self-review dispatch.
- **Do:** treat a manual page as a starting hypothesis about accepted option
  forms, and confirm it against a real invocation before relying on it.
- **Don't:** run `git push -h` expecting it to be exempt like `--dry-run` ---
  it is not on the guard's exclusion list and gets refused like a real push
  with no clean verdict on record.
- **Don't:** read the manual's synopsis line as the complete set of forms an
  option accepts.

(Measured 2026-09-05 while writing `hooks/flag-conflict-with-base.py`'s
argument parser, `Morrison-Lab/ai-config#3175`: `git push -h` was blocked
mid-session with no self-review yet dispatched, and `git push --dry-run
--repo=/nonexistent origin main` was the fallback that measured git's `--repo`
precedence without a real push or the override.)

## `git commit -F -` in a compound command can make no commit and report nothing

The backtick rule above pushes you toward `-F` in the first place.
`-F <file>` is the safe half of that;
`-F -` is not, and its failure is silent in exactly the situation that hides it.

Measured 2026-09-17 in `Morrison-Lab/ai-config`.
This shape made no commit:

```bash
git add <path> && git commit -F - <<'MSGEOF' 2>&1 | tail -3
...message...
MSGEOF
echo "next thing"
```

`git log` still showed the previous commit and `git status` still showed the file as ` M`.
No error surfaced, because the pipeline's output was displaced by the commands that followed it in the same call.
A compound command whose later stages print plenty is precisely where a missing commit looks like a successful one.
Whatever ran after it --- a push, most damagingly --- then operated on a tree the commit never reached.
That trailing push is deliberately not written into the block above, because `scripts/check-chained-commit-push-in-fences.py` denies a commit chained into a later push inside one fence, and this fragment's subject is `-F -` rather than the chaining, so the anti-example loses nothing by naming the consequence in prose instead.

The reliable form worked immediately:

```bash
cat > <scratchpad>/msg.txt <<'MSGEOF'
...message...
MSGEOF
git add <path>
git commit -F <scratchpad>/msg.txt
echo "rc=$?"
```

- **Do:** write the message to a scratchpad file and pass that path to `git commit -F`.
- **Do:** print `rc=$?` on the commit's own line, and confirm with `git log --oneline -1` plus `git status --short` before reporting a commit as made.
- **Don't:** feed `git commit -F -` from a heredoc inside a compound command.
- **Don't:** report a commit landed on the strength of having issued the command.
