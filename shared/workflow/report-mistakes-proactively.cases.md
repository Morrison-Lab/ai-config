# Case records: report-mistakes-proactively

Worked-example case records for the rules in
[`report-mistakes-proactively.md`](report-mistakes-proactively.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "Filing is not gated on approval" --- stale skills already tracked

(Corrected in an ai-config session, 2026-07-28: a sweep found 49 of 179
installed skills stale or orphaned, and the finding was reported as "worth a
tracking issue separately --- say the word and I'll file it".
The user's correction was "always file issues as soon as you notice them" /
"don't wait for my approval".
The dupe-check then showed it was already tracked by #755 and #769, so the
correct action was a comment with the new evidence rather than a new issue
--- which is step 2 doing its job, and is exactly the decision the offer had
deferred instead of making.)

## "A gated action bundled into a discretionary one is still an offer"

(Corrected 2026-07-29, a bcs branch-sweep session: an unlanded engineering fix
found on a closed branch was correctly identified as needing a tracking issue,
and the closing line asked "want me to file the issue and open that PR?".
The user's correction was that filing is not a thing to ask about.
The issue --- `ucdavis/bcs#466` --- was filed immediately afterward, which is
the evidence that nothing was blocking it in the first place.)

## "Offering to hand over work you have already finished"

(Corrected 2026-07-30: a drafted answer for a GitHub discussion sat complete
in a scratchpad file across two replies, each offering to print it on
request, while the surrounding messages explained at length why posting it
directly was blocked.
The user's correction was "why haven't you done it already then?".
It was printed in full in the next message, which is the evidence that
nothing was blocking it.)

## "Never name an issue number before the issue exists" --- filed as #821

(Corrected 2026-07-29, an ai-config session: a PR comment said a noticed
mistake was "filed as #821" before any issue had been created.
The dupe-check then found #815 already covering it, so the correct action was
a comment carrying the new evidence --- not a new issue at any number.
Both halves had to be repaired: a correction comment on the PR withdrawing
the citation, and the evidence re-posted onto #815.)

## "Never name an issue number before the issue exists" --- ai-config#1328 in a source comment

(Corrected 2026-08-09, an ai-config session: a comment in
`scripts/test_check_context_closure.py` cited `ai-config#1328` for the change
the same commit was about to make, guessed from the recent numbering before
the PR existed.
It opened as #1334 and merged as `a8bd2604`.
`#1328` is a real, closed, unrelated item, so the citation resolved and
nothing looked broken;
it is also an issue rather than a PR, which the comment got wrong as well.
The wrong number reached `main` and was corrected on a later PR's merge
commit, `3b9d4834`.

Two things distinguish this from the #821 record above, and neither is a new
rule.
The surface was a tracked source comment rather than a PR comment, so no
reviewer read it as a citation and no instrument saw it:
`scripts/check-links.py`'s `SCAN_GLOBS` cover `shared/`, `skills/`, and
`*.md`, never `scripts/`, and it matches only Markdown link syntax.
And the artifact cited was the PR that this very commit would open, so the
section's remedy --- create first, then cite the identifier the create call
returned --- is unavailable in one pass, because the commit has to exist
before the PR does.
That is what made the rule read as inapplicable at the moment of writing.
Either ordering restores it: commit, open the PR, then amend the comment with
the number the API returned;
or cite nothing numeric and name the change and its destination path, which a
reader can check against the filesystem.)

## "A dupe-check chained into the same call as the create"

(Morrison-Lab/ai-config#1954, 2026-08-22: a duplicate issue was filed because
the duplicate-search and the create ran in one Bash call, the list and the
heredoc separated by nothing more than a `;`:

```bash
gh issue list --repo O/R --state open --search "..." --json number,title --limit 10; cat > /tmp/body.md <<'BODY' ... BODY
gh issue create -R O/R --title "..." --body-file /tmp/body.md
```

The search returned the right match --- #1737,
"semantic-line-breaks.py has no clause-break mode, so it disagrees with
new-line-breaks CI and reverts manual fixes" --- and #1952 was created anyway.
The duplicate was then closed and its content moved to a comment on #1737,
which is the disposition step 2 would have selected had its answer been read.

Two things were checked while writing the rule rather than assumed.
At the time (#1956, 2026-08-22), `hooks/warn-pr-create-without-dupe-check.py` matched `gh pr create`, `glab mr create`, and `mcp__github__create_pull_request`, and nothing else.
`grep -rln 'issue create\|create_issue\|issue_write' hooks/*.py` returned eight files: `no-empty-promise.py`, `no-unauthorized-merge.py`, `no-unfiled-finding.py`, `no-unshipped-commit.py`, and the four matching `test-*.py` counterparts.
None of the four guarded a create against a missing or unread dupe-check --- three of them read filing as a *discharge*, and `no-unauthorized-merge.py` only mentioned the phrase in a comment about heredoc quoting.
And that hook's `transcript_has_dupe_check()` walked prior `tool_use` blocks for a lexical match on `gh pr list`/`view`/`status` or `gh search prs`, with a deliberately session-wide discharge, so even on the PR side it established that a query ran and never that its result was consulted.
ai-config#2324 (implementing the proposal filed as #2088) later extended that hook to `gh issue create` / `glab issue create` and the MCP create-issue tools, which covers a *missing* search.
The chained-call failure this case records is a search that ran in the same call as the create, and that remains a separate instrument (`warn-dupe-check-chained-to-create.py`).)
