When babysitting a PR (subscribed to its activity, driving ARDI, watching CI), default to the cheapest tool call and the smallest push that actually answers the question or lands the change --- babysitting sessions run for hours and accumulate a lot of small, avoidable overhead otherwise.

**Batch related changes into one push, not several trickled commits.** A code fix, its test, a demo/doc update, and a memory note are all part of the same round --- push them together.
Each separate push re-triggers CI and the review bot from scratch, and two pushes close together race each other's review runs (see [`fully-clean`](fully-clean.md) and gha's own `CLAUDE.md` "canceled review" section for the concrete failure mode this causes).
Fewer, complete pushes mean fewer wasted CI minutes and fewer webhook events to triage.

**A reviewer's "considered but declined to raise" note is not an open item -- a clean verdict standing over it is a stop, and acting on it reopens a settled loop.**
[`ardi`](../../skills/ardi/SKILL.md)'s **Stopping conditions** make a totally clean review -- no raised nits, no non-blocking comments -- one of the three ways the loop ends.
A note the reviewer *considered and explicitly declined to raise as a finding* is exactly that: not a posted finding, so it does not keep the loop open.
Acting on it anyway costs a full round (CI plus a re-review), and the fix can itself draw a fresh declined note, so one clean verdict trickles into several rounds over nothing that was ever blocking.
Default to holding, and spend a round on an optional improvement only when it clearly justifies the cost.

Keep the Copilot observation separate, and do not attribute it to your own pushes.
Copilot posts no formal review when it finds nothing, so `copilot-pull-request-reviewer` can complete `success` with `get_reviews` empty even on a stable, single-push head -- the silent-reviewer state [`fully-clean`](fully-clean.md) owns.
A green Copilot check is therefore not a verdict; read `get_reviews`, and treat its emptiness as "no findings posted", not as approval and not as something a trickled push caused.

- **Do:** report ready when a clean verdict stands over only a note the reviewer declined to raise as a finding.
- **Do:** read a Copilot verdict from `get_reviews`, never from the check run's color.
- **Don't:** treat an explicitly-declined optional note as an open item and spend a round on it -- per [`ardi`](../../skills/ardi/SKILL.md)'s Stopping conditions, a review with no raised findings is a stop.
- **Don't:** read an empty `get_reviews` under a green Copilot check as approval or as self-inflicted; it is Copilot's no-findings behavior.

(Morrison-Lab/ai-config#1115, 2026-08-04: a 23-line CLAUDE.md addition earned **Ready for merge** on round one, with one optional cross-link the reviewer noted but declined to raise.
Acting on it drew a second clean verdict plus a fresh declined note -- a forward-pointing phrase the added cross-link introduced -- and acting on that drew a third: three review rounds for a change mergeable after the first.
Copilot's check went green with `get_reviews` empty on every head, including #1118's stable single-push head, so its silence was its no-findings behavior rather than anything the pushes caused -- an earlier version of this entry wrongly called that silence self-inflicted.)

**When a round needs both a `main` merge and a code fix, merge first, then commit the fix, then push once.**
This is the ordering the batch rule implies but doesn't spell out, and the natural sequence is the wrong one: you fix what the review flagged, push it, then notice `main` moved, merge, and push again --- two pushes seconds apart, two review runs, the second cancelling the first.
Merging first costs nothing (the merge commit and the fix commit both ride out in the same push) and collapses the round to a single review run.
(ai-config#700: pushed the review fix, then merged `main` and pushed again about a minute later; the first review run was cancelled mid-flight and the round cost an extra cycle.)
Run the behind-check as its own step, before composing the push, rather than
folding it into the same command.
An answer that arrives in the same output as the push arrives too late to act
on, so the round still costs the second review run this rule exists to save.
(Morrison-Lab/ai-config#957, 2026-07-31: the behind-check was folded into the
same command as the `git push`, so "3 behind" was read only once the push had
gone out.
The follow-up merge push then cancelled review run `30614715159`, in flight on
the commit it superseded.)

**When CI already reports the specific gap, work from that report instead of re-deriving it locally.** A codecov comment naming the exact missing file/line, or a benchmark comment giving exact before/after numbers, already answers "what's wrong and by how much" --- don't re-run the equivalent check locally (a full coverage-instrumented test suite, a full benchmark sweep) just to rediscover the same fact.
Reserve a local re-run for **verifying a fix**, once you've already decided what to change from CI's own report. (A local re-run is still the right move when you need an apples-to-apples comparison CI's own baseline can't give you --- e.g. confirming a benchmark regression's true magnitude on the same hardware, since CI's baseline was recorded on a different/differently-loaded runner.)

**Give a pure re-post webhook event a one-line acknowledgment, not fresh analysis.** A benchmark comment that updates in place with the same verdict on a later commit, or a demo-transcript re-post after a test-only change, carries no new information --- confirm nothing material changed (a glance at the numbers/timestamps, not a re-investigation) and move on, rather than re-running the reasoning that already covered it.

**Prefer the minimal API call that answers the question.** See [`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md) for concrete cases: `get_check_runs` over `get_status` (the latter can show a stale `pending` after CI has actually finished), and a single targeted field read (e.g. `pull_request_read` `get`'s `head.sha`) over fetching a full PR object plus a separate check-runs call when only one fact is needed.
