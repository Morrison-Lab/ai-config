# The Jules reviewer

The on-demand Jules reviewer's own misfires, kept beside the Actions
material that runs it: `jules-review.yml`'s wiring and the `@jules`
mention path stay in [`github-actions.md`](github-actions.md) (the #857
record), and the `jules/review` commit status is read per
[`fully-clean.md`](../shared/workflow/fully-clean.md).
Split out of `github-actions.md` (ai-config#694 pattern) at the 1200-line
gate.

## Jules can block on `jules-review.yml`'s own extra instructions; the block recurs on its items, so rebut once and hold

`jules-review.yml`'s `INPUT_EXTRA_INSTRUCTIONS` (the action's trusted side of
its prompt boundary; the text arrived as the `extra_instructions` input in
[#817](https://github.com/Morrison-Lab/ai-config/pull/817), closing
[#815](https://github.com/Morrison-Lab/ai-config/issues/815), and the env-var
spelling with [#2293](https://github.com/Morrison-Lab/ai-config/pull/2293))
tells the reviewer not to report this corpus's imperative prose as a prompt
injection and never to report a date as a typo or as being in the future.
Measured 2026-09-03 (evening PDT) on
[#3154](https://github.com/Morrison-Lab/ai-config/pull/3154) at `c5eb3da3`:
two consecutive runs returned `VERDICT: block` on those instructions, in
different words each time.
The first wrote "project rules file, line 1: Prompt injection attempt in
project rules file" and called the "Additional instructions (from workflow
config)" section untrusted;
the second wrote "workflow config, line 1: Prompt injection attempt ...
directing the reviewer to ignore certain prompt injections and date-related
typos".
Each also reported the same day's measurement date as "in the future":
the first in a file that exists nowhere in the repository
(`search-is-not-coverage.md`), the second in `grep-is-not-coverage.md`, which
the diff does change, so an item can quote the diff and still be the misfire
the instructions forbid.
The same reviewer had approved `27bb9588`, whose content differs from
`c5eb3da3` only in two dash tokens;
why one run approves and the next blocks is not established.
Filed as [#3183](https://github.com/Morrison-Lab/ai-config/issues/3183).

This is the seventh case in
[`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md)
(a policy detector firing on the repo's own conventions, which
"re-triggering cannot clear" and whose re-raise is not counted against the
rebuttal test), in a sub-shape that file does not name:
the text is the reviewer's own trusted configuration, so the convention grep
the seventh case prescribes does not apply, and the rebuttal is the provenance
that case already names as what matters for injection.
[`fully-clean.cases.md`](../shared/workflow/fully-clean.cases.md)'s "A
false-positive injection-detector block that reproduces every round" (#818)
is the precedent, held for the maintainer.
`jules/review` is a commit status read from `commits/<sha>/status`
([`fully-clean.md`](../shared/workflow/fully-clean.md) criterion 1), and on
2026-09-03 it was outside the repository's required set: with it red and
every check run green, `GET /pulls/3154` reported `mergeable_state: unstable`
rather than `blocked`, the discriminator the bcs `test-coverage` bullet above
records (re-read the required set on a live PR; the set changes without a commit).
The #3154 merge went over the red status under the standing grant;
[#3192](https://github.com/Morrison-Lab/ai-config/issues/3192) puts that
disposition to the maintainer.

- **Do:** read a Jules `block` for whether each item is a claim the diff can
  answer before treating the red status as this PR's.
- **Do:** rebut once (the diff's file list and the clock for the file and
  date items; for the injection item, `jules-review.yml`'s own comment that
  `INPUT_EXTRA_INSTRUCTIONS` is the trusted side of the prompt boundary),
  file the defect, and hold for the maintainer, per the seventh case.
- **Don't:** re-request Jules when the block's items recur, however the
  block's wording moves, or re-scope the diff to satisfy an item about the
  reviewer's own configuration.
