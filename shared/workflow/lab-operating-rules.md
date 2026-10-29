# Lab operating rules (Ezra, 2026-10-23)

These rules came out of the coordinator's work with Ezra.
Each was kept only in project memory until [ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698), where Ezra asked that everything learned be recorded in a repo.
Where a condition can be detected, a hook enforces the rule, and this fragment is the reason the hook exists.
The rest are prose because no condition in the transcript can decide them.

## Merging

- A bare `mwc`, or plain words such as "merge when ready", is the merge grant for every ready PR in the thread's scope.
  Never ask Ezra to name PR numbers ("don't make me name each one").
  Enforced by `hooks/no-numbered-merge-word-ask.py` and `hooks/remind-plain-english-merge-word.py`.
- Never offer him a merge button or a manual step, and never ask him to paste, append, or hand-add text into a file.
  Write an idempotent script, test it, and give him one command that runs it (Ezra, 2026-10-26).
  Enforced by `hooks/no-manual-step-ask.py`.

## Deliverables and approvals

- An ask for a deliverable (for example "post the key") authorizes its whole follow-through, including re-uploads and replacements of the same item.
  Never ask again for each step.
  Enforced by `hooks/no-stepwise-approval-ask.py` (ai-config#4726).
- Decide reversible choices yourself, as `daytb` does.
  Ask only for a merge (plain `mwc`) and for an irreversible student-facing change.
- Any approval ask is one line that covers the entire remaining job.
- Routine pushed scripts (Canvas upload and replace, CI_RUNNER and variable scripts) are allow-listed in the user-level settings on the Mac and cf463-02, so the classifier does not demand typed phrases.
  Merge commands are never allow-listed.
  Ezra, 2026-10-25: "stop making me give so many manual orders".

## Built output

- Reuse the CI-built PDF or HTML instead of rendering locally.
  Download it from the repo's `gh-pages` branch or the published site (for example an mlg exam under `solution/Exams/`).
  Canvas uploads always use the CI-built PDF.
  Render locally only when the source changed and CI has not built it yet.
  Enforced by `hooks/warn-local-render-when-ci-built.py` (a warning, ai-config#4724).
  Ezra, 2026-10-25: "isn't it already rendered in mlg ... remember that going forward".

## Remote Control

- Never ask Ezra to type "go" in a Remote Control session.
  Start a fresh session on an already approved environment with the brief as its opening task.
  Enforced by `hooks/no-manual-step-ask.py`.
- Never ask Ezra to start or run Remote Control, or `claude remote-control`.
  He has given standing permission to start it yourself on cf463-02 and the XPS
  (2026-10-15, [`fetch-untrusted-files`](fetch-untrusted-files.md)).
  Ezra, 2026-10-29: "you can run remote control yourself", "you should have known that".
  Call `start_remote_control`; ask only for a prompt the box itself raises or for cf463-02 sudo.
  Enforced by `hooks/no-ask-to-start-rc.py` on hearthbot replies, thread messages and forge comments.
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

## Asking for a merge word

- Ask for `mwc` only once the whole stack is ready: green on every head (all checks, paged) with a clean review of each head.
  Post that as one line when it is true, not before.
  Not hookable: readiness depends on live GitHub state.
