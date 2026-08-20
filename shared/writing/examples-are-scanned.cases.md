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
