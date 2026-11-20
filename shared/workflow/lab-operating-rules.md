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
  Ask his permission to do the step yourself (a decision card, an approval prompt, or a permission rule you ask to add), then run it.
  Hand him a command to type only for a secret or credential (Ezra, 2026-10-29, ai-config#4842: "don't make me do anything myself unless there's absolutely no other way;
  instead, ask me for permission to do it for me").
  This replaces the 2026-10-26 fallback of giving him one command that runs an idempotent script.
  Enforced by `hooks/no-manual-step-ask.py`, which denies a reply that tells him to type or run a shell command, unless the reply names a secret, token, password or credential.

## Deliverables and approvals

- Ask every multiple-choice question on a decision card (`request_decision`), never as a plain-text option list: "start now or file?", "which option?", lettered or numbered options (Ezra, 2026-11-18, ai-config#5826: "anytime you ask me a multiple choice question, can you use a multiple choice card?").
  This holds for every agent, coordinator and thread alike.
  Enforced by `hooks/no-plain-text-choice.py`; an open-ended question with no fixed answers stays plain text.
- Keep an unanswered decision card last in its thread.
  A card moves when anything is posted after it.
  Ezra has tapped the wrong option because of that, and asked for this rule on 2026-11-19.
  His words: "sometimes a card moves while I'm clicking and I click the wrong choice".
  To post after a card, withdraw it with `close_decision`, make the post, then post the card again as the turn's last thread-visible call.
  His words: "if you want to post something after a card, delete the card and repost it last".
  **Do:** send the message and checklist update first, and post the card last.
  **Don't:** update the checklist or reply under a card still waiting for an answer.
  Enforced by `hooks/no-post-under-open-card.py` (ai-config#5969);
  the reviewer layer is "Posts under an unanswered decision card" in [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md).
- An ask for a deliverable (for example "post the key") authorizes its whole follow-through, including re-uploads and replacements of the same item.
  Never ask again for each step.
  Enforced by `hooks/no-stepwise-approval-ask.py` (ai-config#4726).
- Decide reversible choices yourself, as `daytb` does.
  Ask only for a merge (plain `mwc`) and for an irreversible student-facing change.
- A decision-card tap is Ezra's word for the act the card named: its question, the option he chose and that option's consequence.
  So is a coordinator relay whose `<cited author="user">` entry is his card answer.
  Never ask him to type that act again ("sweep", "open the PR in X") after he tapped it (Ezra, 2026-11-18: "you're asking for too much work from me", ai-config#5839).
  The PR hooks read verified taps through `scripts/lib/card_answer.py`;
  a merge still needs his typed `mwc`, and card text never counts as one.
- When a thread is blocked only because its session predates a hook fix (a hook reaches only sessions started after the merge, from the synced plugin snapshot), restart the work in a fresh thread session instead of asking Ezra to type the old hook's word.
  The coordinator does the restart, with the blocked thread's state in the new brief.
  Collect every typed ask that is still unavoidable (a classifier line, an `mwc` line) into one post, in one fenced block, rather than one post per thread.
  Prose only: no hook can see whether another session's hooks are stale.
- Any approval ask is one line that covers the entire remaining job.
- One approval ask per message.
  A bare "yes" covers only the primary ask, and any use of a credential or key (ssh key, token, secret) is its own single-question ask (Ezra, 2026-11-02, ai-config#4875).
  Enforced by `hooks/no-bundled-approval-ask.py`.
- Give every line Ezra must type or paste in a fenced code block of its own, never only in inline code, quotes or plain text, in every project and thread, the coordinator's project chat included: merge words (`mwc <repo> <pr> <sha>`, `merge 95 and 96`), classifier-clearing lines (`approve push of ...`, `approve editing ...`), `retry <repo>#<n>`, `merge anyway <pr>` and commands.
  The Claude app shows a copy button only on a fenced block (Ezra, 2026-11-15: "always give me the line with a copy button", ai-config#5667;
  restated the same day as "always give me lines in copy blocks" after a coordinator post asked for "merge 95 and 96" inline, ai-config#5685).
  Enforced by `hooks/no-unfenced-typed-line-ask.py`, and checked by [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#typed-lines-without-a-copy-button).
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
- For a timed release to students, set the date in Canvas itself (a file's or assignment's "available from" date), not a scheduled task in the Claude desktop app.
  Such a scheduled task only fires while that app is open, and it only reminds.
  Canvas releases the item by itself, and students see the same date.
  Ezra, 2026-11-03, after a Midterm 2 practice-exam reminder was scheduled: "why not set the publication date in canvas?"

## Sources

- Never answer from memory when a source can be checked.
  Check it and cite what you read (Ezra, 2026-11-04, ai-config#4957).
  See [`check-sources-over-recall`](check-sources-over-recall.md).
  Enforced by `hooks/no-answer-from-recall.py`.
- Never decide a changing condition (quota, availability, runner state) from a note.
  Probe it live in the turn that acts on it, and date every note about one (Ezra, 2026-11-06, ai-config#5018).
  See [`live-state-over-notes`](live-state-over-notes.md).
  Enforced by `hooks/no-waiver-without-live-probe.py`.

## Remote Control

- Never ask Ezra to type "go" in a Remote Control session.
  Start a fresh session on an already approved environment with the brief as its opening task.
  Enforced by `hooks/no-manual-step-ask.py`.
- Never make Ezra the trigger for your own next step ("tell me when to re-check", "say when and I'll merge").
  Schedule the re-check with `send_later` or rely on the PR-activity subscription, fix failures, and merge under a given `mwc` when a PR is fully clean (ai-config#4955).
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
  A dispatched subagent, on a classifier denial, reports the refused command and its stated reason to its caller, and never switches permission modes itself;
  other sessions follow [`ask-for-manual-approval`](ask-for-manual-approval.md).
  Device consent cards are a security boundary, so use environments already approved.
  Not hookable: a denial is not visible to a hook after the fact.

## Questions and decisions

- Ask Ezra one question at a time, never a list.
  Not yet hookable: tracked in [ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698).
- When Ezra says `daytb`, take the coordinator's recommendation.
  It never covers merges.
  Covered by the `daytb` skill.

## Resolving threads

- Before resolving a thread because its work or open question moved to another thread, post one line in it saying why, with a link to the thread that took the work over, as you would when closing an issue as a duplicate.
  A thread resolved without a word looks like a dropped question.
  Ezra, 2026-11-12, after a coordinator resolved a thread that still held an open question: "should the coordinator post a message in the resolved thread explaining why it was resolved, like we would do when we close an issue as a duplicate?"
  ([ai-config#5572](https://github.com/Morrison-Lab/ai-config/issues/5572)).
  Not yet hookable: a thread session cannot see the coordinator's resolve and post tools, so a deny hook on a resolve with no pointer posted waits on checking them (follow-up in ai-config#5572).

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
