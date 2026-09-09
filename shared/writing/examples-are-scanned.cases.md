# Case records: examples are scanned

Case records for [`examples-are-scanned`](examples-are-scanned.md).

## A memory file documenting a wikilink rule broke it with its own examples

`ucdavis/bcs` gates `.claude/memories/*.md` with
`tests/testthat/test-claude-memories-wikilinks.R`, which scans raw
`readLines()` output for a double-bracket link and fails when the named file
does not exist in that directory.

It is worth naming which kind of checker that is, since the fragment turns on
the distinction: line-oriented, with no fence or code-span awareness at all.
Nobody involved owned it during the incident, so the deform-the-example remedy
was the only one available -- unlike this repo's own checkers, which strip code
regions via `scripts/lib/fences.py` and would never have seen the examples.

[#651](https://github.com/ucdavis/bcs/pull/651) added a memory file that hit
this twice, in successive commits.

**First**, a real link to a session-local auto-memory.
That file lives outside the repository, so it has no entry in
`.claude/memories/` and the link dangled.
Caught by CI.

**Then**, the section added to *document* that rule used two literal
double-bracket placeholders as illustrations.
Both matched the test's pattern, neither named an existing file, and the
backticks around them shielded nothing.
Caught by review, not by the author, and not by the previous CI round -- the
first fix had already been pushed and the second defect rode in with it.

The remedy was an angle-bracketed placeholder, which the pattern cannot match
because it requires a letter immediately after the opening brackets, plus a
sentence in the file saying why it is written that way.

Two details generalize past the specific test.

**The red landed somewhere unhelpful, which is what made it expensive.**
The test runs inside an `update-snapshots` job that the three required
`R-CMD-check` OS legs `needs:`, so a dangling link *skipped* those legs rather
than failing anything.
The PR reported `BLOCKED` with nothing visibly red and the cause named only
inside one job's log -- roughly fifteen minutes to be told the wrong thing.

**The local guard built afterwards reproduced the corpus's own
examined-nothing failure.**
Its first draft used `grep -P`.
BSD grep has no `-P`, so on macOS the command exits `invalid option -- P` and
emits nothing, and the check reported `PASS` on a tree carrying a deliberately
injected dangling link.
`grep -E` works on both and the pattern needs no PCRE.

What surfaced it was the negative control plus the denominator: the check
prints links and files scanned, so `0 link(s) across 14 file(s)` read as
broken at a glance where a bare `0 dangling` would not.
That is [`fail-fast`](../principles/fail-fast.md)'s pass-path-equals-failure-path
shape, arriving inside a guard written to prevent exactly this class of
mistake.

Filed as [ucdavis/bcs#653](https://github.com/ucdavis/bcs/issues/653) and
shipped as [#655](https://github.com/ucdavis/bcs/pull/655).
2026-08-19.

## A hook's own remedy text re-triggered on the reply that complied with it

2026-09-08/09, `Morrison-Lab/ai-config#2016` and `#3371`.
Recorded in the main file under "A compliance report is not an escape either";
this entry carries the fuller timeline.

`hooks/no-unfiled-finding.py` blocked a reply that named a defect as worth an `<issue-shaped word>` and filed nothing --- a correct firing, matching the anti-pattern the hook exists to catch.
The finding itself is unrelated to hooks or this file's subject --- a `check-pr-fully-clean.py` attribution gap noticed in passing --- and was then filed as [#3371](https://github.com/Morrison-Lab/ai-config/issues/3371);
its topic does not matter to what follows, only that filing it is what the next reply had to report.

The very next reply reported that filing.
To say what had happened, it restated the wording the earlier reply had been blocked over --- there is no other way to describe what a hook caught without naming what it caught.
`no-unfiled-finding.py` fired again, on a reply that had already done what it demanded, asking for the issue that already existed.

Verified rather than assumed: `gh issue view 3371` returns state `OPEN`, `createdAt: 2026-09-09T01:51:08Z`, which precedes the blocked reply's own turn.
So the second firing was a false positive on a message reporting a true, already-completed discharge, and the first firing on the identical wording was a true positive.
Both are confirmed by reading the transcript's own tool calls rather than by trusting either reply's account of itself.

**Why the phrase-list route is closed here in particular.**
The example case has a remedy that changes the *sentence*: render it so it cannot match.
The negation and quotation cases have no such remedy --- this file's own guidance for both is to fix the detector or absorb the false positive, never to reword a true sentence to dodge it.
This case is like the latter two in offering no sentence-level fix, but for a different reason: the sentence's accuracy is exactly what makes it match, so a vaguer report would dodge the hook and also under-report what was caught, which is a worse trade than absorbing the false positive.
The only fix that does not cost accuracy is behavioural: check the transcript for a filing tool call after the first block and before the second message, which the hook already has the transcript to do.

**Where the finding was tracked.**
The general shape --- a hook matching a mention of its trigger phrase rather than a live use --- was already open as [#2016](https://github.com/Morrison-Lab/ai-config/issues/2016), filed against a different hook (`no-stale-pr-status.py`) and its title names exactly this property: "fires on a MENTION of its trigger phrase, not only a use."
Per this repo's own triage policy, a new symptom of a tracked defect family is a comment on the existing issue, not a new issue, so this occurrence was posted there (comment `5594563791`, 2026-09-09T01:52:34Z) rather than filed as a third issue.
No hook has been fixed as a result of this entry.
