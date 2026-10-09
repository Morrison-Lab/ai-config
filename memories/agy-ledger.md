# `agy` standing rules

The per-agent mistake ledger that [`improve-your-subagents`](../shared/workflow/improve-your-subagents.md) asks every orchestrator to keep, for the `agy` CLI.
Prepend the numbered list, verbatim, to every `agy` brief, and append to it after every fix round.

It lives here rather than in a session scratchpad or a PR branch because a rule written where the next dispatch cannot read it changes nothing.
Each numbered rule is a past mistake on a real dispatch, stated as the action that avoids it, with the incident in parentheses.

1. Do not claim work you did not do.
   A reviewer diffs your commit message against your diff and rejects the commit when they disagree.
   Say only what the diff or command output shows. (Twice: tests reported that were never written.)
2. Do not leave unreachable code after a return. (A duplicate block left after `return parsed`.)
3. Do not write a commit message through a double-quoted shell string;
   the shell expands variables and runs backtick spans inside one.
   Write the message to a file with `python` and use `git commit -F`. (A `$HOME` expanded into a message.)
4. Do not reverse a decision an earlier round made on purpose without saying why.
   Read the surrounding comment first;
   if it explains why the current form was chosen, changing it is a claim needing evidence. (`bootstrap.sh`'s render guard made fatal, undoing a deliberate non-fatal choice.)
5. Do not add a check whose message describes a different test from the one it performs.
   If a check rests on a property of the data rather than of the language, state that property in its docstring and say what would invalidate it. (A token-count check with a message about spaces in paths.)
6. Append a rule to a corpus file as its own section with its own heading and context.
   Never append bare bullets into somebody else's list, and never split an existing sentence. (A rule pair spliced through the middle of a sentence.)
7. Do not delete a test because its name is wrong;
   fix the name if the coverage is real, and delete the test only after showing the test cannot fail. (A test for a second chained block in an allowlisted file, deleted, restored by the orchestrator, then deleted again once shown unable to fail, on ai-config#3440 on 2026-09-12.)
8. Write scratch files ONLY under the scratch directory your brief names, never into a repository checkout, and delete them before you finish.
   Never create a file in a checkout you were told only to read. (Fourteen scratch files left in the maintainer's primary checkout across two dispatches, on 2026-09-12.)
9. Do not use your native file tools (`write_file`, `read_file`, `edit_file`);
   they are denied for the repositories and scratch directories an `agy` job works in, and one call aborts the whole run with no output.
   Read with `Get-Content` or `python`, and write with a `python` script through your shell tool. (A whole memories pass lost.)
10. After writing prose through a script, count the backslash-apostrophe pairs in the written file and confirm none remain outside a deliberate example.
    Escaping an apostrophe inside a string literal delimited by the same quote leaves the backslash in the file, and markdown renders it. (`maintainer\'s` and `Don\'t` written into a published section on 2026-09-12.)
11. Put commands, paths and placeholders in markdown code spans.
    A bare `<path>` is read as an HTML tag and can vanish from the rendered page, and a bare command is indistinguishable from prose. (A section giving its command and a `<path>` placeholder as plain text, 2026-09-12.)
12. Delete only files you created, and only in the directory your brief tells you to clean.
    A scratch directory your brief names for helper scripts is shared with the session that dispatched you, and its other contents are that session's. (A cleanup job told to remove its own files from a repository checkout also deleted every brief and log in the orchestrator's scratch directory on 2026-09-12, destroying the record of what two jobs reported.)

## Orchestrator-side rules (for the session writing the brief)

- Never set an agent's working directory to a checkout it does not own.
  Give it its own worktree for edits, and a named scratch directory for everything else.
- Name the exact files an agent should read, so the shell route is the obvious one.
- Send an agent's mistake back to it with the finding, the input that broke the agent's output, and the standard.
  Do not commit the fix yourself.
- Give your own files, such as a job's log, a name the agent's deletion rule cannot match.
  An agent told it may delete files with a given prefix will delete an orchestrator log carrying that prefix, because it is following the rule it was given.

## Ending an `agy` review loop

Measured on #4427 and #4434, 2026-10-08.
Every `agy --print` review round produced new `[NIT]` items, some repeating items already answered on the PR.
`scripts/check-pr-fully-clean.py` reads any item under a `### Findings` heading as open.
A reply that answers the item does not supersede the review;
only a later review does.
So each round otherwise costs a push and a paid Claude review, and on #4427 two rounds of that did not converge.

What converged on both PRs was one more `agy` run, with the answered items listed in the brief as context and an instruction to report only new findings.
On #4427 that run was on the same head, with no push.
On #4434 the real nits were fixed in the push that also merged the base, and that push's `agy` run reported `### Findings` as `None.` beside `Ready for merge`, which scored exit 0.

A skip list can also hide a real finding.
On #4431 at `72f7a3e3`, an `agy` run given a skip list reported `None`, while the Claude review of the same head found a real deadlock in the branch scope.
That skip list held only items genuinely answered on the PR, so keeping the list narrow does not prevent this.
The safeguard is a second reviewer: a `None` from a run with a skip list counts only beside an independent reviewer's clean verdict on the same head.

- **Do:** fix the real nits once, answer the rest on the PR, then give `agy` the answered list and ask only for new findings.
- **Do:** list only items that were actually answered on the PR, never a whole area of the diff.
- **Do:** trust that run's `None` only when an independent reviewer has returned a clean verdict on the same head.
- **Do:** when a push is owed anyway, such as a base sync, fold the nit fixes into it so they cost no extra review cycle.
  When none is owed, make one push carrying every accepted nit fix, after the usual pre-push self-review, then one `agy` run on the pushed head.
- **Don't:** push once per `agy` round to clear its newest nit list.
- **Don't:** write "Blocking findings: None" in a review.
  The scorer reads it as not-clean (#4428).
