Part of an orchestrator's job is to find ways for its subagents to improve over time.
Correcting each output as it arrives keeps the work moving and leaves the mistake rate exactly where it was, because a dispatched agent's mistakes are a function of three things the orchestrator owns: the brief it was given, the memory it could read, and the loop that feeds findings back to it.

The measured shape (2026-09-02, thirteen `agy` dispatches on one Godot repo): every one of eight extra fix rounds was an omission the brief had not named, and the one mistake the agent repeated after recording it had been recorded in a PR worktree its next dispatch never read.
The agent was not the weak link; the briefing was.

## What to change, in order of payoff

**Keep a per-agent mistake ledger and prepend it to every brief.**
A numbered list of standing rules, each one a past mistake stated as the action that avoids it, kept in the orchestrator's own memory rather than in any branch, so a learning written during one PR reaches the next dispatch on another.
Append to it after every fix round.

**Turn each fix round into a change to the loop.**
After a checker or reviewer catches a defect in the agent's output, ask what would have prevented the class: a preamble line, a required self-test, a checker the agent must run and paste, a smaller task ([`learn-from-review-findings`](learn-from-review-findings.md) and [`algorithmatize-checks`](algorithmatize-checks.md) govern the same move for your own work).
Make that change in the same session.
The re-dispatch itself still goes to the same agent, carrying the finding and its own UMS step, per the user's directive tracked as [ai-config#3073](https://github.com/Morrison-Lab/ai-config/issues/3073).
The orchestrator then copies that entry into its own ledger, because a learning written inside a PR worktree is one the next dispatch never reads.

**Give instruments, not adjectives.**
"Be careful with regexes" changes nothing.
"Enumerate the input forms, run each through an `awk 'BEGIN{...}'` block, and paste the output" is checkable, and the paste is what lets the orchestrator verify without re-deriving.

**Measure the agent.**
Rounds to clean per PR, and mistakes per dispatch, by class.
Compare briefs and models against those numbers rather than against an impression of the last run.
A model that "does a good job with caveats" is a number that has not been written down.

**Try structural variations.**
A two-pass dispatch that writes, then reviews its own diff against the ledger before returning.
A cheap implementer paired with a different-vendor reviewer, per [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md)'s cross-model review pattern, whose findings become ledger lines.
A task split small enough that the agent's completeness weakness cannot reach it.

**Promote what works.**
A ledger line that has held for several sessions belongs in the agent's delegation skill as a preamble line, and a mistake that is lexically decidable belongs in a hook, so every orchestrator inherits the improvement rather than re-learning it.

- **Do:** keep a mistake ledger per agent in orchestrator-owned memory and prepend it to every brief.
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
