# Case records: self-review-fallback

Worked-example case records for the rules in
[`self-review-fallback.md`](self-review-fallback.md), moved here verbatim to
keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Where the cross-vendor directive came from

(Directive source: a public write-up of a multi-agent review workflow, 2026-08:
"Models are from different vendors, and you get better results due to them
having different approaches and different blind spots.
Friction (disagreement) is your friend here."
The corpus already had the mechanisms --- Copilot alongside `claude-review`,
plus [`agy-review-workflow`](../../skills/agy-review-workflow/SKILL.md) and
[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md) --- and no
statement of why to pair across vendors or how to weight their agreement.)

## A session that could reach none of four working reviewers

(`Morrison-Lab/ai-config#1417`, 2026-08-12, filed as
[#1433](https://github.com/Morrison-Lab/ai-config/issues/1433).
A remote session could summon none of four configured reviewers, and each
gate was read rather than inferred.

`claude-review.yml` is `workflow_dispatch`-only, and
`POST .../actions/workflows/claude-review.yml/dispatches` returned
`403 Resource not accessible by integration` --- the session token carries no
`actions: write`.

`claude-bot.yml` carries no job-level `if:` of its own and delegates to
`Morrison-Lab/gha/.github/workflows/claude.yml@v1`, whose job `if:` requires
`author_association` in `["OWNER","MEMBER","COLLABORATOR"]`.
`jules-review.yml` and `antigravity-review.yml` carry the same allowlist
inline.
Reading the callers alone would have found three unconditional-looking
trigger blocks and settled nothing.

The common cause was one identity fact: API **reads** authenticated as the
repo owner, while comment **writes** landed as `claude[bot]` with
`author_association: CONTRIBUTOR`.
All three comment-triggered runs therefore reported `skipped`, not `failure`.

Copilot was the one reviewer that was genuinely down --- requested
successfully, then refused with "unable to review ... reached their quota
limit" --- which is the case this fragment's fallback already covered, and
not the case the entry above is about.

What settled that the others were up rather than broken: `claude-review`
completed successfully on `ums/is-stale-branch-coverage` and
`ums/mechanism-claim-comments` the same day.
So the PR was reported blocked on an external verdict rather than ready, and
was not merged, even though `Morrison-Lab/ai-config` carries a standing `mwc`
grant --- that grant's scope limit is a **fully clean** PR, and a PR one human
action short of a reachable reviewer is not one.)

## The stub-retry skipped on a sentinel denial count

(Morrison-Lab/ai-config, 2026-08-20: two PRs, [#1724](https://github.com/Morrison-Lab/ai-config/pull/1724)
and [#1741](https://github.com/Morrison-Lab/ai-config/pull/1741), produced an
identical `review / claude-review` job signature --- jobs `96364511234` and
`96365603526`, the latter in run `32349569604`.

Read off `actions/jobs/<id>`, both jobs concluded `failure` with the same three
steps deciding it:

| step | conclusion |
| --- | --- |
| `Fail the check if the review did not complete (attempt 1)` | `success` |
| `Retry Claude Code Review after a stub result or action short-circuit` | `skipped` |
| `Resolve final review outcome` | `failure` |

Every other step in both jobs was `success` or `skipped`, which is
[`fully-clean`](fully-clean.md)'s "a job's conclusion is set by whichever step
failed" in its plainest form.

The job log carries the cause across these lines, one intervening line
elided:

```
permission_denials_count could not be parsed from execution result
  (got 'MISSING'); defaulting to sentinel 999999 (gha#370).
[...]
permission_denials_count=999999 (stub-retry max_denials=5)
permission_denials_count=999999 exceeds the stub-retry threshold (5) ---
  this looks like gha#198's pattern, not gha#185's; not marking as retryable.
```

The elided line is `check-review-execution.sh`'s unconditional
`permission_denials_count=<n> (max_denials=<n>)` at line 184, a near-duplicate
of the line following it that differs only by the `stub-retry ` qualifier.

The execution result's own summary earlier in the same log reads
`"permission_denials_count": 0`, so the real count was well inside the
threshold and the run was refused a retry purely on the parser's failure value.
`Morrison-Lab/gha#370` is closed, and the sentinel behaviour it introduced is
what fires here.

The check then reported `Claude review states no verdict (no '### Verdict'
heading or 'Verdict:' line anywhere in its output)` --- the stub signature the
parent fragment already describes --- while the retry meant to recover it never
ran.)

**A near-miss worth recording, because the step shape is not the cause.**
[#1757](https://github.com/Morrison-Lab/ai-config/pull/1757)'s own
`review / claude-review` job (`96501751353`, run `32392491819`) shows the same
three step outcomes --- `Fail the check if the review did not complete
(attempt 1)` `success`, `Retry Claude Code Review after a stub result or action
short-circuit` `skipped`, `Resolve final review outcome` `failure` --- and is
**not** another instance of this defect.
(`require-review` went red behind it, as it does whenever the review job fails,
but that is a separate JOB (`96502554966`) rather than a fourth step, so it is
no part of the signature.)
The claude-review job's log reads `"permission_denials_count": 6` against
`max_denials=5`, and the
workflow says so itself: `this looks like gha#198's pattern, not gha#185's; not
marking as retryable`.
Grepping that log for `999999`, `could not be parsed`, `sentinel`, and
`gha#370` returns zero.
So the gate refused a retry on a genuinely measured count, which is the gate
working rather than failing.

This was first written up here as a third occurrence, and the count was used to
argue the defect had cleared
[`deterministic-tools`](../principles/deterministic-tools.md)'s third-occurrence
bar.
It had not.
**The step signature is shared by at least two distinct causes**, so counting
occurrences by signature inflates the count of either one --- and the inflated
number was doing argumentative work, which is how a miscount becomes a wrong
decision rather than a wrong sentence.
Read the denial count before classifying, and classify the second branch by
cause rather than by the value observed: a parsed count above the threshold is
gha#198, while a `999999` sentinel is this defect whatever the real count was,
because the parse failed and so no count was measured at all.

## A cross-vendor reviewer found seven defects the primary never reached

The cross-vendor preference is argued from theory in
[`self-review-fallback`](self-review-fallback.md) --- two reviewers sharing a
vendor share their blind spots, so their agreement measures the blind spot.
This is the first *measured* instance in this corpus, and it is a stronger case
than the theory predicts: the primary reviewer never produced a verdict at all,
and the cross-vendor one found four genuine security-relevant bypasses.

Measured 2026-08-21/22 on
[ai-config#1884](https://github.com/Morrison-Lab/ai-config/pull/1884), a PR
adding `hooks/no-clobbering-push.py`.

**The primary reviewer failed three times across two runs**, at
$14.52 total, producing no `### Verdict` on any attempt:

| run | attempts | denials | retry step |
| --- | --- | --- | --- |
| 32545411241 | 2 | 3 | ran (`success`) and also stubbed |
| 32546034763 | 1 | 11 | refused, gha#198 branch |

The denials were diagnostic rather than random, which is worth reading before
concluding a reviewer is simply flaky: the blocked calls were an
`awk`/`grep -nP '[^\x00-\x7F]'` non-ASCII scan of the diff, a scratch `Write`
to hold it, and `git log origin/main` to fact-check a claim about repo state.
The reviewer was being denied the checks this corpus tells it to run, and most
of the 11 denials were it retrying spellings of the same blocked scan.
Filed as [gha#579](https://github.com/Morrison-Lab/gha/issues/579).

**A `codex` review then found seven defects**, run read-only against the
checked-out branch with a forced JSON schema and an explicitly adversarial
prompt.
Four were force-push bypasses in a guard whose entire purpose is to catch force
pushes:

- `--force --force-with-lease` was silent, because the guard read the lease as
  a mitigation.
  `git push --help` on `-f, --force` says the flag "disables these checks", the
  lease among them.
- `--dry-run --no-dry-run --force` was silent, because the scan was
  positive-only and every `git push` option has a `--[no-]` form.
- `-fo ci.skip origin HEAD` was silent *and* resolved `ci.skip` as the remote,
  because `-o` is the one short option taking a value and it was missing from
  the cluster alphabet.
- `--repo origin HEAD` checked the wrong remote, because `--repo` was skipped
  as an option value when its value *is* the remote.

The seventh is the one worth generalizing.
The diff cited [`memories/git.md`](../../memories/git.md) as authority for
"a `stale info` refusal is the one case that genuinely needs bare `--force`".
That file says the reverse in as many words: the lease is unsatisfiable rather
than violated, "`--force` is unnecessary, and there is nothing to race".
The citation resolved, so no link checker could see it, and it contradicted the
diff's *own* neighbouring claim that the lease succeeds trivially when the
remote ref is absent.

**Two lessons, and the second is the transferable one.**

The value here was not redundancy but a *different reading* of the same diff,
which is a reason to chase a cross-vendor reviewer beyond mere availability.
Note the limit of what this case shows, though: the primary produced zero
verdicts across three attempts, which is "down" rather than "slow" by this
fragment's own taxonomy, so it is evidence about the value of a second reading
and not about when to reach for one.

And a self-review is systematically weakest on the *mechanism* of the thing it
is reviewing.
The self-review posted on that PR ran the prose fact-check faithfully and found
two real defects in its own prose, and it did not find a single one of the four
parser bypasses, because checking a claim about `git push`'s option grammar
requires re-deriving the grammar rather than re-reading the sentence.
Where a diff encodes a *tool's* behaviour, read that tool's own documentation as
the source, not the diff's description of it.

## A clean same-vendor verdict over eight blocking cross-vendor findings

The case above is the first measured instance of the cross-vendor preference, and it names its own limit: the primary produced zero verdicts across three attempts, so it is evidence about the value of a second reading rather than about when to reach for one.
This is the case that supplies the missing half.
Here the primary did not fail.
It read the reviewed head, and it answered clean.

Measured 2026-08-24 Pacific on [ai-config#2131](https://github.com/Morrison-Lab/ai-config/pull/2131), at head `b744d6a2`.

Only one of the two same-vendor passes examined *that head*:

| reader | rounds | what it read |
| --- | --- | --- |
| the repo's own `claude-review` | 1 | `b744d6a2` itself; **Ready for merge** |
| dispatched `adversarial-reviewer` subagent | 11, pre-push | a sequence of states ending at `5aa36bbe` |

Each of those eleven rounds read a different state, and the branch's own commit messages name them (`594fdce9`: "One blocking finding on `5aa36bbe`").
So the last one is one small branch commit --- `594fdce9`, nine insertions and four deletions --- plus the `origin/main` merge away from the reviewed head.
That gap cuts *for* this record rather than against it, and it is derivable rather than a judgment: every file `codex` raised a blocking finding in --- `hooks/require-agent-disclosure.py`, `skills/gi/SKILL.md`, `skills/post-merge/SKILL.md`, `tool-mappings.md`, `AGENTS.md` --- is byte-identical at `5aa36bbe` and at `b744d6a2` (`git diff --name-only 5aa36bbe b744d6a2 --` over those paths is empty).
So the eleven rounds read exactly the code the eight blocking findings were about, and they still are not a verdict on `b744d6a2`.
Say it that way rather than counting them alongside the one verdict that did examine that head, which would inflate the same-vendor total this record's argument turns on.

`claude-review`'s own findings line reads "None that meet the high-signal bar", followed by two observations it calls very minor and non-blocking.
Quote it that way rather than as "no findings": [`fully-clean`](fully-clean.md) is explicit that "non-blocking", "nit", and "minor" are prioritization labels rather than a pass, and softening the qualifier here would strengthen this record's own argument, which is the direction to be most careful about.

A `codex` pass on the same head then returned 11 findings, 8 of them blocking, and every one was verified real before being accepted.

Two explanations are ruled out by the record itself.
It is not that the primary was flaky, since it completed and produced a real, reasoned verdict at cost.
It is not that the cross-vendor reviewer was noisier, since the findings were checked individually rather than taken on its word.

Three explanations remain, and they are not exclusive, so the case supports the fragment's theory without isolating it.
The first explanation is that theory: two readings that share a vendor share their blind spots, so their agreement measures the blind spot.
The second explanation is **contamination**, recorded in [`adversarial-self-review`](adversarial-self-review.md)'s "The PR's own review history is rationale you cannot withhold" --- the `claude-review` verdict named the eleven prior rounds in its own justification, so the two same-vendor readings were not independent samples and part of their agreement is explained by the second having read about the first.
That confound bears on the one verdict this record rests on, since the eleven pre-push rounds are what it cited.
The third explanation is a **different threshold**: that same verdict scopes its findings line to a "high-signal bar (compile/parse errors, definite wrong-result logic, or clear unambiguous CLAUDE.md violations)", so the two reviewers may have been applying different tests for what counts as a finding rather than holding different blind spots.
The threshold explanation's remedy is the cheapest to state, since a bar can be named in the request; the contamination explanation has cheap remedies of its own, in the section linked below.
Take the case as establishing that a clean same-vendor verdict is not evidence of absence, which all three explanations deliver, rather than as measuring how much of the gap each one accounts for.

The tracking issue is [ai-config#2177](https://github.com/Morrison-Lab/ai-config/issues/2177).
