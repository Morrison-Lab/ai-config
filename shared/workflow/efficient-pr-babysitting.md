When babysitting a PR (subscribed to its activity, driving ARDI, watching CI), default to the cheapest tool call and the smallest push that actually answers the question or lands the change --- babysitting sessions run for hours and accumulate a lot of small, avoidable overhead otherwise.

Worked-example case records for the rules below live in
[`efficient-pr-babysitting.cases.md`](efficient-pr-babysitting.cases.md), moved out of the auto-loaded context.

**Batch related changes into one push, not several trickled commits.** A code fix, its test, a demo/doc update, and a memory note are all part of the same round --- push them together.
Each separate push re-triggers CI and the review bot from scratch, and two pushes close together race each other's review runs (see [`fully-clean`](fully-clean.md) and gha's own `CLAUDE.md` "canceled review" section for the concrete failure mode this causes).
Fewer, complete pushes mean fewer wasted CI minutes and fewer webhook events to triage.

**The largest part of that saving presupposes that a push triggers a review, so price the cost in this repo before holding a finished commit back.**
The rule above names three savings, and they do not stand or fall together.
Two of them --- the review re-trigger and the `cancel-in-progress` race --- require the repo's review workflow to carry a push-based trigger.
Where it carries only `workflow_dispatch`, a push schedules no review at all, so both of those go to zero.
The third does not: a CI workflow triggered on push still runs, so the wasted CI minutes and the webhook event are still real, and batching still saves them.

Price what remains rather than assuming it is nothing.
Here that is **two** `validate` runs, not one, because `validate.yml` carries `on: [push, pull_request, workflow_dispatch]` and a push to a PR branch fires both the `push` and the `pull_request` event.
Count the check runs rather than the workflows, which is what makes the difference visible:

```bash
gh pr checks <N> --json name,workflow | jq -r '.[] | .name'   # same name, twice
```

That is still a real cost and a small one beside the risk of holding the commit at all, so the conclusion is unchanged --- but note the error ran in the direction that *flattered* the argument, making batching look cheaper to skip than it is.
An error favouring your own conclusion is the one least likely to be re-checked, which is why this one survived a round that had already corrected the sentence around it.

The two prices are asymmetric, which is what decides an uncertain case rather than merely making it a wash.
The avoided cost is a CI run, plus a review run only where a push would have triggered one.
The risked cost is losing committed work outright, since a withheld commit exists only in a working tree an ephemeral container can reclaim.
So even a genuine doubt about whether the precondition holds resolves toward pushing.

Note what the correction does **not** change, because that is the part worth carrying: the conclusion survives, and only its size moved.
A rule that bundles several savings under one recommendation invites reading a precondition on one of them as a precondition on all of them, so itemize before concluding that a rule buys nothing here.

The general form is worth carrying past this rule.
**A cost-avoidance rule is conditional on the mechanism that generates the cost being present here, so confirm the cost exists before paying a real price to avoid it.**
The failure is not disregarding a rule but applying it where its premise does not hold, and it is invisible from the inside: following a written rule feels like compliance, which is the one thing that stops you asking whether the rule applies.
[`challenge-the-assignment`](challenge-the-assignment.md) is the neighbouring rule, and it governs a premise inside a task you were handed rather than one inside a standing rule you invoked on your own initiative.

Note where the gap actually sat, because it was not in the knowledge.
[`ardi`](ardi.md) and [`pr-on-claim`](pr-on-claim.md) both already say to read the review workflow's `on:` block and to dispatch explicitly when it carries no push-based trigger, and [`memories/claude-review-dispatch.md`](../../memories/claude-review-dispatch.md) owns the per-repo trigger facts.
Every one of those fires around a push or a draft-to-ready transition.
None fires when you invoke the batching rule to withhold one, which is the moment the premise needed checking.
One read settles it, once per repo:

```bash
sed -n '/^on:/,/^[a-z]/p' .github/workflows/<review-workflow>.yml
```

- **Do:** confirm this repo's review workflow carries a push-based trigger before withholding a finished commit to batch it.
- **Do:** push when the precondition is uncertain, since one review run is cheaper than losing committed work.
- **Don't:** hold a committed fix out of a push in a dispatch-only repo --- there is no second review run there to avoid.
- **Don't:** read "I am applying a written rule" as evidence the rule applies here.
  That feeling is precisely what suppresses the check.

**A review round is the most expensive thing on the PR, so cancelling one is a real spend rather than a way to save time.**
Every cost this file prices so far is a CI minute or a wasted review-round race.
The direct cost is larger: measured 2026-08-12 on `Morrison-Lab/ai-config`, one round billed **$42.92**, against **$5.91** for the confirming re-review of the same PR.
So a slow review is not a thing to cancel impatiently, and the slowest run is liable to be the one that costs most to repeat.
Whether to cancel a slow run at all is decided by whether the PR's head has moved rather than by how long the run has taken --- [`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s "Whether to cancel a slow review turns on whether the head has moved" carries the criterion, the two runs that showed the same symptom and needed opposite actions, and why a runtime baseline is the wrong instrument.

**A reviewer's "considered but declined to raise" note is not an open item -- a clean verdict standing over it is a stop, and acting on it reopens a settled loop.**
[`ardi`](../../skills/ardi/SKILL.md)'s **Stopping conditions** make a totally clean review -- no raised nits, no non-blocking comments -- one of the three ways the loop ends.
A note the reviewer *considered and explicitly declined to raise as a finding* is exactly that: not a posted finding, so it does not keep the loop open.
Acting on it anyway costs a full round (CI plus a re-review), and the fix can itself draw a fresh declined note, so one clean verdict trickles into several rounds over nothing that was ever blocking.
Default to holding, and spend a round on an optional improvement only when it clearly justifies the cost.
That default is about the fix and not about the fact, so where a declined note asserts something checkable, verify it against the code before writing it off -- the cost argument here holds whether the note is right or wrong, and only checking says which, per [`address-every-comment`](address-every-comment.md)'s "A note the reviewer declined to raise is still a claim".

Keep the Copilot observation separate, and do not attribute it to your own pushes.
Copilot's end-of-run state has been observed in two shapes.
Through August 2026 `copilot-pull-request-reviewer` could complete `success` with `get_reviews` empty even on a stable, single-push head, a silent state whose cause [`review-verdict-pitfalls`](review-verdict-pitfalls.md) leaves unresolved.
That silence is not evidence that Copilot found nothing.
On 2026-09-01 and 2026-09-02 (Pacific) it posted a formal review whose body opens `### 🟢 Approval recommended` with zero generated comments, on [#2983](https://github.com/Morrison-Lab/ai-config/pull/2983) and [#2976](https://github.com/Morrison-Lab/ai-config/pull/2976) respectively.
Two PRs are a sample, so expect either shape until more is measured.
A green Copilot check is therefore not a verdict.
Read `get_reviews`, treat an empty result as "no findings posted", and treat the approval body as the clean verdict, neither of them as something a trickled push caused.

- **Do:** report ready when a clean verdict stands over only a note the reviewer declined to raise as a finding.
- **Do:** read a Copilot verdict from `get_reviews`, never from the check run's color.
- **Don't:** treat an explicitly-declined optional note as an open item and spend a round on it -- per [`ardi`](../../skills/ardi/SKILL.md)'s Stopping conditions, a review with no raised findings is a stop.
- **Don't:** read an empty `get_reviews` under a green Copilot check as approval or as self-inflicted; it is Copilot's no-findings behavior.

**A caveat reporting that the reviewer *could not check* is not a declined note, and the two call for opposite responses.**
The rule above governs a note the reviewer weighed and ranked low.
A reviewer can also report that it was unable to look at all --- a tool gate, a
sandbox restriction, a denied network call --- and it says so in the same
courteous, non-blocking register, inside the same clean verdict, frequently in
the same sentence position.
Reading the second as the first is the error, because it inherits a judgment
nobody ever made.

Two asymmetries decide it.
A review sandbox is usually **more** restricted than the session driving the
PR, since the reviewer runs under a tool-approval gate the driving session does
not, so a claim the reviewer could not settle is frequently one you can settle
in a single command.
And a declined note has been examined by someone and found minor, whereas an
unverified one has been examined by **nobody** --- so holding it is not a
considered risk but an unexamined one, and it reads as considered precisely
because it arrives inside a clean verdict from a careful reviewer.

The discriminating question is cheap enough to run against any caveat in front
of you: **did the reviewer weigh this and rank it low, or report that it could
not look?**
The wording answers it directly.
"Isn't worth another round" and "not worth blocking on" rank a thing.
"Could not independently verify", "denied by this session's tool-approval
gate", and "noting it as unverified" report a blind spot, whatever softening
rides alongside them.
Expect that softening, and discount it: a reviewer routinely attaches its own
guess at importance to the second kind --- "illustrative", "non-load-bearing"
--- and that guess is worth nothing, because it grades an item the same
sentence just said it could not read.

Verifying is not spending a round, which is what keeps this compatible with the
rule above.
Run the check.
Where it confirms the claim, hold exactly as before and the clean verdict still
stands.
Where it refutes the claim you have a defect rather than an optional
improvement, and the cost argument was never about defects.
Run it before the merge, since afterwards the same correction costs a whole PR.

- **Do:** run the reviewer's own blocked check yourself, in the session driving
  the PR, before treating an unverified claim as settled.
- **Do:** discriminate on what the caveat reports --- a ranking or an inability
  --- rather than on how non-blocking it sounds.
- **Don't:** read a reviewer's guess that an unverified item is illustrative or
  non-load-bearing as evidence about that item; it is grading something it did
  not read.
- **Don't:** treat verifying as reopening the loop --- confirming a claim costs
  one command, and holding afterwards is the same stop.

**When a round needs both a `main` merge and a code fix, merge first, then commit the fix, then push once.**
This is the ordering the batch rule implies but doesn't spell out, and the natural sequence is the wrong one: you fix what the review flagged, push it, then notice `main` moved, merge, and push again --- two pushes seconds apart, two review runs, the second cancelling the first.
Merging first costs nothing (the merge commit and the fix commit both ride out in the same push) and collapses the round to a single review run.
Run the behind-check as its own step, before composing the push, rather than
folding it into the same command.
An answer that arrives in the same output as the push arrives too late to act
on, so the round still costs the second review run this rule exists to save.

**When CI already reports the specific gap, work from that report instead of re-deriving it locally.** A codecov comment naming the exact missing file/line, or a benchmark comment giving exact before/after numbers, already answers "what's wrong and by how much" --- don't re-run the equivalent check locally (a full coverage-instrumented test suite, a full benchmark sweep) just to rediscover the same fact.
Reserve a local re-run for **verifying a fix**, once you've already decided what to change from CI's own report. (A local re-run is still the right move when you need an apples-to-apples comparison CI's own baseline can't give you --- e.g. confirming a benchmark regression's true magnitude on the same hardware, since CI's baseline was recorded on a different/differently-loaded runner.)

**Give a pure re-post webhook event a one-line acknowledgment, not fresh analysis.** A benchmark comment that updates in place with the same verdict on a later commit, or a demo-transcript re-post after a test-only change, carries no new information --- confirm nothing material changed (a glance at the numbers/timestamps, not a re-investigation) and move on, rather than re-running the reasoning that already covered it.

**Prefer the minimal API call that answers the question.** See [`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md) for concrete cases: `get_check_runs` over `get_status` (the latter can show a stale `pending` after CI has actually finished), and a single targeted field read (e.g. `pull_request_read` `get`'s `head.sha`) over fetching a full PR object plus a separate check-runs call when only one fact is needed.
