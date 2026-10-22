# Decision log

Decisions about the lab's repositories and tooling that otherwise exist only in a chat thread.
Format and rules: [`record-every-decision`](../shared/workflow/record-every-decision.md).
Newest first.
Each entry gives the decision, who decided and when, and the thread.

## 2026-10-22

- **`gha` stays one repository.**
  Decided in the thread [Split gha actions by topic](https://claude.ai/code/project/chan_014QLd5McmoUEgMPRiXeVnjS?thread=cmsg_014QLd5McmoUEgMPRiXeVnjS3DwCoFrh938CRvknWL95Kx), 2026-10-21.
  An optional pilot would read rule lists from `psw` and `psc`; it waits on Ezra's go.
- **`gla` and `glr` are public, as new history-free repositories.**
  Decided by Ezra on 2026-10-22, in the thread "Taking gla and glr public".
  The old private repositories were renamed `gla-history` and `glr-history`.
  The process fix is [ai-config#4662](https://github.com/Morrison-Lab/ai-config/issues/4662), and the process is in [`going-public`](../shared/workflow/going-public.md).
- **`grt` becomes public, as a history-free export.**
  Ezra, 2026-10-22.
  The old repository becomes `grt-history`, and the visibility change needs Ezra's go in a Remote Control session.
