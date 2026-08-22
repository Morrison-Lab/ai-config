Treat token cost as a property of a workflow's **shape**, not only of the choices made inside one session.
When a procedure is structurally wasteful --- it loads context nobody reads, re-derives what an instrument could decide once, re-runs what one batched pass would run once, or routes work to a tier that does not need it --- the deliverable is a **change to the workflow**, filed or shipped, rather than a cheaper run of the same procedure.

## Why this needs stating separately from the other two levers

[`CLAUDE.md`](../../CLAUDE.md)'s quota section already carries model tier and compaction.
Both are reactive lever-pulls at a decision point, and both spend less on the work **as shaped**, so their saving expires with the session that made it.
This lever changes the shape, so its saving accrues to every future session instead.

That difference is also why the structural question never arises on its own.
Following an expensive procedure correctly reads as compliance from the inside, and pulling one of the other two levers reads as having managed quota --- so a session can do both, honestly, and never once ask whether the procedure was worth running as written.
[`efficient-pr-babysitting`](efficient-pr-babysitting.md) records the same shape one level down: "A rule that bundles several savings under one recommendation invites reading a precondition on one of them as a precondition on all of them", and "Don't read 'I am applying a written rule' as evidence the rule applies here."

The evidence that the gap is real is in the tracker rather than in an argument.
As of 2026-08-22 this repo carries at least four separately-noticed structural inefficiencies --- [#1138](https://github.com/Morrison-Lab/ai-config/issues/1138) (startup context), [#1499](https://github.com/Morrison-Lab/ai-config/issues/1499) (subagents inherit the whole auto-loaded preamble), [#1852](https://github.com/Morrison-Lab/ai-config/issues/1852) (alias directories are 27% of the skill-listing budget), and [#1916](https://github.com/Morrison-Lab/ai-config/issues/1916) (a quadratic tokenizer run by five `PreToolUse` hooks on every Bash command).
Each was found incidentally.
None was found by a rule saying to look, because no such rule existed.

## Tells, and who owns each

None of these is a new claim.
Each is a fragment this corpus already has, read for its **cost** rather than for the property it was written about --- which is the half none of them states.

- **Always-loaded content that only some sessions read.**
  Demote it to a markdown link, or prune it.
  [`memories/claude-code-context-pools.md`](../../memories/claude-code-context-pools.md) is the authority, and its load-bearing point is counterintuitive: *splitting* an always-loaded file saves nothing, because every piece still loads.
  Only demotion or deletion pays.
- **A judgment call you have now made twice.**
  The third time is an instrument, per [`algorithmatize-checks`](algorithmatize-checks.md) and [`deterministic-tools`](../principles/deterministic-tools.md).
  Those two argue correctness and inspectability.
  The token saving is real and additional, since an instrument's verdict costs a tool call where the judgment costs a reasoning pass every time.
- **A serial loop whose base moves faster than one round of it.**
  Batch it, per [`batch-merge-and-resolve`](batch-merge-and-resolve.md), which supplies the two measurements that decide it rather than leaving it to judgment.
- **A brief that hands over an enumerated set rather than the query deriving it.**
  Per [`derive-dont-enumerate`](derive-dont-enumerate.md): a stale list costs a re-dispatch, and the items that appear between the lists are covered by nobody.
- **Work sitting at the conductor's tier that a cheaper or unbilled one could do.**
  [`delegate-to-opencode`](../../skills/delegate-to-opencode/SKILL.md) is unbilled and [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md) is separately billed, so both come ahead of this session's own quota for bounded mechanical work.
- **A large tool output re-read rather than summarized once.**
  Record the conclusion and stop re-fetching the evidence, per [`efficient-pr-babysitting`](efficient-pr-babysitting.md).

## The instrument for the always-loaded pool

The one pool with a deterministic check already built:

```bash
python3 scripts/check-context-closure.py
```

Measured on `main` at 2026-08-22: 9 files, 243,069 bytes (~60,767 tokens at 4 B/token), which is **43,069 bytes over** the 200,000-byte budget.
Nothing turns red, and that is deliberate rather than a defect --- the script's own comment says the budget "can stay advisory because crossing it is a prompt to decide what comes out".
Read an over-budget line as the prompt it is, and act on it or route it to [#1138](https://github.com/Morrison-Lab/ai-config/issues/1138) rather than noting it and moving on.
Re-run the checker rather than quoting that figure.
The corpus grows several KB a day.

## What "act on it" means

The finding is worth exactly what any other noticed defect is worth, so it routes the same way, per [`report-mistakes-proactively`](report-mistakes-proactively.md).
Fix it in the same stride when the fix is small and in scope.
File it when it is not, with the measurement in the issue body, because a structural inefficiency stated without a number is an opinion.
Neither route is gated on approval.

Two boundaries, so this does not become a licence to wander.

**Efficiency never outranks correctness.**
A cheaper procedure that checks less is not a saving, and this rule must never be read as permission to skip a verification step, shorten a review, or trust a cached verdict.
[`efficient-pr-babysitting`](efficient-pr-babysitting.md) prices one review round at $42.92, and [`fully-clean`](fully-clean.md) still requires one every time.

**Don't restructure a workflow mid-task to save tokens on the task in front of you.**
The change belongs in its own issue or PR, on the corpus, where someone can disagree with it.
A workflow quietly reshaped inside a session that was doing something else is [`incidents-dont-repeal-decisions`](incidents-dont-repeal-decisions.md)'s lapsed decision wearing an efficiency argument.

## Human behaviour is in scope, and a suggestion with no mechanism is not one

A workflow includes the people in it.
A merge-method choice, a habit of trickling review requests, a convention about when to open a stacked PR --- each is a decision about the *shape* of the procedure, each has a token price, and none of them is the agent's to make.
So the tells above apply to human steps exactly as they do to agent ones, and finding one is worth saying.

**Naming the behaviour and stopping there is the near-miss**, and it reads as helpful rather than as evasive.
It is [`no-empty-promises`](no-empty-promises.md)'s failure pointed outward: the suggestion costs nothing to produce, changes no file, and closes the topic on the record, so nobody returns to it.
A behaviour nobody was given a reason to change does not change.

So every suggestion about human behaviour ships **at least one mechanism** for encouraging or enforcing it, in the same reply.
Four rungs, weakest first:

1. **A written rule**, in the skill or doc that owns the action.
   Always available, so it is the floor rather than an option --- there is no case where nothing can be written down.
2. **A visible marker at the moment of the action** --- a PR label, a `> [!IMPORTANT]` alert in the PR body, a bot comment on the thread.
   This is the rung that changes behaviour most per unit of effort, because it makes the wrong action *look* wrong exactly when someone is about to take it, rather than in a document read months earlier.
3. **A guard that intercepts the action** --- a `PreToolUse` hook, a required check.
   Reserve it for a condition a query can decide, per [`algorithmatize-checks`](algorithmatize-checks.md), and default to warning rather than blocking.
   [`pr-on-claim`](pr-on-claim.md) records a `PreToolUse` block considered and **rejected** on exactly this reasoning: "the bias that is safe for a nag is not safe for a refusal", and a genuine block needs adversarial hardening that has to be weighed against what it actually prevents.
4. **A setting that removes the option** --- a repo setting, a branch ruleset.
   Strongest and bluntest.
   It also removes the legitimate uses, so it needs a case that the option has no legitimate use here.

Pick the rung from the cost of the mistake and the cost of a false positive, not from how strongly you hold the opinion.
[`deterministic-tools`](../principles/deterministic-tools.md)'s third-occurrence bar governs rungs 3 and 4: build the guard once the mistake has actually recurred, not because it could.

**The decision stays the human's.**
[`flag-practice-slippage`](flag-practice-slippage.md) sets the manner: name the specific practice and gap, cite the rule or label the opinion as an opinion, say it before the action rather than in the retrospective, and say it **once**.
Shipping a mechanism is not a licence to relitigate a decision already made.

### Worked example: squash-merging a base PR taxes every PR stacked on it

Squash-merging PR A rewrites its commits into one new commit with a new SHA.
A PR B stacked on A still carries A's original commits, so once A lands, git sees the same content twice under two different SHAs and conflicts on every co-touched file.
A **merge commit** makes A's own commits ancestors of the base branch, so B's copies are already reachable and the sync is clean.

Measured in an isolated throwaway repo on 2026-08-22 --- one file, PR A adding two commits, PR B stacked with one:

| base merged with | merging the base back into the stacked branch |
|---|---|
| `--squash` | **CONFLICT** in the co-touched file |
| merge commit | clean |

The price of the squash is one deconflict, one CI run, and one review round **per stacked PR**, and [`efficient-pr-babysitting`](efficient-pr-babysitting.md) measured one review round on this repo at $42.92.

The corpus already pays this tax without having priced it.
[`cascade`](../../skills/cascade/SKILL.md)'s step 3 exists only to remediate it --- it resolves "squash-stack conflicts" by taking the branch side and then proving the merge was content-neutral.
A whole remediation step, for a cost the merge method chooses.
That is the shape to look for: **a procedure that exists to clean up after a choice, where changing the choice deletes the procedure.**

Note what this example does *not* establish.
Squash is a good default for an unstacked feature branch with many small iteration commits, which is why [`merge-it`](../../skills/merge-it/SKILL.md) has it, and nothing here argues against that.
The claim is narrow: it is the wrong method when the PR has open dependents, and whether it does is decidable by one query.

```bash
gh pr list --repo <owner>/<repo> --state open --base "$(gh pr view <N> --repo <owner>/<repo> --json headRefName --jq .headRefName)"
```

## Dogfooding

This fragment is referenced from `CLAUDE.md` by a **markdown link** rather than an `@`-import, so it loads only when read.
An imported file loads at launch for every session regardless of task, so writing the always-loaded-cost rule as always-loaded content would have cost 12,532 bytes on every session to say "watch the always-loaded cost".
Derive that figure rather than estimating it (`wc -c` on this file), which is what the finding that corrected an earlier guess here turned on.
The check on any addition to this corpus is the same one: which pool does it land in, and does every session pay for it.

- **Do:** ask what a procedure costs *by construction*, separately from what this run of it costs.
- **Do:** file the structural finding with its measurement, and route it rather than absorbing it silently.
- **Do:** check which context pool an addition lands in before writing it.
- **Do:** treat a human step as in scope, and ship a mechanism --- a written rule at minimum --- in the same reply that names the behaviour.
- **Don't:** read a pulled lever --- a cheaper subagent, a compaction --- as having answered the structural question.
  Those are the other two levers, and they expire with the session.
- **Don't:** buy a saving with a skipped check.
- **Don't:** reshape a workflow inside a task that was doing something else.
- **Don't:** name a human behaviour change and leave it at that.
  A suggestion nobody was given a reason to adopt is the empty promise pointed outward.
