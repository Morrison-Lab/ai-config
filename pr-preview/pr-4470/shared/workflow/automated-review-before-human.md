Never ask a person to review work until its automated review is clean or deadlocked.
That holds in every repository, project and forge (GitHub, GitLab, or any other): a GitHub PR, a GitLab MR, a rendered document sent for a read, or any other work product awaiting a person's review.
A status report or a PR/MR check is covered too: list an item as waiting on human review only when its latest commit has a clean automated review.
In a status pass, start the review job, even under a read-only brief ([`status-requests-act`](status-requests-act.md)), when all four hold:

- the review has not run on the latest commit;
- the item is in scope per [`reviewing-prs`](../../memories/reviewing-prs.md);
- no review run is in flight on its head;
- the item is not a draft.

Starting it is the only review-related write this rule adds to a status pass.
In a status pass, report a draft as a draft, and an out-of-scope item as having no clean automated review, rather than un-drafting it or triggering a review on it.
The agent triggers the automated reviews itself.
"Ready for your review" is a claim that this already happened.

## The gate

When about to ask for a review, mark a draft PR or MR ready first, since a draft is not ready for a person and can suppress the forge's review automation ([`put-prs-in-ready-mode`](put-prs-in-ready-mode.md)).
A deliberately draft-gated dependent PR is the exception: it stays in draft, so trigger its automated review explicitly (a `/review`-style comment, or a dispatch where the caller allows it), and let the merge-order alert carry the ordering.
It is not presented to a person as awaiting review until it is un-drafted, and a status pass reports it as draft-gated.

The gate covers items in scope per [`reviewing-prs`](../../memories/reviewing-prs.md);
for anything else, report the review state and trigger nothing.
Before any message that asks a person to review, check these on the current head:

1. **The automated reviews ran on this head.**
   Trigger every configured reviewer yourself once the round's pushes are done:

   - the repo's review workflow, by whichever trigger its caller documents.
     ai-config's `.github/workflows/claude-review.yml` runs on `pull_request` events (not for a bot sender), on a `/review` comment, and on `workflow_dispatch`, but a dispatch issued by `claude[bot]` fails, so an agent session uses `/review`;
     [`ardi`](../../skills/ardi/SKILL.md) covers the `@claude review` and dispatch-only cases.
   - Copilot, per [`copilot-review-before-human`](../vendored/copilot-review-before-human.md).
   - On GitLab, the MR pipeline's review job: find it in `.gitlab-ci.yml`'s `include:` list, per [`self-review-fallback`](self-review-fallback.md), and run it or start a new MR pipeline.

   Where the review runs on push by itself, let that run rather than adding a duplicate, but confirm it actually started and finished on this head.
2. **The verdict is clean, or the loop is deadlocked.**
   Address every finding (fix, rebut, or defer to a filed issue), push, and re-trigger, per [`ardi`](ardi.md) and [`address-every-comment`](address-every-comment.md).
   A deadlock is an item where your rebuttal and the reviewer's re-raise have each failed to persuade the other;
   name it when you ask.
3. **A review that never produced a verdict is not one.**
   A quota skip, a stub with no verdict, a run that never started, or a repo with no reviewer at all leaves the head unreviewed.
   Re-trigger once the quota resets, and meanwhile post an independent adversarial review per [`self-review-fallback`](self-review-fallback.md) and [`adversarial-self-review`](adversarial-self-review.md).
   When no automated reviewer is configured, or the configured one stays unavailable, that posted review, driven to a clean verdict on the current head, stands in as the automated verdict.
   Say so in the request: name the reviewer that did not run and why, and link the stand-in review.
   For a document with no forge thread, put the stand-in review in the request itself, naming the version it reviewed.
4. **The check is an instrument, not a recollection.**
   Run `scripts/check-pr-fully-clean.py` or `scripts/check-mr-fully-clean.py` where they apply, and otherwise re-query the head's review state rather than recall it ([`recheck-review-findings`](recheck-review-findings.md)).

The gate governs when a request may go out, not whether one must, so a repo whose standing instruction is never to request human review (such as `Lacaedemon/sparta` in [`preferences`](../../memories/preferences.md)) is unaffected.
Two cases go to a person without it, and each request says so:

- a redaction PR, whose automated review [`pr-on-claim`](pr-on-claim.md) deliberately withholds, since a reviewer reading the removed lines is the harm;
- an explicit instruction from the user to request a human review now, which is more specific than this rule;
  report the automated review's state in the same reply.

Then ask, and link the clean verdict (or the deadlocked item) in the request.

## Why it is a gate on the request, not a step in the loop

The rule was already in the corpus as step 3 of a PR loop ("request human review only after AI approval or deadlock"), in the `AGENTS.md` section "Request review and drive every started PR to clean" (since replaced by its section "Get a clean automated review before asking a person to review" and this fragment), worded for GitHub pull requests.
The rule was skipped anyway: on 2026-10-02 an agent asked the user to review a GitLab MR on which no automated review had been triggered.
The same day, a scheduled read-only status check listed six GitLab MRs as waiting on the user's review although their manual AI review job had never run;
the rule's PR-loop wording did not read as covering a status pass.
A loop step fires while the agent is driving a PR;
the moment that matters is different --- the agent has finished and is about to hand off --- and nothing at that moment pointed back to the loop.
Stating the rule as a precondition of the request puts it where the handoff happens, and naming every forge stops "PR" being read as "GitHub only".

- **Do:** trigger the automated reviews yourself, drive them to clean or deadlock, and link that verdict when you ask a person to review.
- **Don't:** tell a person a PR, MR or document is ready for their review, or list it as waiting on their review, on a draft or on a head with no clean automated verdict, or treat a quota-skipped review as a pass.

(User, 2026-10-02, on abridge MR !124: "you need to trigger the automated reviews on [the MR] and possibly others;
always do this when you're ready for a review.
don't ask me to review until you get a clean automated review or deadlock.
haven't I told you this before?" and "that should be a global rule for all our work (all projects, all repos)".
Tracked in [ai-config#4240](https://github.com/Morrison-Lab/ai-config/issues/4240) and [ai-config#4241](https://github.com/Morrison-Lab/ai-config/issues/4241).)
