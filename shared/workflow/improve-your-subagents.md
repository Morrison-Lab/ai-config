Part of an orchestrator's job is to find ways for its subagents to improve over time.
Correcting each output as it arrives keeps the work moving and leaves the mistake rate exactly where it was, because a dispatched agent's mistakes are a function of three things the orchestrator owns: the brief it was given, the memory it could read, and the loop that feeds findings back to it.

The measured shape (2026-09-02, thirteen `agy` dispatches on one Godot repo): every one of eight extra fix rounds was an omission the brief had not named, and the one mistake the agent repeated after recording it had been recorded in a PR worktree its next dispatch never read.
The agent was not the weak link; the briefing was.

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
