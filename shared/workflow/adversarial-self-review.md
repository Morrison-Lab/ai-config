Every self-review is an **adversarial review by a separate subagent**.
Whenever this corpus calls for reviewing your own work --- before a push, as the fallback when the external reviewer is down, or the project-conventions pass a clean verdict does not discharge --- dispatch it to a reviewer with its own context and an adversarial brief, and take its findings as findings.
The authoring session never reviews its own diff inline.

[`self-review-fallback`](self-review-fallback.md) governs *when* a self-review is owed and to what standard.
This governs *who performs it*, which that fragment left to the author by default.

## Why the authoring session cannot be the reviewer

A reviewer's job is to read what the diff **says**.
The author knows what it was **meant** to say, and that knowledge is not removable by care --- it is the context the session is made of.
So the author reads the artifact and recovers the intent, which is confirmation rather than review.

This corpus already names the shape.
[`verify-the-right-artifact`](verify-the-right-artifact.md) is about verifying an adjacent artifact thoroughly instead of the target one, and the adjacent artifact here is the intent in your own head --- the one artifact that is never wrong, because it is what the diff was written from.
Nothing about the check feels skipped: the reading is real, the standards are applied, and the answer comes back clean.

Two consequences worth stating separately, because they are easy to run together.

**A subagent buys independence of intent, not independence of vendor.**
A Claude subagent reviewing a Claude diff shares the training and therefore the blind spots, exactly as [`self-review-fallback`](self-review-fallback.md)'s cross-vendor section says.
What it does not share is the account of what the change was for.
Those are different independences, and this rule buys the second one only.

**So the subagent is the floor, not the ceiling.**
For merges, the next section adds a stricter gate still:
a second adversarial review from a different model and harness.

## Cross-model and cross-harness reviews are required for merging, and the harness list is concrete

(Directive from the user, 2026-08-25: "all reviews, even self-reviews, must be
adversarial; don't do them yourself, use a subagent, preferably using a
different model and harness".)

Two gates meet here, and they have different independence bars.

The **self-review duty** (gating a push) takes an adversarial subagent on any
harness, same-harness included --- that floor buys independence of intent,
which is what a push gate needs.
The **merge gate** (see [`fully-clean`](fully-clean.md)) requires more:
a reviewer differing from the authoring session in **both** model and harness,
the only configuration that also buys independence of blind spot.

The user's 2026-08-25 machine inventory names **cursor**, **agy** (CLI),
**opencode**, **claude**, and `codex` wherever installed
([`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md)).
From the authoring session's perspective the ladder filters itself:
any entry sharing your model or your harness does not qualify for this gate,
whatever the list says.
Dispatch in independence-and-availability order ---
`agy` CLI or `opencode` first, then `codex`, then `claude` ---
where each entry qualifies only if both its model and harness
differ from the authoring session.
This review order serves independence and measured availability,
overriding [`delegation.md`](../../memories/delegation.md)'s cost-first
delegation order for general work.
A multi-backend harness qualifies only when both its harness
and its configured model differ from the authoring session.
`cursor` stays out of the active ladder until its headless dispatch
is probed here.
If no qualifying entry remains, autonomous merging waits ---
it never falls through to a same-model or same-harness reviewer.
A quota outage reroutes the dispatch --- it does not license skipping it.
Waiting does not overrule a human:
escalation to the repository owner per [`fully-clean`](fully-clean.md)'s
deadlock rule ends in their manual review and merge decision,
which is the one authority above this gate.

`agy` specifically: its API-dispatch route is retired, but the **agy CLI** is a
separate path and remains available --- see
[`delegation.md`](../../memories/delegation.md)'s delegate ladder.
A retired API never disqualifies a CLI harness
that operates on a separate path from it.

A second directive the same day sets the merge consequence:
"you must not merge, even with mwc enabled,
unless you have a 100% 'all clear' review verdict
from an adversarial review".

This **adds** a gate and replaces none.
Every requirement [`fully-clean`](fully-clean.md) already sets stands unchanged
--- including the external automated PR reviewer's clean verdict at head,
wherever a repo has one ---
and an author-dispatched subagent verdict never satisfies that external gate.
What is added: a merge additionally requires
the author-dispatched cross-model, cross-harness reviewer's
100% all-clear adversarial verdict at the shipping head.
A Needs-more-work verdict blocks until a compliant re-dispatch returns
all-clear at the new head.
A skip notice, a stub, or a stale-head verdict clears nothing.
A split --- one all-clear and another not-clean, nits included --- is not
100% all-clear, and `mwc` does not authorize merging it
(ai-config#2274).
ARD every item from every review, then request fresh reviews.
If no qualifying reviewer is reachable, the merge waits ---
"blocked on reviewer availability" is the honest status ---
and arming an auto-merge while waiting is
[Pattern 12](../../memories/mistake-patterns.md).


The merge-side rules live with the gate they serve:

- **Do:** for any merge, use a reviewer on a **different model and harness**
  from your own
  (agy CLI, opencode, codex,
  claude only for sessions authored outside Claude,
  or cursor once its headless dispatch is measured),
  and report which harness produced each verdict.
- **Don't:** merge anything --- under any grant, `mwc` included ---
  without a 100% all-clear adversarial verdict at the shipping head.
  A skip notice, a stub, an older-head verdict,
  or a same-harness convenience pass clears nothing.
- **Don't:** reuse a passing same-harness pre-push verdict
  to satisfy the merge gate.
  A merge needs its own cross-model, cross-harness verdict
  evaluating the shipping head.


## What "separate" requires

**Its own context window.**
The near-miss is the pass performed in the same turn under a reviewer framing --- "now let me look at this adversarially" --- and it reads as compliance, because the prose that comes out is adversarial in tone and nothing in the output distinguishes it from a dispatched review.
The test is mechanical rather than tonal: an `Agent` call was made, or it was not.

**Foreground, not background.**
A background dispatch returns an agent id rather than a report, so the verdict is not the call's result and the work you are gating cannot wait on it.
This is the Agent tool's own criterion for `run_in_background: false` --- the very next action depends on the answer.

**Read-only.**
The reviewer reports; the author disposes.
A reviewer that can edit turns a finding into a silent fix, which loses the finding and the disposition together.

**No Agent tool, or no reviewer registered here?**
A separate CLI is the same move and a stronger one ---
[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md),
[`delegate-to-opencode`](../../skills/delegate-to-opencode/SKILL.md),
or [`adv`](../../skills/adv/SKILL.md) (`pre-push-review.py`).
`adv` auto-detects and excludes the active agent harness
from rotation via session environment variables;
specify a target directly (`--engine <name>`)
or pass `--exclude-engine cursor` in alternate mode
until headless cursor dispatch is enabled.
The `adversarial-reviewer` persona also lives at `.claude/agents/` and `.opencode/agents/`, which are project agents: a session rooted in another repo may not be able to resolve it at all ([ai-config#1921](https://github.com/Morrison-Lab/ai-config/issues/1921) tracks shipping it alongside the guard).

Note what that CLI fallback does to the pre-push guard, since the two rules meet here and pull opposite ways.
A CLI's verdict never becomes an `Agent` call's `tool_result`, so the guard cannot see it however real the review was.
Prefix the push itself with `ALLOW_UNREVIEWED_PUSH=1` there, and say in the same reply which reviewer produced the verdict and why the subagent route was unavailable --- the override covers a push whose verdict the guard cannot check, not only a push with nothing to check.
The same applies to a session whose reviewer is registered from a stale definition, which is the case on any rollout of a change to the persona itself.
Where no second context is reachable at all, say so in the review itself rather than letting an inline pass be reported as a dispatched one.

**Cursor Cloud has a subagent dispatch.**
On Cursor Cloud, when the session's `Task` tool lists
`adversarial-reviewer`, that is the dispatch
(measured 2026-08-25 PDT on a Grok conductor).
If `Task` is absent or does not list that persona,
that is the CLI-fallback case above.
Morrison-Lab/ai-config's Cursor adapter skips
`no-push-without-self-review.py` until
[#2241](https://github.com/Morrison-Lab/ai-config/issues/2241),
so `ALLOW_UNREVIEWED_PUSH=1` is inert for the adapter
under any reviewer
(see [`memories/cursor.md`](../../memories/cursor.md)).
Call `parse_report()` from the worktree's `hooks/no-push-without-self-review.py`
on the report recovered from the child's transcript
when the worktree hook script exists
(see [`memories/cursor.md`](../../memories/cursor.md)).
Do not import `~/.claude/hooks/`:
it is a different revision from the branch under review.
When the three-dot diff includes
`hooks/no-push-without-self-review.py`,
also parse with `origin/<default-branch>`'s copy, or obtain a CLI review.
If the worktree script is missing, obtain a CLI review.
Do not push unless the verdict is `clean` and the
fingerprint prefix-matches HEAD.
If there is no fingerprint
(including a stale-registered persona),
obtain a CLI review.
The empty `pr-on-claim` `--allow-empty` branch has no report to parse:
do not invent one,
do not refuse that push for lack of a verdict,
and say in the reply that the carve-out was used.
The carve-out is `git rev-list --count origin/<default-branch>..HEAD`
equal to 1 and `git diff --quiet HEAD^ HEAD` exit 0
in the checkout whose push follows.
Exit 1 means a diff; exit 128 means the command failed.
Both conditions passing is the `--allow-empty` pr-on-claim commit.
`git diff origin/<default-branch>...HEAD` empty
in the checkout whose push follows is tree equality,
not "this branch carries nothing".
A net-zero tree of other commits is not the carve-out.
If the dispatch errored, produced no report,
or produced a report whose fingerprint cannot be recovered
(including a stale-registered persona),
obtain a CLI review,
write that reviewer's report to a file under `/tmp`,
and call `parse_report()` on that file.
If Claude Code's native guard is also running, the prefix
is that guard's escape even when the adapter skip makes
it inert for the adapter.

## Brief it with the diff and the standards, never with your rationale

The instinct on writing the brief is to supply the context that makes the change make sense --- what the problem was, why this approach, what the alternatives were.
That re-imports precisely what dispatching was meant to exclude.
A reviewer holding your account of the change checks the diff against **it** rather than against the repo, and agrees, because the two were written by the same session minutes apart.

Give it the base ref, the paths, the standards that apply, and the question.
Where the change's own reasoning matters, it is in the diff --- a comment, a docstring, a fragment --- and the reviewer should be reading it there, where a later reader will.
Scope is not rationale: which branch, which base, where the tests live, and what is out of scope are facts the reviewer cannot derive and must be told.

- **Do:** hand over `git diff <base>...HEAD`, the applicable rules, and the question.
- **Don't:** hand over the case for the change.
  If it is not persuasive from the diff alone, that is the finding.

### The PR's own review history is rationale you cannot withhold

The rule above governs the brief you write.
A reviewer reading the **PR** gets a second channel you never chose to open: the claim comment saying how many rounds ran, the round-by-round commit messages, and the `# round-2 review finding 8` markers a fix left behind in the test file.
Each of those is a true record, and none of them was written as an argument, which is why the effect is invisible from both ends --- nothing in the artifact reads as persuasion, and nothing in the verdict reads as deference.

Measured 2026-08-24 Pacific on [ai-config#2131](https://github.com/Morrison-Lab/ai-config/pull/2131).
The repo's own reviewer returned **Ready for merge** and named the history in its own justification: the PR's history and the round markers baked into the test file "show the near-misses I would normally look for [...] were already found and fixed in earlier rounds, and my independent probing did not surface anything beyond that."
A cross-vendor pass on that same head then returned 11 findings, 8 of them blocking (see [`self-review-fallback.cases.md`](self-review-fallback.cases.md), "A clean same-vendor verdict over eight blocking cross-vendor findings").

**State what is observable, which is narrower than it first looks.**
That verdict also lists nine verification steps it ran, so "it probed less" is a claim about effort that those steps weigh against, and at least one other explanation fits --- the reviewer probed normally and the diff was, in its own words, "almost entirely prose/documentation plus one well-isolated, warn-only hook with unusually thorough self-testing".
What is observable is that **the history entered the justification**: a reason for finding nothing was supplied by the artifact rather than derived from the diff.
That is enough, because a verdict resting partly on prior rounds is partly a re-reading of those rounds, so it is worth less as corroboration than its independence suggests --- however hard it worked.

**A `# round-N` marker is a changelog of past MISSES, not a certificate of coverage.**
It records that one defect was found there once.
It says nothing about the family that defect belonged to, and reading it as evidence of scrutiny inverts its meaning: the marker points at a line that was wrong, and a reader who takes it as a coverage claim reads it as a line that has been checked.

**The loop is self-reinforcing, which is what makes it a rule rather than a matter of care.**
More rounds produce a more reassuring history, which is available as a reason to stop, and a diff that accumulates many rounds is often one complex enough to need more.
So the effect is strongest exactly where it is most costly.
That is [`learn-from-review-findings`](learn-from-review-findings.md)'s convergence rule reaching a reviewer who never ran the earlier rounds: there a series narrows its own search space by inheriting findings, and here a *fresh* reviewer inherits the narrowing from the artifact instead.

- **Do:** quote back the sentences in a verdict that cite the PR's history rather than the diff, and say what independent evidence is left once they are set aside.
- **Do:** label a regression case with the property it pins rather than the round that found it, so the comment is a specification a reviewer can check instead of a report that scrutiny already happened.
- **Don't:** read a long visible review history as coverage --- it is a record of what was found, and every entry marks a place a defect once lived.
- **Don't:** count a verdict that cites prior rounds in its justification as a fully independent round;
  that much of it is a re-reading of the rounds it names, however hard the rest of it worked.

## Run every mechanical style instrument before dispatching, not after

The rule above is about what the reviewer sees.
This one is about what should never reach it: a defect a repo's own
deterministic checker already catches.

A prose diff has several mechanically-checkable style classes --- a semantic
line-break checker, a line-length pass, a forward-reference grep, an
ambiguous-pronoun scan --- each cheap, deterministic, and running in seconds.
None of that is a reason to skip the adversarial round; it is a reason the
round should never be the first thing that finds one of these, per
[`algorithmatize-checks`](algorithmatize-checks.md).
An adversarial round costs real tokens and real time, and spending a round on
a defect a repo script would have caught for free is the same waste
`algorithmatize-checks` names for any other check a human re-derives by hand
--- reviewer judgment substituting for an instrument that already exists.

So run every available mechanical style instrument on the diff, and fix what
it finds, **before** the diff goes to the adversarial reviewer.
And brief the reviewer to report every finding it has in one round, style
findings included, rather than holding some back --- the point of running the
instruments first is to keep the round's own findings down to what only
judgment can catch, not to teach the reviewer that style is someone else's job.

- **Do:** run the repo's own style checkers (NLB, line-length, forward
  references, ambiguous pronouns, or whatever the repo defines) on the diff
  and fix their output before the first adversarial dispatch.
- **Do:** brief the reviewer to report every finding in one round rather than
  holding style findings for a later pass.
- **Don't:** let the adversarial reviewer be the first detector of a defect a
  mechanical instrument already checks for.

(Measured 2026-09-02 driving `Morrison-Lab/ai-config#3025`, a 24-line
addition to `memories/reviewing-prs.md`.
Four adversarial-reviewer rounds ran, each costing roughly 210k tokens: round
1 found a misattributed citation plus word-wrapped lines, round 2 found an
ambiguous "It" and a forward-pointing "below", round 3 found lines of
140--241 characters, round 4 was clean.
Every style class in rounds 1--3 was mechanically checkable before dispatch
--- the NLB checker, an `awk` line-length pass, the `fix-forward-references`
grep, and an ambiguous-pronoun scan --- and running them first would have
collapsed the four rounds to at most two.)

## Its findings are findings

[`self-review-fallback`](self-review-fallback.md) already rules out surfacing a defect in your own review and closing it on your own estimate of its blast radius.
A dispatched reviewer makes that concrete, because the finding now has an author who is not you: give each one Address, Rebut, or Defer-to-a-tracked-issue per [`ard`](../../skills/ard/SKILL.md), in writing, exactly as for a finding from the PR's own reviewer.
"I know why that is fine" is a Rebut, and a Rebut is something you would be willing to post.

## Review the instrument too, not only the change it verifies

The section above says a dispatched reviewer's findings are findings.
This says what to put in front of it, and the answer is wider than the change: **the verification artifacts are part of the diff and get reviewed as such.**

The reason is not symmetry.
A change is guarded by the suite and by the instrument, so a defect in it has two independent detectors.
A defect in the *instrument* has none --- the suite does not test the parity checker, the parity checker does not check itself, and a broken instrument's characteristic output is a reassuring number rather than an error.
That inverts the intuition that tooling is the low-risk part of a diff: it is the part with the fewest detectors, and therefore the part where an independent reader is worth the most.

The corollary is that a green suite is not a reason to shorten the round.
A suite reports that the assertions written so far pass, which is silent about an assertion that cannot fail, a control patching dead code, and a metric over the wrong quantity --- three defects a reader finds by reading and no run finds at all.

So brief the reviewer with the whole diff, naming the verification files explicitly rather than describing them as scaffolding, and ask specifically: what result would this instrument have to produce for the change to be abandoned?
An instrument with no such result is a finding on its own terms, per [`verify-the-right-artifact`](verify-the-right-artifact.md)'s transformation-for-conclusion section.

- **Do:** include tests, controls, harnesses, and parity checkers in the diff the reviewer sees, and name them in the brief.
- **Do:** ask what output would falsify the instrument, and treat "none" as a finding rather than as reassurance.
- **Do:** keep running rounds while findings keep landing;
  a round that finds something is evidence the next one will too.
- **Don't:** describe the verification files as scaffolding, or scope the review to "the actual change" --- that excludes the least-guarded code in the diff.
- **Don't:** read a green suite as a reason to stop early;
  the defects this section is about are invisible to it by construction.

(Measured 2026-08-28 on [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515).
Five adversarial rounds each found real defects against a fully green suite, and three of the five found them in the verification tooling rather than in the change: a parity metric that could not fail, a negative control patching a function that had moved off the execution path, and an assertion comparing a function against itself.
The last of those had let a previously-rejected design pass 299 tests.)

## Give a docs-only diff describing an instrument a full round

The section above says a diff's verification artifacts are the least-guarded part of it.
Its limit case is a diff carrying no code at all: documentation describing how an instrument behaves.
That reads as the safest change available: nothing executes, no suite can break, and the round feels like a copy-edit.
Treat that reading as the risk rather than as a fact about relative rates --- one case cannot establish which diffs get cut short most often, and it does not have to, because the instruction is the same either way: review it at full depth.

The defect it carries is not new here.
[`fact-check-prose`](../writing/fact-check-prose.md)'s "Prose that distills code is a code claim, checked like code" already owns it, names the same psychology, and prescribes the same remedy;
its "condensation of the code that builds it" section extends the rule to a written-out command, and its fenced-block section to program output.
Read those for what the check is.
What this section adds is the **review-side** consequence, which none of them states: that a docs-only diff about instruments invites an early stop, and that the findings cluster rather than scatter when the round runs to depth.

The measured shape is worth carrying because it tells a reviewer where to aim.
The findings cluster, rather than scattering: a consumer described as reading one field when it falls back to another, a format called unparseable when the parser accepts it, a value called rejected when nothing validates it, a set of accepted forms given as two when the code accepts three.
None reads as a guess afterwards, because each is a claim about a file in the same repository, and knowing roughly what that file does feels like having read it.
Where the claim is about which branch fires, read the branch.
A negative claim --- *this form does not parse*, *nothing accepts this* --- is the one to execute rather than reason about.
Reading can settle it, when the parser is small and you read all of it;
what reading cannot tell you is whether you read all of it, and every refuted negative claim in this measurement was made by someone who believed they had.

- **Do:** run each consumer named in the prose against the input the prose describes, before writing the sentence about it.
- **Do:** treat a negative claim about a parser, guard, or matcher as owing an execution, not an argument.
- **Do:** let the round count be decided by whether findings are still landing --- the rule the section above already gives --- rather than by the diff's size or its lack of code.
- **Don't:** read "no code changed" as "nothing here can be wrong" --- the claims changed, and they have no suite.
- **Don't:** describe a fallback, a precedence rule, or an accepted-form list from the shape of the code;
  enumerate it from the code.

(Measured 2026-09-02 on [ai-config#3010](https://github.com/Morrison-Lab/ai-config/pull/3010), a documentation-only change carrying 52 insertions and 1 deletion across four files, of which 34 insertions are to this file.
Twelve adversarial rounds are recoverable from the session: 7, 8, 4, 3, 3, 3, 1, 1, 0, then 4, 1, 0 after the scope reopened.
Nine of those 35 findings were the one shape above, and five of the nine are recoverable, each a claim the named consumer disproves once read or run: that the three payload consumers read the payload and nothing else, when they fall back to prose;
that a bolded verdict phrase does not parse, when it does;
that demoting a disclosure marker changes `_reviewer_identity()`, when the Claude Code footer is deliberately excluded from `REVIEW_AGENT_MARKERS`;
that a non-conforming payload is rejected, when nothing validates it;
and that the pre-push guard accepts two verdict phrasings, when it accepts three.)

## Require detailed and holistic review passes

Reviewers must independently assess both detailed, evidence-backed implementation defects and the whole change:
requirements, intent, cross-file consistency, integration, regression risk, and validation.
A perfunctory scan of isolated diff hunks misses both subtle line-level bugs and systemic architectural drift.

The two passes evaluate complementary failure modes:

1. **Detailed implementation defect audit**:
   - Trace control flow, edge cases, error handling, syntax, regex greediness, and path-escaping at the line level.
   - Fact-check external tool behaviour and claims against direct documentation rather than trusting prose.
   - Detect placeholder comments, cargo-cult code, uninformative naming, and dead code.

2. **Holistic change assessment**:
   - Evaluate whether the implementation satisfies the stated requirements and broader intent.
   - Check cross-file and cross-module consistency across the entire repository.
   - Analyze architectural coherence, integration boundaries, downstream contract impacts, and regression risks.
   - Verify test suite adequacy and whether validation steps would actually fail if the underlying logic broke.

Review outputs must explicitly report both passes, even when one has no findings.
An explicit evaluation of the holistic assessment alongside an itemized findings list (or an affirmative clean declaration `No actionable findings identified.`) proves that both dimensions were thoroughly examined.

- **Do:** require reviewers to conduct and explicitly document both a detailed implementation defect audit and a holistic change assessment.
- **Do:** report the holistic assessment explicitly in review outputs, even when no architectural, integration, or regression issues are found.
- **Don't:** accept a review that stops at superficial surface checks without evaluating the systemic impact on requirements, architecture, cross-file consistency, and validation rigor.

## The posted fallback comment is the reviewer's report, not an author composite

When the self-review is posted as a PR comment, the comment body **is**
the dispatched reviewer's structured report, then the required
disclosure marker from
[`disclose-agent-authorship`](disclose-agent-authorship.md).
The marker is forge attribution, not author recap.
Dispatching the reviewer and then writing a different review body is the
same failure as reviewing inline, one step later: the authoring session
still composed the text that readers treat as the review.

Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234#issuecomment-5415839535).
A foreground `Task` dispatch
(`bc-61fbadd0-7970-5b2d-8775-4924a28e09a1`, catalog name
"Final review HEAD f71c02ea") ran on `f71c02ea`.
The posted comment was author-assembled, labeled
"Fallback self-review", copied the child's
`### Verdict: Ready for merge` and `Reviewed-Commit` lines, and wrapped
them in a 16-item
"Round history that was Addressed, Rebutted, or Deferred" ledger.
That comment is the wrap, not the parent `Task` JSON.
How Cursor Cloud obtains the child's structured report is in
[`memories/cursor.md`](../../memories/cursor.md).

- **Do:** post the dispatched reviewer's structured report
  (Summary / Findings / Verdict / Reviewed-Commit) as the fallback comment,
  then append the required disclosure marker.
  How Cursor Cloud obtains that report is in
  [`memories/cursor.md`](../../memories/cursor.md).
- **Don't:** wrap the verdict in the authoring session's ARD round-history
  recap in the same comment.
- **Don't:** omit the disclosure marker, or treat that marker as license to
  add an ARD ledger.
- **Don't:** paraphrase a missing reviewer body as Ready for merge.

## The mechanism

[`hooks/no-push-without-self-review.py`](../../hooks/no-push-without-self-review.py) gates the pre-push case on Claude Code, per [`algorithmatize-checks`](algorithmatize-checks.md).
It answers three questions rather than one, because provenance alone is not enough.

*Who said it*: a verdict is admitted only from the `tool_result` of an `Agent` call whose `subagent_type` is the reviewer, and only when that result is not an error.
So an inline pass, a verdict quoted out of a file, the guard's own denial message, and a clean report from some other subagent all fail.

*What it said*: restricting provenance does not make a phrase search sound **inside** the admitted body, which is the same failure one layer in --- a review whose closing note quotes the clean verdict it is withholding would read as clean.
So the verdict is the last line that **is** a verdict line, anchored at line start, and a quotation mid-sentence is not one.

*What it was about*: the reviewer states the commit it read as a `Reviewed-Commit: <sha>` line after its verdict, and the guard resolves what the push would actually ship --- reading the refspec, not just `HEAD` --- and compares.
A push ships commits, so anything that changes what would be shipped --- a later commit, a `main` merge, a rebase, a commit a subagent made in a transcript the guard cannot see, or a branch other than the reviewed one --- fails the comparison.
That is also why the review comes **after** committing, which is where [`ardi`](ardi.md) already puts the pause point.

The other cases have no guard and are prose rules here.

- **Do:** dispatch [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md)
  (foreground, read-only) for the pre-push self-review gate,
  and report which agent produced the verdict.
- **Do:** at merge time, satisfy the separate cross-model, cross-harness
  gate defined under "Cross-model and cross-harness reviews are required
  for merging, and the harness list is concrete" above.
- **Do:** re-dispatch after fixing findings, so the clean verdict describes the tree you are shipping.
  Do not report a HEAD as reviewed until a dispatched review of **that** SHA has returned.
  If a fix already moved HEAD, re-dispatch on the current SHA before the next status report.
  (ai-config#2277, 2026-08-26: addressed two wording nits on `92c65d5c` and reported without a review of that SHA until asked.)
- **Don't:** perform a self-review inline under a reviewer framing --- that is the move this rule replaces, and it is indistinguishable from compliance in the output.
- **Don't:** brief the reviewer with the rationale for the change.
- **Don't:** count a subagent's clean verdict as the external verdict [`fully-clean`](fully-clean.md) requires.
  It is a self-review, performed properly.

## A verdict phrase separated from its heading by a line break is no verdict

`VERDICT_LINE` matches `Verdict[ \t]*:` and the phrase on the **same line**, optionally heading-prefixed (`### Verdict: Ready for merge`).
It does not match a heading naming the section with the phrase on the line that follows it:

```
## Verdict

Ready for merge

Reviewed-Commit: <sha>
```

`parse_report` returns no verdict for a report shaped that way, and `read_latest_review` then keeps whichever verdict it last successfully parsed from an **earlier** dispatch in the same transcript --- so a later, clean, correctly-formatted review can be invisible while an older `needs_work` review from before it stands as "the latest."
The refusal then reads "The latest adversarial self-review returned a blocking verdict," which is true about the parsed history and false about what the session actually did.
It is easy to misdiagnose as the transcript lagging a same-turn dispatch --- a plausible-sounding mechanical explanation that was never actually verified, and that ai-config#2444 was originally filed on before this parsing gap was found instead.

[`.claude/agents/adversarial-reviewer.md`](../../.claude/agents/adversarial-reviewer.md) already specifies the one-line form for its own persona.
The gap is any other brief that asks something to act as an adversarial reviewer --- a same-vendor fallback subagent, a CLI dispatch, a hand-written prompt --- without repeating that requirement.

- **Do:** put `Verdict: <phrase>` literally on one line in every review brief you compose, whatever is dispatching it --- `### Verdict: Ready for merge`, never a heading with the phrase on its own following line.
- **Do:** when a guard refuses a push on a verdict you believe is clean, run the guard's own reader (`read_latest_review`/`parse_report`) over the live transcript and print what it parsed per admitted result, before attributing the refusal to a cause like transcript lag.
- **Don't:** treat a heading form (`## Verdict` with the phrase on the next line) as equivalent to the required one-line form --- it parses as no verdict at all.
- **Don't:** file or accept a "the transcript lags the current turn" diagnosis for a refused push without first executing the parser against the actual transcript;
  the two failures produce an identical refusal message.

(ai-config#2444, 2026-08-27: filed on the lag diagnosis, which running `read_latest_review`/`parse_report` directly against the session transcript then refuted --- it returned the older `needs_work` verdict from a mid-session dispatch rather than a stale read of a same-turn one.
The issue's body was rewritten afterwards to lead with the corrected diagnosis and keep the lag theory behind a marked `<details>` block, so read it as the corrected account rather than the filed one.)

**A separate, real constraint: the guard tracks one global latest verdict, not one per branch.**
`read_latest_review` scans the whole transcript and keeps overwriting a single `(verdict, reviewed_commit)` pair with whatever it parses next, with no branch scoping at all.
Reviewing branch A (clean, commit `X`) and then branch B (clean, commit `Y`) leaves `Y` as the global "latest" pair;
pushing branch A afterward compares its shipped commit `X` against the held `Y`, fails the SHA match, and refuses citing an unreviewed commit --- even though branch A's own review was genuinely clean.

- **Do:** review and push one branch before dispatching a review for a second branch in the same session, when driving more than one branch's push through this guard.
- **Don't:** read that refusal as a defect in branch A's review;
  the guard has no notion of "branch" to be defective about, and the SHA comparison is doing exactly what it is built to do.

## Structured review data (JSON payload)

Every reviewer emits two representations of one verdict: the human-readable Markdown report, then a machine-readable JSON payload in a trailing HTML comment.

**"Every reviewer" means every review you post, not only one a dispatched persona wrote.**
The paragraphs around this section are mostly about a review dispatched to the [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) persona before a push,
so the requirement reads as that persona's rather than as a rule about reviews.
It binds every review you post or produce: a forge comment, a local report, a review composed in-transcript.
The one you are likeliest to write without a payload is the review nobody dispatched and no push follows --- a review-only request on somebody else's PR --- since neither the persona nor the pre-push guard is in play there.

Nothing goes red when the payload is omitted, which is why this needs stating rather than more care.
Such a review still yields a verdict its consumers read, since Markdown parsing is every one of their fallbacks when no payload is present.
What a missing payload loses is the per-finding records, which no prose pattern recovers.
The near-miss is a thorough report --- findings reproduced, locations cited, the disclosure marker appended --- where every standard a human reader can see is met and the machine-readable half is the one absent.

The Markdown half owes a verdict line the consumers' own patterns match, and the forms are not interchangeable.
Measured 2026-09-02 against the three consumers, on `Ready for merge`:

| form | `check-pr-fully-clean.py` | `parse_report` | `enforce-mwc-review-gate.py` |
| --- | --- | --- | --- |
| `Verdict: <phrase>` | reads | reads | **no verdict** |
| `### Verdict` then `**<phrase>**` | reads | **no verdict** | reads |
| `### Verdict: <phrase>` | reads | reads | reads |

So write `### Verdict: Ready for merge` or `### Verdict: Needs more work` --- the heading and the phrase on one line, which is the only form all three read.
The phrase matters as much as the form: the pre-push guard accepts `Ready for merge`, `Needs more work`, and `Needs work` and nothing else, so `Verdict: Clean`, `Verdict: Approved`, and `Verdict: Ready` return no verdict there while `check-pr-fully-clean.py` accepts all of them.

- **Do:** append the payload to any review you post or produce, including one nobody dispatched and one no push follows.
- **Don't:** read this section as binding the persona alone --- the persona is where it is already implemented, not where it applies.
- **Don't:** treat a thorough, well-cited, correctly-disclosed report as complete without it;
  that combination is exactly what the omission looks like from the inside.

```html
Reviewed-Commit: <sha>

<!-- review-data:
{
  "schema_version": "1.0",
  "reviewer": "<agent/bot name>",
  "commit_sha": "<full sha>",
  "verdict": "CLEAN",
  "findings": []
}
-->
```

For a not-clean verdict, set `"verdict": "NOT_CLEAN"` and give `"findings"` one object per finding, each with the four keys `file`, `line`, `category`, and `message`.
State those keys in any brief you write, rather than only asking for "finding objects" --- a reviewer that guesses the key names produces `structured finding in unknown: ` as the reported blocking reason.

Name the target repository's schema version in that same brief when it differs from the template above, and its required fields with it --- a version string alone still leaves the reviewer emitting a payload that does not conform to the target's contract, which nothing there validates and so nothing there catches.
A review you compose yourself has no brief to carry that, so read the target's own reviewer prompt before copying the template: `Morrison-Lab/gha`'s asks for `1.1` and two fields this template does not have.
Nothing here reads `schema_version`, and this corpus emits `1.0` --- in that template, in both `adversarial-reviewer` persona files, and in `pre-push-review.py` --- while `Morrison-Lab/gha`'s reviewer prompt requires `1.1` with `detailed_assessment` and `holistic_assessment` fields (measured 2026-09-02, [ai-config#3006](https://github.com/Morrison-Lab/ai-config/issues/3006)).
A reviewer left to copy the template emits `1.0` into a repository asking for `1.1`.

Three rules govern how the payload is read, and each exists because its absence inverted a verdict:

- **The payload must be last, and the last one wins.**
  Last among `review-data` blocks, that is --- [`disclose-agent-authorship`](disclose-agent-authorship.md) still ends a posted comment with its marker, and the two do not conflict: `extract_structured_review` reads a payload the marker follows (verified 2026-09-02), and [`pre-push-review.py`](../../scripts/pre-push-review.py) already emits the report in that order.
  The authoritative payload follows the verdict and the `Reviewed-Commit` fingerprint.
  A reviewer who quotes the template above (it hardcodes `"verdict": "CLEAN"`) before writing its own would otherwise publish a `NOT_CLEAN` review that scored clean.
- **A payload inside a code region does not count.**
  Fences, inline code spans, and indented blocks are all excluded, so a comment that merely mentions the format is not a review of anything.
  This is the same rule `check-pr-fully-clean.py` already applies to quoted *finding* vocabulary (ai-config#2449), applied to a *verdict*.
- **Findings block regardless of the stated verdict.**
  A payload that enumerates findings and then labels itself `CLEAN` is contradicting itself, and the safe reading of a contradiction is the blocking one.

All three consumers read the payload through one extractor, [`scripts/lib/review_payload.py`](../../scripts/lib/review_payload.py): [`scripts/check-pr-fully-clean.py`](../../scripts/check-pr-fully-clean.py) for a comment posted to a PR, [`scripts/pre-push-review.py`](../../scripts/pre-push-review.py) for a report produced locally, and [`hooks/no-push-without-self-review.py`](../../hooks/no-push-without-self-review.py) for the pre-push guard.
They score the same artifact, so they must agree, and one extractor keeps them in agreement: a report whose payload says `NOT_CLEAN` or lists findings scores blocking across all three.
Markdown parsing remains the fallback when no payload is present.

## The review gates the push, not the work --- and it is one round, not a loop

The rule above is a gate on a **push**.
It is not a rule that the work must stop moving until the reviewer is happy,
and reading it that way turns one gate into an unbounded loop.

The failure runs like this.
A review returns findings, you fix them, and the fix needs its own review ---
correctly, since a fix is a diff nobody has read.
So far so good.
The trap is treating each round's fix as something that must clear review
*before the branch can be pushed at all*, because that condition never
arrives: every round produces new code, new code owes a review, and the
commits pile up locally while the loop runs.
Measured on [ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911):
five rounds on one file, every round finding something real, and nothing
pushed for hours.

It reads as rigour from the inside, which is what makes it worth a rule.
Each individual decision to hold is defensible, and the loop is invisible
because no single round is the one that went wrong.

**Pushing is not merging, and the costs run the other way.**
A pushed branch is where CI and the repo's own reviewer can see the code, so
pushing *adds* scrutiny rather than skipping it.
Holding subtracts it, and adds costs of its own: the work is invisible to
other sessions, it is unbacked-up, and its merge conflict with a moving base
grows the whole time.

So the gate is per push and the review is of what that push ships.
Under harnesses without a strict local push guard, once a round's fix is verified ---
its own tests, its own mutation control, its own measurement ---
push it, and let the next review run against the pushed head, which is the head that matters.

**Under Claude Code**, however, the `no-push-without-self-review.py` guard
enforces the loop strictly: a push is rejected by default if the latest review on the branch returned findings.
The primary remedy is not to bypass the guard by pushing mid-round (which the guard blocks without an override),
but to keep each round's scope strictly minimal.
Address the findings, get a clean verdict on that focused diff, and push immediately.

- **Do:** (Non-Claude harnesses) push a verified round and let the reviewer read the pushed head.
- **Do:** (Claude Code) keep the scope of each fix round small so you can achieve a clean verdict quickly, and push the verified round as soon as you obtain a clean local verdict on it.
- **Do:** batch a round's fixes into one push, per
  [`efficient-pr-babysitting`](efficient-pr-babysitting.md), rather than
  trickling or hoarding.
- **Don't:** hold a branch until some future round returns clean if the harness allows pushing ---
  that condition recedes with every fix.
- **Don't:** read a gate on pushing as a gate on shipping any of the work.

(Directive from the user, 2026-08-22, mid-session on #1911: "what are you
waiting for?".
Five commits were sitting unpushed behind a self-imposed review queue while
the branch's conflict with `main` had to be re-resolved twice.
The honest answer to the question was "nothing".)

## Query all available providers sequentially

When obtaining adversarial reviews,
you need a clean verdict from **every** available provider.
You must define the initial pinned quorum by performing an exhaustive discovery/availability check across all known providers (e.g., Cursor, OpenCode, Codex, Copilot, Claude, and the local `adversarial-reviewer` subagent).
Every provider found reachable at the start of the cycle must be included in the pinned quorum.
Any exclusion of a known provider must be recorded explicitly with its reason (e.g., quota blocked, CLI offline).
Do not stop after one provider returns clean.
Query them sequentially, one at a time.
Once one provider gives a clean review,
move on to the next one.
If any provider rejects the diff with findings,
you must address the feedback.
When you make fixes,
**do not hold the branch**:
push the verified fixes immediately.
Pushing the new commit naturally restarts the sequential query process against the new HEAD from the first provider.
When requesting review on the new push,
proactively carry forward any previously accepted rebuttals from earlier providers into your initial review request.
This ensures providers do not redundantly re-raise settled non-code issues on the new diff.
You must submit your rebuttal to the provider and request a new review.
This allows them to post a clean verdict at HEAD
that supersedes their previous findings.
Only after the provider posts a new clean verdict
may you continue to the next provider in the quorum.
Continue this iterative loop of review, fix, and push
until the current HEAD receives clean verdicts from the entire pinned quorum.

The set of required providers must be pinned at the start of the review cycle.
If a pinned provider drops offline or experiences transient operational failures (e.g. 500 errors, rate limits), you must wait and retry.
Alternatively, request explicit user permission to drop it from the quorum.
If the quorum size is zero at the start of the cycle, or drops to zero at any point during the cycle, you must fail closed and wait until at least one becomes reachable.
This applies if, for example, all external providers and the local fallback self-review subagent are offline or fail.
Alternatively, request explicit user permission to proceed.
Do not bypass the review gate.
If any provider (or combination of providers) creates an unbounded loop ---
whether through irreconcilably contradictory requirements,
self-contradictory oscillation,
or endless non-contradictory goalpost-moving ---
halt the review process and escalate to the user for a tie-breaking decision.

## A relayed not-clean round is a standing verdict under your login, so close it with a clean one on the new head

The findings a subagent review returns are worth posting to the PR, and the natural form is one comment: "the review returned Needs more work with N findings;
all N are addressed in <sha>".
That comment is posted under the account's own login, and `scripts/check-pr-fully-clean.py` reads it as that login's latest verdict.
"All addressed" does not clear it, because the instrument keys on the verdict phrase and on the reviewer, and a later all-clear from a *different* reviewer never supersedes a standing not-clean (ai-config#2274).
So the PR reads not-clean under `mwc` however many CLEAN bot rounds follow, until the same login posts a clean verdict on the current head.

The fix is cheap and it is the honest one anyway: once the findings are addressed, run the adversarial reviewer again on the new head and post its verdict, with a `### Verdict` line and the reviewed commit, under the same login.
That is the same-reviewer clean the rule asks for, and it is a real re-review rather than an edit to the old comment.

- **Do:** post a fresh adversarial verdict on the head that carries the fixes, in the same voice and login as the round that found them.
- **Don't:** rely on "all findings addressed in <sha>" inside the not-clean comment, or on later bot verdicts, to clear a not-clean you relayed.

(Measured 2026-09-01 on UCD-SERG/serocalculator#668: the relayed round on `065adf0` read as `d-morrison=not-clean` two CLEAN bot verdicts later, and a fresh Sonnet adversarial review of `2aa82df`, posted with its verdict, was what flipped the instrument to exit 0.)
