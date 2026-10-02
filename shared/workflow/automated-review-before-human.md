Never ask a person to review work until its automated review is clean or deadlocked.
That holds in every repository, project and forge:
a GitHub PR, a GitLab MR, a rendered document sent for a read, or anything else a person is asked to look at.
The agent triggers the automated reviews itself;
"ready for your review" is a claim that this already happened.

## The gate

Before any message that asks a person to review, check these on the current head:

1. **The automated reviews ran on this head.**
   Trigger every configured reviewer yourself once the round's pushes are done:
   the repo's review workflow (`/review` comment or `workflow_dispatch` where the caller documents one), Copilot, or the GitLab review job.
   In a repo that reviews automatically on push, let that run rather than adding a duplicate,
   but confirm it actually started and finished on this head.
2. **The verdict is clean, or the loop is deadlocked.**
   Address every finding (fix, rebut, or defer to a filed issue), push, and re-trigger,
   per [`ardi`](ardi.md) and [`address-every-comment`](address-every-comment.md).
   A deadlock is an item where your rebuttal and the reviewer's re-raise have each failed to persuade the other;
   name it when you ask.
3. **A review that never produced a verdict is not one.**
   A quota skip, a stub with no verdict, a run that never started, or a repo with no reviewer at all
   leaves the head unreviewed.
   Re-trigger once the quota resets, and meanwhile post an independent adversarial review
   per [`self-review-fallback`](self-review-fallback.md) and [`adversarial-self-review`](adversarial-self-review.md).
4. **The check is an instrument, not a recollection.**
   Run `scripts/check-pr-fully-clean.py` or `scripts/check-mr-fully-clean.py` where they apply,
   and otherwise re-query the head's review state rather than recall it
   ([`recheck-review-findings`](recheck-review-findings.md)).

Then ask, and link the clean verdict (or the deadlocked item) in the request.

## Why it is a gate on the request, not a step in the loop

The rule was already in the corpus as step 3 of a PR loop
("request human review only after AI approval or deadlock"),
near the end of `AGENTS.md`, worded for GitHub pull requests.
It was skipped anyway:
on 2026-10-02 an agent asked the user to review a GitLab MR on which no automated review had been triggered.
A loop step fires while the agent is driving a PR;
the moment that matters is different --- the agent has finished and is about to hand off ---
and nothing at that moment pointed back to the loop.
Stating the rule as a precondition of the request puts it where the handoff happens,
and naming every forge stops "PR" being read as "GitHub only".

- **Do:** trigger the automated reviews yourself, drive them to clean or deadlock, and link that verdict when you ask a person to review.
- **Don't:** tell a person a PR, MR or document is ready for their review on a head with no clean automated verdict, or treat a quota-skipped review as a pass.

(User, 2026-10-02, on abridge MR !124:
"you need to trigger the automated reviews on [the MR] and possibly others;
always do this when you're ready for a review.
don't ask me to review until you get a clean automated review or deadlock.
haven't I told you this before?"
and
"that should be a global rule for all our work (all projects, all repos)".
Tracked in [ai-config#4241](https://github.com/Morrison-Lab/ai-config/issues/4241).)
