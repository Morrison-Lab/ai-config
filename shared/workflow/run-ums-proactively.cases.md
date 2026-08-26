# Case records: run-ums-proactively

Worked-example case records for the rules in
[`run-ums-proactively.md`](run-ums-proactively.md), moved here verbatim to
keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Stale records checker baseline and shallow clones

### Measured baseline (2026-08-16)

Measured against this repo on 2026-08-16:
503 files examined,
3 orphans (`commands/release-pr.md`, `memories/MEMORY.md`, `references/cloud-setup/README.md`),
181 generated wrappers and 2 root entry points exempt.
All three were inspected and are the benign kinds above,
so treat that as the baseline rather than as a backlog.

### Shallow clone behavior

The age bucket carries no information under a shallow clone,
which is what the checker's own output says (`age_informative: false` in `--json`).
`git log` cannot see past the fetch depth,
so every file reads as no older than the oldest fetched commit.
`actions/checkout` clones at depth 1,
so the CI step is advisory for that reason as well as for the orphan bucket's.
Re-run against a full clone (`git fetch --unshallow`) before reading it.

## Are you sure about that?

The questioning case is conditional on the claim being wrong, and
the near-miss is answering the question.

A user (or reviewer) asks "are you sure about that?" about a figure,
a state claim, or a count you just reported.
You re-query, the claim was wrong, and you reply with the corrected
value.
From the inside that is a closed Q&A: they asked, you checked, you
answered.
Nothing merged, no finding was Addressed, and you never said "I was
wrong", so `hooks/remind-ums-after-error.py` does not fire and the
clean-verdict / Address checkpoints are not in scope.

The lesson is the query you should have run before asserting the
claim, which is exactly what
"A false claim about *state*" already says to record --- and that
trigger never saw this path, because the discovery arrived as an
answer to a question rather than as an admission.

If the re-query confirms the claim, answering is enough and no pass
is owed.
The given example names the wrong-claim branch only
(directive, 2026-08-25, on [ai-config#2261](https://github.com/Morrison-Lab/ai-config/issues/2261)).
