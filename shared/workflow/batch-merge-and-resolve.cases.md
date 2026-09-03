# Case records: batch-merge-and-resolve

Worked-example case records for the rules in
[`batch-merge-and-resolve.md`](batch-merge-and-resolve.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "A conflict your sweep found is not a conflict your merge caused" --- 20 conflicts, 2 of them mine

(UCD-SERG/serocalculator#635, 2026-08-07.
The PR consolidated the methodology and simulation vignettes, deleting one and
renaming four out of `vignettes/articles/` into `vignettes/methodology/`.
After it merged, 26 open PRs reported `mergeable: UNKNOWN`, and a
`git merge-tree --write-tree` sweep found 20 genuinely conflicting.
Attribution ran on the merge commit itself:

```bash
git diff --name-status -M "$merge^1" "$merge" | grep -E '^(D|R)'
```

which returned exactly `man/figures/sim-recovery.png` (D),
`vignettes/articles/simulate_xsectionalData.qmd` (D), and four `R099`/`R100`
renames.
Intersecting that set with the 20 isolated **2** as caused --- #511, whose
include pointed at a renamed path, and #510, which edited the deleted vignette.
The other 18 collided on `DESCRIPTION`, `inst/WORDLIST`, a `pkgdown/`
directory removed long ago, and workflow files: ordinary drift in a repo whose
PRs had been open for months.
The subtraction mattered as much as the addition.
PR #555 looked caused, because its conflict was on
`simulate_xsectionalData.**Rmd**` --- a different file, deleted long before by
`19ab811d`, confirmed with `git log --diff-filter=D`.
Without attribution the sweep prescribes claiming and resolving all 20.
The branch behind #511 was a CRAN release branch this session did not own, so
the response at the time was an explanatory comment naming the rename and where
the content went, not a push.
That comment is superseded: #511 was Copilot-authored and assigned to others,
so under `memories/reviewing-prs.md`'s scope test it gets no comment either,
and the current response is a report to the user.
`git show --name-status "$merge"` was the first command reached for and printed
no file list at all --- both merges here are two-parent merges, which is the
case that behaves this way; re-measured against this corpus's own merge
`f6be2ab3`, it
prints only the commit header while `git diff --name-status -M f6be2ab3^1
f6be2ab3` returns `M skills/stack-prs/SKILL.md`, and
`git show --name-status f6be2ab3 | grep -cE '^[ADMR]'` returns 3 for the
`Merge:`, `Author:` and `Date:` header lines.)

## "The batch pass" --- a squash-merge queue that serial chasing could not converge

(Morrison-Lab/ai-config, 2026-07-30/31.
`main` took 7 squash-merges in the hour ending `00:51:57 PT`; over the last 10
first-parent commits the span was 87.1 min and the mean interval 9.7 min.
`git log --merges` reported none of them, the repo being squash-merged.
An agent merged `main` into #946 at `00:42:25 PT`; #943 landed at `00:50:28 PT`
and re-dirtied it 8 minutes later, so the review round never closed.
Five open PRs touched `CLAUDE.md` at that point: #943, #946, #951, #959,
and #961 --- of which #943 and #951 have since merged.
A pairwise sweep of the 8 heads then open found **2 of 8** conflicting with
`main` and **9 of 28** pairs conflicting with each other.
The pair #953 and #961 was one of the 9: each was clean against `main`
and conflicted with the other on `.github/workflows/validate.yml`.
The negative control caught two false all-clears before any zero was trusted:
`--write-tree` exiting 129 on git 2.34.1, and `grep '^<<<<<<<'` returning 0
against a real conflict whose markers were diff-indented.
Both had reported all 28 pairs clean.)

## "A threshold breach that exists only in the sum"

(Morrison-Lab/ai-config #1223 and #1226, 2026-08-06.
`memories/` carries a 1200-line-per-file cap.
`memories/github-actions.md` stood at 1068 lines on `main`; #1223 took it to
1187 and #1226 to 1164, each comfortably under.
Projected across both, `1187 + 1164 - 1068 = 1283`, over by 83.
Both PRs were `CLEAN` with `Ready for merge` verdicts and full green check sets
at the time, and the file sets were derived rather than recalled --- of the four
PRs open, `memories/github-actions.md` was the only path appearing in more than
one.
No ordering avoids it, since both orders reach 1283; after #1223 merged the file
had 13 lines of headroom against #1226's 84-line addition, so #1226 relocated
its section to a new sibling file rather than trimming to fit a budget already
spent.

The enforcement half was measured on #1226's own first push, which failed
`validate` at **step 12, "Run memory-file-size check tests"** --- not at the
later step named "Check for oversized memory files (advisory)", which runs
`scripts/check-memory-file-size.py` with no `--strict` and exits 0 by design.
What gates is the assertion in `scripts/test_check_memory_file_size.py` whose
comment reads "The real corpus must stay under the shipped default, or the
check ships red", calling `cmfs.oversized_files` over the tracked memory files
and exiting 1 on any finding.
So the cap is hard and is enforced from the check's test suite rather than from
the check.
Two sibling files were already at the gate when this was found:
`memories/git.md` at 1199, and `memories/claude-bot-workflows.md` at 1199 after
the trim #1226 made to fit, with `memories/debugging.md` at 1169 --- tracked
as #1228.)
