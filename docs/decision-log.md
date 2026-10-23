# Decision log

Decisions about the lab's repositories and tooling that otherwise exist only in a chat thread.
Format and rules: [`record-every-decision`](https://github.com/Morrison-Lab/ai-config/blob/main/shared/workflow/record-every-decision.md).
Newest first.
Each entry gives the decision, who decided and when, and the thread.
A reason or an option list that the thread summary did not carry is left out rather than guessed.

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
