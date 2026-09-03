Triage the issue backlog on a fixed cadence, and treat closing an issue as not-planned as a normal outcome of that pass rather than as a failure to do the work.

Every open issue carries exactly one priority label, `P1`, `P2`, or `P3`, or is closed.
An unlabelled open issue is untriaged, and untriaged is a state the weekly pass ends.

## Why a counterweight is needed

Two standing rules each generate issues and neither declines any.
[`report-mistakes-proactively`](report-mistakes-proactively.md) files every noticed mistake, however small.
`no-mistake-without-a-hook.py` turns every admitted mistake into a hook, and every hook then generates its own defect stream.
Measured 2026-09-03 across all 1,232 issues in this repo ([ai-config#3134](https://github.com/Morrison-Lab/ai-config/issues/3134)):
the open count went from 15 to 410 in six weeks,
73% of the open issues were agent-tooling self-maintenance,
67% had never been commented on,
and 14 issues in the repo's whole history had been closed as not-planned.
The close rate was not the problem.
It rose roughly sevenfold over the same period.
Filing rose faster, and nothing filed was ever declined.

## The pass

`scripts/triage-backlog.py` is the deterministic half.
It reads every open issue, assigns each one a disposition from its title and labels, and reports how many it examined alongside the per-bucket counts, so an empty bucket reads as a measurement rather than as an unrun rule.
The [`triage`](../../skills/triage/SKILL.md) skill runs it, reviews the plan, applies overrides, and performs the label and close operations.

The dispositions:

- **P1** --- blocks work now, merged bad state, or hides a failure: a guard that denies every call, a merge gate with a hole, a check that is inert where it is needed, a secret that is unset.
- **P2** --- an actionable defect or improvement with a workaround, which is the default.
- **P3** --- a directive with no acceptance criterion, a question, a reading assignment, or a nice-to-have.
- **not-planned** --- a test of the filing mechanism, an aphorism that belongs in `memories/preferences.md` rather than in the tracker, or an item nobody will schedule.
- **duplicate** --- the same title as an older open issue.

The heuristic is a proposal.
Read the P1 and not-planned lists in full before applying, and correct them with `--override`.
Reading all of P2 is not required: the default bucket is where a wrong guess costs least.

## Closing as not-planned is licensed

An issue closed as not-planned is still searchable, still cites its evidence, and can be reopened in one click.
An issue left open with no label and no comment is none of those things in practice: it is indistinguishable from the 300 beside it.
So the pass may close, on its own judgment, an issue that is a bare aphorism, a filing-mechanism test, or a duplicate, and should say in the closing comment which of those it was.
Anything else that looks unlikely to be scheduled gets `P3` rather than a close, because the judgment that it is not worth doing belongs to the maintainer.

## Fold, do not multiply

A hook or checker with a stream of near-identical defects gets one tracking issue with a checklist, not one issue per symptom.
`check-pr-fully-clean` accumulated 72 issues in ten weeks, 24 of them still open at the measurement above, and 22 issues lifetime were about a memory file approaching its line cap.
Under [`report-mistakes-proactively`](report-mistakes-proactively.md)'s dupe-check step, a new symptom of a tracked defect family is a comment on the family's issue, not a new issue.
A bare directive ("less is more", "question everything") is a preference, and its home is a memory entry; it is filed as an issue only when it names a concrete change.

- **Do:** run the pass weekly, label every open issue, and close the bare, junk, and duplicate ones as not-planned with a one-line reason.
- **Do:** append a new symptom to the owning tracking issue when one exists.
- **Do:** read every P1 and every proposed close before applying the plan.
- **Don't:** leave an open issue unlabelled after the pass.
- **Don't:** close an actionable-but-unlikely item as not-planned; label it P3 and leave the call to the maintainer.
- **Don't:** file an aphorism as an issue; record it in memory.
