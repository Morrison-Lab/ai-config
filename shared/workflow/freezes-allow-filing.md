# A freeze stops new work, not issue filing or your own urgent fixes

Ezra, 2026-11-12: "a freeze shouldn't prevent you from filing issues" ([ai-config#5574](https://github.com/Morrison-Lab/ai-config/issues/5574)).

A freeze is any instruction that stops new work.
Examples are his scope freeze of 2026-11-11 ([ai-config#5530](https://github.com/Morrison-Lab/ai-config/issues/5530)), the [WIP cap](wip-cap.md), [`finish-wave`](../../skills/finish-wave/SKILL.md), and a "don't start anything new" in a thread.
It stops grabbing, claiming, assigning and working issues.
It never stops filing them.

Under that scope freeze, the course project's coordinator found an issue and held back filing it, reading "no new issues" as "no new filings".
Ezra corrected that the next day with the words above.
An unfiled finding is lost when the session ends, which is the failure [`issue-first`](issue-first.md) and [`report-mistakes-proactively`](report-mistakes-proactively.md) exist to prevent.
A freeze is when findings pile up fastest, because nobody is clearing them.

- **Do:** file what you find, or what Ezra suggests, in the same turn, with its usual labels and duplicate search, during any freeze.
- **Do:** leave it unclaimed: no claim comment, no branch, no PR, no assignment to yourself or another thread.
  Say in the reply that it is filed and waits for the freeze to lift.
  The one exception is an urgent issue of your own, below.
- **Don't:** hold a finding back, keep it only in project memory, or list it as an "open item" in a reply because a freeze is on.
- **Do:** work an urgent issue you filed yourself, or one you just added a fresh failure to, even under a freeze.
  Ezra, 2026-11-12: "you can handle urgent issues that you file yourself, even under the freeze".
  Urgent means the defect is hurting work in progress now, such as a merge gate that takes an agent's word (the case was [ai-config#4893](https://github.com/Morrison-Lab/ai-config/issues/4893)).
  Say in the reply that you are working it, and why it is urgent.
- **Don't:** treat filing as permission to start anything else: [`/defer-issue`](../../skills/defer-issue/SKILL.md) is the shape, file and stop.

This is prose because no hook can see an issue that was not filed.
The failure is an absent tool call, and nothing in a transcript marks which findings deserved one.
