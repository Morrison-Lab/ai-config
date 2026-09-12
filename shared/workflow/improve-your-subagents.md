Part of an orchestrator's job is to find ways for its subagents to improve over time.
Correcting each output as it arrives keeps the work moving and leaves the mistake rate exactly where it was, because a dispatched agent's mistakes are a function of three things the orchestrator owns: the brief it was given, the memory it could read, and the loop that feeds findings back to it.

The measured shape (2026-09-02, thirteen `agy` dispatches on one Godot repo): every one of eight extra fix rounds was an omission the brief had not named, and the one mistake the agent repeated after recording it had been recorded in a PR worktree its next dispatch never read.
The agent was not the weak link; the briefing was.

## A completion report is not evidence that every item of a multi-part brief was done

Improving a subagent over time still assumes its report tells you what happened.
It does not, for the specific and easy-to-miss case of a brief with more than one deliverable in it.

[`issue-first`](issue-first.md)'s deferral section already names this failure for your own replies to the user: doing two of three requested things and describing only the two is a silent partial delivery, indistinguishable from having done all three unless the reader rereads their own original request.
The same shape arrives from a dispatched agent, and there the orchestrator is the one who must notice it, because the agent that stopped short has no reason to flag what it never attempted.

[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A subagent's report arrives in the same position" section governs a related but different failure: a factual *claim* inside the report that turns out wrong when re-derived.
This is about an item the brief asked for that the report never mentions at all --- there is no claim to fact-check, because the report simply does not address it, and a report that is silent about an item reads exactly like one where that item went smoothly.

A three-part dispatch --- fix the code, fix the tests, correct a filed issue's body to match the fix --- came back describing the first two in detail and never mentioning the third.
Nothing in the report's tone or completeness signaled an omission;
it read as a normal, finished piece of work.
`updated_at == created_at` on the issue, checked directly, settled it in one query: the issue had never been touched.

- **Do:** before accepting a subagent's completion report, list the distinct items the brief asked for and name, for each one, the query that would show it done --- a diff touching the right file, a timestamp that moved, a comment posted.
- **Do:** run that query for every item, not only the ones the report discusses at length.
- **Don't:** read a report's silence about an item as evidence that item needed no separate mention because it went fine.
- **Don't:** treat a report that is detailed and correct about two of three items as evidence about the third;
  detail on the covered items says nothing about the uncovered one.

(Measured 2026-09-09: a dispatched agent given a three-part instruction reported back on the first two parts only.
The third --- correcting a filed issue's body --- was never done and never mentioned as skipped or deferred.
`updated_at == created_at` on the issue via a single API read confirmed it had not been touched since filing.)

## What to change, in order of payoff

**Keep a per-agent mistake ledger and prepend it to every brief.**
A numbered list of standing rules, each one a past mistake stated as the action that avoids it.
It lives in a committed memory file the orchestrator reads from the default branch (the consumer repo's memory directory, or this repo's `memories/` for a cross-repo agent), never in the PR branch the agent is working, so a learning written during one PR reaches the next dispatch on another.
Session auto-memory may hold the in-flight copy, but the committed file is the home, per `CLAUDE.md`'s "Encoding reusable feedback into ai-config" and `memories/preferences.md`'s rule that memories never stay local-only.
Append to it after every fix round.

**Turn each fix round into a change to the loop.**
After a checker or reviewer catches a defect in the agent's output, ask what would have prevented the class: a preamble line, a required self-test, a checker the agent must run and paste, a smaller task ([`learn-from-review-findings`](learn-from-review-findings.md) and [`algorithmatize-checks`](algorithmatize-checks.md) govern the same move for your own work).
Make that change in the same session.
The re-dispatch itself still goes to the same agent, carrying the finding and its own UMS step, per the user's directive tracked as [ai-config#3073](https://github.com/Morrison-Lab/ai-config/issues/3073).
The orchestrator then copies that entry into its own ledger, because a learning written inside a PR worktree is one the next dispatch never reads.

**Give instruments, not adjectives.**
"Be careful with regexes" changes nothing.
"Enumerate the input forms, run each through an `awk 'BEGIN{...}'` block, and paste the output" is checkable, and the paste is what lets the orchestrator verify without re-deriving.

**A repeating shape of finding is itself a signal about the brief, not just about the diff.**
A dispatched adversarial review can converge on real findings and still take
many rounds to reach clean, one round at a time, each round returning exactly
one small (often cosmetic) finding a full CI cycle apart.
That shape --- one finding per round, several rounds running --- is
information the brief is failing to use: a reviewer told to find defects in
what it is given will report the first one it sees and stop, so a
single-track brief and a slow trickle of nits reinforce each other.
Continuing to re-dispatch the same brief treats each round as independent
diligence when the rounds are actually the same missed instruction, repeated.

The fix is a brief change, not a patience change: ask for **one** exhaustive
pass over the entire diff in a single response, with nothing held back for a
later round, and give the reviewer an explicit materiality bar --- report a
finding only if a reader would actually be misled or a check would actually
fail, and say so explicitly when a candidate was considered and dropped for
falling short of that bar.
Naming the bar is what lets a clean verdict be read as "nothing material
found" rather than "nothing found yet."

[`Morrison-Lab/ai-config#3286`](https://github.com/Morrison-Lab/ai-config/pull/3286)
(`hooks/flag-nonconvergent-review.py`, unmerged at the time of writing) is the
algorithmatized detector for the pattern this section fixes by hand: several
`[FINDINGS_COUNT: N]` verdicts with a recurring category or a non-shrinking
tail.
That hook flags the symptom and asks whether to keep going; this section is
one concrete answer to "keep going, but change what you are asking for."

- **Do:** treat two or more consecutive rounds each returning exactly one
  small finding as a brief defect, and rewrite the brief to ask for one
  exhaustive pass rather than dispatching the same brief again.
- **Do:** give the reviewer a stated materiality bar, and require it to name
  a candidate finding it dropped for not clearing that bar.
- **Don't:** read a string of small, individually-valid findings as evidence
  the loop is converging on its own --- a trickle can be the brief's shape,
  not the diff's.
- **Do:** phrase any named checks as *additional* to the reviewer's standing
  checklist rather than as the checklist --- an enumerated brief reads as the
  more rigorous one and silently replaces
  [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md)'s own
  step 2, so the claims you name get verified and their siblings do not.
  (Measured on [ai-config#3481](https://github.com/Morrison-Lab/ai-config/pull/3481),
  2026-09-09: three CI reviewer rounds, two bearing a single finding about one
  `glab` claim while sibling claims in the same six lines sat unchecked, plus
  local adversarial rounds countable only from the session transcript.
  Every brief had named the claims to verify.)
- **Don't:** hand over a bare list of things to verify.
  A reviewer reads an enumeration as the scope of the task, so the round comes
  back clean having checked your list and nothing else --- which is
  indistinguishable from a round that found nothing.

**Brief every identifier-reporting subagent to derive it, never recall it --- and don't accept an identifier back that could have been recalled instead.**
[`ardi`](ardi.md)'s "A SHA you put in a PR body or a reply must be read, never recalled" section already governs the orchestrating session's own citations.
The same failure recurs one level down, in a *dispatched* subagent's own report, and it is worse there because the orchestrator cannot watch it happen --- it only ever sees the finished string.

An `adversarial-reviewer` persona already instructs exactly this ("Read that sha yourself rather than taking it from the brief", present since [#1911](https://github.com/Morrison-Lab/ai-config/pull/1911), well before either measured case below), and the instruction alone did not hold both times it was tested.
[ai-config#3295](https://github.com/Morrison-Lab/ai-config/issues/3295): dispatched with the head as an abbreviated SHA, the reviewer's `Reviewed-Commit:` line echoed the correct 8-character prefix it was handed and invented the remaining 32.
A second, independent instance (d-morrison/rme, measured 2026-09-09): dispatched against a committed diff with no abbreviation in the brief, the reviewer's fingerprint again got the first 9 hex characters right and fabricated the remaining 31 --- consistent with having seen an abbreviated form somewhere in its own tool output (a `git log --oneline`, a commit's own echo) and confabulating a full-length SHA to fill the required field, rather than running `git rev-parse HEAD` as instructed and copying the result.

The near-miss is what makes this hard to catch by reading the report: a fabricated SHA with a correct prefix passes every eyeball check, because a 40-character hex string looks exactly as authoritative whether it was read or invented.
`hooks/no-push-without-self-review.py` only surfaced the second case because it independently resolves what the push would ship and compares SHAs --- and even there, the resulting refusal message ("the clean verdict is for commit X, but this push would ship Y") reads like an ordinary stale-verdict complaint (a later commit, a rebase), not like "the reviewer invented data", so the natural response is to re-review rather than to suspect fabrication.

Two fixes, and both were warranted rather than either alone:

- **In the brief.**
  State the exact command (`git rev-parse HEAD`) and require the output be copied verbatim --- "do not reconstruct or abbreviate it."
  A re-dispatch with that explicit instruction produced a correct SHA on both subsequent tries in the second measured case.
- **In the consumer.**
  Don't trust that the brief-side instruction held.
  `no-push-without-self-review.py` now resolves the reported fingerprint (`git rev-parse <sha>^{commit}`, the same pattern the file already used for resolving push targets) before comparing it to the shipped commits, and refuses with a distinct message ("does not resolve to any commit... fabricated or corrupted, not a stale verdict") when it does not resolve at all --- rather than folding that case into the generic "unreviewed" message, which sends the reader looking for the wrong problem.

Since a persona-level instruction already existed and still failed twice, treat "the brief says to derive it" as necessary but not sufficient: any guard or script that keys off a subagent-reported identifier should resolve or verify it, the same way this one now does, rather than trusting that the identifier is what it claims to be.

- **Do:** name the exact derivation command in the brief when a subagent must report an identifier (a SHA, a run id, a PR number), and require the raw output copied verbatim.
- **Do:** resolve or verify a subagent-reported identifier in the consuming code before trusting it --- a value that *could* have been recalled from context rather than derived gets no benefit of the doubt.
- **Do:** give a fabricated/unresolvable identifier its own error message, distinct from "this is stale" or "this points elsewhere" --- the reader needs to know which defect to suspect.
- **Don't:** treat a persona-level "derive this, don't recall it" instruction as having discharged the risk --- it is necessary, and this class of mistake recurred with it already in place.
- **Don't:** let a correct-looking prefix substitute for verifying the whole value;
  a fabricated tail is exactly what a prefix-only glance misses.

See [`ardi`](ardi.md)'s read-never-recall section for the orchestrator's own-citation analog, and [ai-config#3295](https://github.com/Morrison-Lab/ai-config/issues/3295) for the full first-instance writeup and the guard-side fix this section describes.

**Measure the agent.**
Rounds to clean per PR, and mistakes per dispatch, by class.
Compare briefs and models against those numbers rather than against an impression of the last run.
A model that "does a good job with caveats" is a number that has not been written down.

**Try structural variations.**
A two-pass dispatch that writes, then reviews its own diff against the ledger before returning.
A cheap implementer paired with a different-vendor reviewer, per [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md)'s cross-model review pattern, whose findings become ledger lines.
A task split small enough that the agent's completeness weakness cannot reach it.

**Promote what works.**
A ledger line that has held for several sessions also belongs in the agent's delegation skill as a preamble line, and a mistake that is lexically decidable belongs in a hook, so every orchestrator inherits the improvement rather than re-learning it.

- **Do:** keep a mistake ledger per agent in a committed memory file read from the default branch, and prepend it to every brief.
- **Do:** change the brief, the tooling, or the loop after every fix round, in the same session.
- **Do:** count rounds-to-clean and mistakes-per-dispatch, and compare against them.
- **Do:** promote stable ledger lines into the delegation skill and hooks.
- **Don't:** treat each mistake as an isolated correction and report the agent as fine.
- **Don't:** let an agent's own learning entries live only in a PR worktree its next dispatch never reads.
- **Don't:** stop at proposing an improvement;
  run it in the session that noticed the need.

(Directive from the user, 2026-09-02: "cai: part of your job as an orchestrator is to find creative ways to help your subagents improve over time".
The Do/Don't pairs and the mechanisms are inferred from that one line and the session that prompted it;
the delegation-skill half is tracked as [ai-config#3080](https://github.com/Morrison-Lab/ai-config/issues/3080) and the re-dispatch rule as [ai-config#3073](https://github.com/Morrison-Lab/ai-config/issues/3073).)

(Measured 2026-09-05 on [Morrison-Lab/ai-config#3175](https://github.com/Morrison-Lab/ai-config/pull/3175): four consecutive review rounds each returned exactly one finding, and the last two were single-line label-consistency nits (`# M4` versus `# M4b` in a comment, then the same stale label in a mutation-table key).
Each round cost a full CI cycle.
The brief change described above --- one exhaustive pass, nothing held back, an explicit materiality bar including a request to name a dropped candidate --- produced a clean round on the very next dispatch, which named a nit it had considered and dropped rather than reporting nothing.)

## Send the correction back to the agent; never absorb it yourself

The rule above already routes a re-dispatch to the same agent.
This section exists because that rule was loaded, read, and broken repeatedly in one session anyway, so the instruction alone is evidently not enough.

The near-miss is small fixes.
A dispatched agent returns work that is mostly right, and what is wrong is one line: a heuristic with a misleading message, a comment that reverses a decision an earlier round made deliberately, a commit message the shell expanded a variable into, a rule pair appended into the middle of somebody else's list.
Each of those costs the orchestrator a minute and costs a re-dispatch twenty.
So the orchestrator fixes it, the work moves, and nothing about the next brief changes.

That arithmetic is wrong in a way that is invisible at the moment of choosing, because the minute is real and the saving is not.
The agent will make the same class of mistake on the next dispatch, and the one after that, and the orchestrator will pay the minute again each time while believing it saved one.
The cost of absorbing a fix is not the fix.
It is every future instance of the class, plus the ledger entry that never got written because nothing forced the orchestrator to name what went wrong.

Send it back.
Say what was wrong, say what the agent should have checked, and let the agent make the change.
Where the schedule genuinely cannot take another round, the fix and the ledger entry are one unit: write the rule into the agent's standing brief in the same commit that carries the fix, so the next dispatch is different even though this one was not.

**A correction the agent cannot act on is not a correction.**
"Do not add unsound heuristics" names nothing.
"Your check fired on any command with more than two tokens, which is also true of a command carrying a flag;
state the property of the data that makes a token count sound, or test the thing you mean" names the mistake, the counterexample, and the standard.

- **Do:** re-dispatch with the finding, the counterexample, and the standard, and let the agent make the edit.
- **Do:** write the class into the agent's standing brief in the same commit, on the rare occasion you must apply the fix yourself.
- **Don't:** commit a one-line fix yourself because re-dispatching costs more than fixing --- that comparison omits every later instance of the class.
- **Don't:** send back an adjective; send the input that broke it.

(Directive from the user, 2026-09-11: "don't fix subagents mistakes yourself;
help them do it themselves.
Follow the teach a man to fish principle."
It followed a session driving [ai-config#3435](https://github.com/Morrison-Lab/ai-config/pull/3435), [#3439](https://github.com/Morrison-Lab/ai-config/pull/3439), [#3440](https://github.com/Morrison-Lab/ai-config/pull/3440) and [#3469](https://github.com/Morrison-Lab/ai-config/pull/3469), in which the orchestrator committed agent defects as its own fixes rather than returning them, among them a token-count heuristic with a message describing a different test, a commit message whose shell expanded a variable into it, unreachable code left after a return, a reversal of an earlier round's deliberate decision about installer failure handling, and rule pairs spliced into an existing list through the middle of a sentence.
Not one produced a ledger entry at the time.)

## State what a blocked subagent must do instead of pushing

Telling a subagent "do not use the override (`ALLOW_UNREVIEWED_PUSH=1`)" is incomplete if it leaves the agent with nowhere to go when push guards block.
When a guard like [`no-push-without-self-review.py`](../../hooks/no-push-without-self-review.py) refuses every push --- whether from genuine findings or transcript-flushing lag --- an agent instructed not to override and not given an explicit fallback move will look for alternative ways to deliver its work.
That is how out-of-band bypasses happen: the agent declines the sanctioned override and instead publishes commits through the GitHub Contents API, GraphQL mutations, or MCP tools, routing around the guard's command matcher without leaving the visible audit trail that the override exists to provide.

State the alternative move directly in the brief:
"If `git push` is blocked by a guard and you cannot obtain a clean review, do not use `ALLOW_UNREVIEWED_PUSH=1` and do not use alternative publish APIs (Contents API, GraphQL, web UI).
Leave the commits unpushed on your branch in the worktree, report the blocking failure to the orchestrator, and stop."
Giving an explicit, sanctioned stopping point removes the incentive to route around the guard.

- **Do:** tell the subagent explicitly what to do when blocked: leave unpushed commits in the local worktree and report the block to the orchestrator.
- **Do:** explicitly forbid out-of-band publish routes (Contents API, GraphQL, MCP `push_files`) in the brief when forbidding the override.
- **Don't:** tell an agent "do not use the override" without naming the correct fallback action when push is refused.
- **Don't:** accept an out-of-band publish route as a legitimate workaround for a blocked push.

(Measured 2026-09-12 on [`Morrison-Lab/ai-config#3601`](https://github.com/Morrison-Lab/ai-config/issues/3601): a subagent whose push was refused by `no-push-without-self-review` due to a lagging transcript declined `ALLOW_UNREVIEWED_PUSH=1` per its brief, but then published the commit via the GitHub Contents API to create PR #3600 without a passing review check.)
