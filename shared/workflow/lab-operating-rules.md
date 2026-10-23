# Lab operating rules (Ezra, 2026-10-23)

These rules came out of the coordinator's work with Ezra.
Each was kept only in project memory until [ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698), where Ezra asked that everything learned be recorded in a repo.
Where a condition can be detected, a hook enforces the rule, and this fragment is the reason the hook exists.
The rest are prose because no condition in the transcript can decide them.

## Merging

- A bare `mwc`, or plain words such as "merge when ready", is the merge grant for every ready PR in the thread's scope.
  Never ask Ezra to name PR numbers ("don't make me name each one").
  Enforced by `hooks/no-numbered-merge-word-ask.py` and `hooks/remind-plain-english-merge-word.py`.
- Never offer him a merge button or a manual step.
  Enforced by `hooks/no-manual-step-ask.py`.

## Remote Control

- Never ask Ezra to type "go" in a Remote Control session.
  Start a fresh session on an already approved environment with the brief as its opening task.
  Enforced by `hooks/no-manual-step-ask.py`.
- A failed start ("device did not pick up") is retried once before anything is reported.

## Denied steps

- A denied push or tool call: retry once unchanged.
  Never route the change through another session.
  Device consent cards are a security boundary, so use environments already approved.
  Not hookable: a denial is not visible to a hook after the fact.

## Questions and decisions

- Ask Ezra one question at a time, never a list.
  Not yet hookable: tracked in [ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698).
- When Ezra says `daytb`, take the coordinator's recommendation.
  It never covers merges.
  Covered by the `daytb` skill.

## Actions budget

- Public repos run Actions for free.
  On private repos, rerun only a PR that is about to merge, and never run mass syncs.
- Confirm a billing failure from the check-run annotations before reporting it.
  A job that fails in about two seconds is usually billing, not code.
  Not hookable: it depends on a live GitHub state.

## Recording what is learned

- Facts Ezra pastes (emails, permissions, grants) go into a repo or library file in the same turn.
  A fact left only in chat is lost.
- A turn that writes project memory must also reach a repo: a hook, check or fragment, a filed issue or PR, a `Mechanism: <url>` line, or `memory only: <reason>`.
  Enforced by `hooks/no-memory-only-learning.py`.
- Every correction Ezra makes becomes a hook or failing check.
  Enforced by `hooks/no-user-correction-without-mechanism.py`.
