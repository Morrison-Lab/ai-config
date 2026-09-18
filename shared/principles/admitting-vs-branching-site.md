# Admitting site vs branching site

When enabling a new condition, trigger, or input case,
that condition must be handled at two distinct sites that must agree:

1. **The admitting site:**
   the guard, rule, or filter that decides whether the code **runs** for that case.
2. **The branching site:**
   the downstream execution logic that decides what the code **does** once it runs.

Fixing only the admitting site makes the code execute for the new case,
but leaves the downstream execution logic branching on variables or assumptions
that are invalid, empty, or defaulted for that case.
This creates a false sense of completion:
the diff mentions the condition,
the admitting rule matches the finding's wording,
and CI runs green,
while the actual execution path silently does the wrong thing.

## Why half-fixes survive self-review

A half-fix at the admitting site is peculiarly resistant to casual self-review:

- **The finding names the admitting condition:**
  A review comment or issue typically says "Job X does not run on tags"
  or "Feature Y ignores webhook events".
  The wording directs attention to the admission gate.
- **The diff matches the finding:**
  Adding the admitting rule (e.g. `- if: $CI_COMMIT_TAG`) matches the requested change.
  Reviewing the diff shows the named concept present and accounted for.
- **The branching site never names the new condition:**
  The downstream code that needs changing is the site that *does not* mention the new condition.
  Searching the codebase for the named concept finds only the admitting site you just edited.
- **The branching variable goes silently empty:**
  The downstream code often tests an alternative variable that becomes empty or unset
  under the new condition (e.g. `CI_COMMIT_BRANCH` is empty on a tag pipeline).
  The condition `"${CI_COMMIT_BRANCH}" = "main"` evaluates to false,
  silently routing the new case down an unintended fallback path (such as a diff against an unrelated branch).
- **Shallow tests pass:**
  Text-matching tests or configuration linters only verify that the admitting rule exists in the manifest.
  Because CI rarely triggers the newly admitted condition during the PR itself,
  the defect survives until an external reviewer flags it or production fails.

## The two-site check

Whenever handling a new case, mode, or input trigger, ask two separate questions:

1. **Admission:** Does the case now reach the code?
2. **Branching:** Does the code branch and execute correctly once it arrives?

To find the branching site, do not search for the new condition.
Search instead for the variables and flags that the code tests *instead of* the new condition ---
specifically properties that become empty, unset, or defaulted when the new case is active.

## Testing requirements

Text-matching tests cannot detect an admitting-vs-branching divergence.
A test asserting that `- if: $CI_COMMIT_TAG` appears in a configuration file
proves only that the admitting site was edited.

To verify the branching site:

- **Execute against real fixtures:**
  Extract or invoke the actual execution logic against simulated environments
  for every admitted case (e.g. branch pipelines, tag pipelines, default branch, merge requests).
- **Verify mutation failure:**
  Verify that the test suite fails when the branching site is in the half-fixed state.
  If the test passes when the branching site is untouched, the test is not verifying behaviour.

## A predicate shared by several branches: widening it can steal a case from a stricter sibling

The two-site frame above assumes one admission gate feeding one execution path.
A related but distinct shape recurs in authorization code with several branches in one `if`/`elif` chain, each meant to be authoritative for a different kind of input, where the same downstream predicate (a persona-name lookup, a type matcher) is consulted from more than one arm.
Widening that predicate to admit a new case for the arm you are fixing can make an **earlier** arm match inputs it was never meant to see, silently routing them away from a **later**, stricter arm that was the actual authority for them.
The widened arm is not wrong about the case it was built for;
it now also wins ties it should have lost.

Nothing about this shows up in a diff review of the arm you touched, because that branch continues to behave correctly on its own inputs.
What breaks is a sibling branch elsewhere in the chain, and the failure is silence rather than an error: the sibling's stricter check simply never runs for the stolen input.

(`Morrison-Lab/ai-config#3707` / `#3742`, commits `dd10dca4` and `6ed58075`, 2026-09-17.
`hooks/no-push-without-self-review.py` widened the persona-key set a lookup function reads, to recognize a Codex reviewer dispatch keyed on `agent` or `persona`.
That same lookup is consulted from a branch that ran before the branch carrying the guard's real, stricter provenance check for task-output-tool calls -- a `task_id`-membership test against IDs the guard itself recorded as reviewer dispatches.
Because the persona check now matched more inputs, a task-output call merely *labelled* with a reviewer persona was parsed as a genuine reviewer report: dispatch an unrelated persona in the background, capture its task id, then call the task-output tool with that id plus a `persona` key naming the reviewer and a well-formed clean report -- authorized, with no review having happened.
The hole pre-dated the widening (it reproduced on `origin/main` via a persona key already in the narrower set);
the widening spread it to two more keys.
The fix reorders the chain so the stricter, task-id-gated branch is tested first and is exhaustive for its own input class, so a persona label on that call can never reach the looser branch at all.
Twelve regression cases pin the ordering; reverting it fails all twelve.)

- **Do:** before widening a predicate, list every branch that consults it, not only the one the finding named -- a persona/name/type matcher reused across an `if`/`elif` chain gates more than the arm you are editing.
- **Do:** where two branches can both match the same input, make the stricter, more-authoritative branch's condition run first and exhaustive for its own input class, so a looser sibling can never reach it.
- **Do:** mutation-test a branch ordering the same way any other guard condition is tested -- revert the order and confirm the regression case fails.
- **Don't:** reason about a widened predicate's safety from the arm it was written for;
  ask what else in the same chain reads it.
- **Don't:** assume a hole that appeared alongside a widening was caused by it -- check whether the base branch already reproduces it, since the fix differs (reorder vs. narrow) depending on which is true.

## Closing a bypass promotes the survivor's completeness from harmless to decisive

The section above is about a predicate you *widen* stealing a case from a stricter sibling.
This is about a predicate you never touch, once a later fix removes its sibling path outright rather than reordering around it.

When two paths admit the same case and one is a bypass, closing the bypass does not only remove a hole.
It also promotes the surviving path from *one of two ways in* to *the only way in*, and every gap the surviving path already had changes status at that same moment, with none of its own code touched.
What used to be a near-miss -- caught by the path that just closed -- is now a hard denial that reads exactly like the check having genuinely run and failed.

Nothing about this shows up in a diff review of the closing fix, for the same reason the widening case above is invisible: the code whose completeness now matters is the code that diff never touches.
The check is to ask, for each path removed, what the survivor now decides *alone*, and to derive its coverage rather than assume the completeness it had while something else backed it up.

(`Morrison-Lab/ai-config#3707` / `#3746`, commits `dd10dca4`/`6ed58075` then `24baa1489`, 2026-09-17.
The reorder described above closed the persona-label bypass for retrieval-shaped tool calls, so a `task_id`-membership gate's own key list became those calls' sole provenance.
`taskId` was missing from that list, while a different branch fifty lines below already read `origin.get("taskId")` -- the module knew the spelling;
the gate that had just become decisive did not.
Before the reorder this was harmless: the persona path admitted the call anyway.
After it, a retrieval call spelling its task id that one way was wrongly denied, with the guard's own message describing it as a review that never ran.
The fix was wider than the review that found it: the same spelling was also missing on the *producing* side, where the dispatch result that registers a task id read `task_id`, `conversationId`, and `id`, but not `taskId` either.
A chain closed at one end and left incomplete at the other is no stronger than before the reorder -- fixing only the end the review named would have left the identical class of denial reachable from the other side.)

- **Do:** after removing one of two paths that reach the same outcome, ask what the surviving path now decides *alone*, and re-derive its completeness rather than assuming the coverage it had while something else backed it up.
- **Do:** when a review finds an incompleteness on one side of a producer/consumer chain, check the matching site on the other side before calling the fix done -- a chain is no stronger for being fixed at only one end.
- **Don't:** review only the diff that closes the bypass;
  the code whose risk just changed is the code that diff leaves untouched.

## Widening a lookup from first-match to any-match promotes every shadowed key to a peer

The two sections above are about a *predicate* or a *path* whose scope
changes.
This is the same shift in a *lookup*: when a function that returns only its
first hit is changed to return every hit, a key that used to be masked by an
earlier, more specific key on the same call stops being masked and starts
being trusted on its own.

A low-entropy fallback --- a bare `id`, kept last in an ordered key list
precisely so a more specific spelling is tried first --- is safe exactly
because first-match reaches it only when nothing better is present.
Under any-match it is consulted on every input whether or not a better
spelling is also there, so a coincidental `id` collision between two
unrelated payloads now authorizes on its own, with nothing in the diff that
touched the key list itself.

(`Morrison-Lab/ai-config#3737`, round 7, commit `c2cbd6e3`.
`hooks/no-push-without-self-review.py`'s `_task_ids()` was widened from
returning the first spelling present in `TASK_ID_KEYS` to returning every
spelling present, to fix the producer/consumer disagreement over
`taskId`/`conversationId` the section above records.
`TASK_ID_KEYS`'s own generic `"id"` entry, a low-entropy last resort under
first-match, is now registered unconditionally by any reviewer-dispatch
result carrying an `"id"` field for anything other than a task --- so a
background task numbered the same as an unrelated object's `id` can register
as a reviewer task id and authorize a push that reviewed nothing.
The counter-argument was already written in the same file, on the sibling
constant: `TASK_ID_KEYS_ORIGIN`'s own comment says admitting a bare `id`
there "would test membership for a value that was never a task id" --- an
argument about the *value's meaning*, not about the envelope, and one that
applies to `TASK_ID_KEYS` exactly as written, but was never re-read against
it when the lookup mode changed from first-match to any-match.)

- **Do:** before changing a lookup from first-match to any-match, re-read
  every key ordered *after* the first, since ordering is often doing implicit
  safety work that only first-match enforces.
- **Do:** re-read an argument already written against admitting a
  low-entropy key on a sibling constant, and ask whether it applies to the
  constant you are widening.
- **Don't:** assume a key's presence in an existing list is still safe once
  every present key registers, rather than only the first one found.
- **Don't:** treat "the keys already agree" (this file's own
  admitting-vs-branching argument, and the bypass-closing argument above) as
  covering a widening that changes *how* the keys are consumed rather than
  *which* keys are consumed.

## Related rules

- [`dead-code-is-tech-debt.md`](dead-code-is-tech-debt.md) section 5:
  A structurally identical conjunct nearby is not automatically the same class of dead code --- the companion finding from the same review round on the same file.
- [`fail-fast.md`](fail-fast.md):
  A guard keyed on an empty variable should fail loudly rather than silently taking an invalid fallback.
- [`algorithmatize-checks.md`](../workflow/algorithmatize-checks.md):
  Extract execution scripts into testable units rather than embedding untestable multi-line shell blocks in CI templates.
- Pattern 35 in [`mistake-patterns.md`](../../memories/mistake-patterns.md):
  The recurring failure record for admitting-vs-branching half-fixes.
- [`fixtures-are-not-evidence.md`](../workflow/fixtures-are-not-evidence.md): Every row testing the widened predicate supplied its old key for free and so could not exercise the new ones.

## Do / Don't

- **Do:** audit every downstream execution branch whenever adding or modifying an admission rule.
- **Do:** search for variables that become empty or default in the new case to locate downstream branching sites.
- **Do:** test the actual execution script against concrete fixtures representing each admitted state.
- **Don't:** assume a fix is complete because the diff adds the admitting rule named in the issue.
- **Don't:** rely on text-matching or YAML-presence tests to verify multi-site behavioural fixes.
