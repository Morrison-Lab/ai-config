# Decision log

Decisions about the lab's repositories and tooling that otherwise exist only in a chat thread.
Format and rules: [`record-every-decision`](../shared/workflow/record-every-decision.md).
Newest first.
Each entry gives the decision, who decided and when, and the thread.
A reason or an option list that the thread summary did not carry is left out rather than guessed.

## 2026-10-23

- **The ai-config backlog is processed by cluster, and a daily scheduled run keeps it down.**
  Decided by Ezra ("daytb", following the coordinator's recommendation), in the thread "ai-config backlog processing".
  Measured 2026-10-23: 758 open issues, median age 49 days, 581 older than 30 days, 554 with no comment, about 6 closed per day over the previous week.
  Triage closes duplicates, stale items and fixed items with a note, and a cluster of issues about one hook or script gets one fix PR.
  A correction becomes a hook or a failing check, not a new issue, and a new symptom of a tracked script is a comment on its tracking issue, as [`triage-backlog`](../shared/workflow/triage-backlog.md) says.
  The daily run is scheduled at 02:47 America/Los_Angeles.
  It works clusters first, then the oldest issues, at most 10 per run, and never merges.
  It is a scheduled task in the harness (id `trig_013zD2wkY2XsVHYQ3seY3LDy`), not a file in this repository.
  Tracked by [ai-config#4700](https://github.com/Morrison-Lab/ai-config/issues/4700).
- **No merge on a standing grant in Ezra's project threads.**
  A merge there needs Ezra's own typed word, in the thread that owns the PR, for a PR that existed when he typed it.
  Decided by Ezra (the project rule in the DATA 571 project memory);
  restated by the [coordinator session](https://claude.ai/code/session_01RZfvzzeAzADKS6FC1m9VHm) on 2026-10-22 22:14 PDT.
  Slip: I merged [ai-config#4692](https://github.com/Morrison-Lab/ai-config/pull/4692) under ai-config's standing merge grant, in the thread "Documenting every decision".
  The change was a link swap, so it was not reverted.
  It is the second such slip, after [gha#1169](https://github.com/Morrison-Lab/gha/pull/1169), recorded in [ai-config#4689](https://github.com/Morrison-Lab/ai-config/pull/4689).
  The standing-grant sentence in `CLAUDE.md` does not apply in these threads.

## 2026-10-22

- **`gla` and `glr` are public, as new history-free repositories.**
  Decided by Ezra, in the thread "Taking gla and glr public".
  Checked over the GitHub REST API on 2026-10-22: `gla` and `glr` are public, and `gla-history` and `glr-history` exist and are private.
  The process fix is [ai-config#4662](https://github.com/Morrison-Lab/ai-config/pull/4662), and the process is in [`going-public`](../shared/workflow/going-public.md).
- **`grt` is to become public, as a history-free export.**
  Decided by Ezra on 2026-10-22.
  Not done yet: on 2026-10-22 `grt` is still private and `grt-history` does not exist.
  The old repository is to be renamed `grt-history`.

## 2026-10-21

- **`gha` stays one repository.**
  Decided in the thread [Split gha actions by topic](https://claude.ai/code/project/chan_014QLd5McmoUEgMPRiXeVnjS?thread=cmsg_014QLd5McmoUEgMPRiXeVnjS3DwCoFrh938CRvknWL95Kx).
  An optional pilot would read rule lists from `psw` and `psc`, and it waits on Ezra's go.
