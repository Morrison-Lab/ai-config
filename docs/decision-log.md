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
  Tracked by [ai-config#4700](https://github.com/Morrison-Lab/ai-config/issues/4700).

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
