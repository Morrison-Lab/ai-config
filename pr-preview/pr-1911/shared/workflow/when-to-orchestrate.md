When a heavy skill runs, decide whether to fan the work out to a **Workflow**
(multi-agent orchestration) instead of handling it inline. This is the shared
decision rule the parallelizable skills consult.

## The opt-in gate comes first

The `Workflow` tool is opt-in-gated and a skill cannot override that for a bare
prompt. But *an invoked skill whose instructions say to use a workflow* is itself
a sanctioned opt-in. So this rule never forces a workflow --- it only decides
whether to **launch** one or **propose** one:

- **Launch directly** when an opt-in signal is already present: the user wrote
  `ultracode`, set a `+Nk` token budget, said "use a workflow" / "fan out", or
  ultracode is on for the session.
- **Otherwise propose with a one-line cost estimate** and wait --- e.g. "This is
  workflow-shaped: ~N agents, ~Xk tokens. Run it as a workflow, or inline?" Never
  auto-spend on a large fan-out without a signal.

## When the task is workflow-shaped

Orchestrate only when **all three** hold:

1. **Decomposable** --- the work splits into at least ~4 independent targets
   (files, sources, review dimensions, gradable items) whose handling does not
   depend on each other's results.
2. **Verification-bearing** --- the targets benefit from adversarial
   double-checking (review, audit, research, grading), not just a mechanical edit
   applied uniformly.
3. **Scale earns it** --- serial handling would be slow or lossy: a broad sweep,
   a whole-corpus pass, or an ask that says "thorough", "comprehensive", "audit",
   or "every".

## The shared-runner exception

Fanning out work that **pushes commits and triggers CI / a review bot per target**
(driving several open PRs, opening several issue PRs at once) does **not** clear
this bar, even at ~4+ targets: the targets are decomposable but they collide on
shared review runners and make per-PR status illegible. That is why `ardia`
drives PRs one at a time and `gip` caps concurrency. For those, orchestrate only
the part that touches no shared forge state, and keep the push --- re-review ---
merge actions serial or capped.

That part is wider than a survey.
It covers reading each PR's latest review and
CI logs, tracing findings, running local checks, and **preparing an uncommitted
patch** in an isolated worktree --- none of which claims, comments, commits,
pushes, or requests review, so none of it contends for a review runner.
[`ardia`](../../skills/ardia/SKILL.md)'s step 2 is the worked form, including
the artifact handoff and the staleness re-check a prepared patch needs.
The line is **mutation of shared state**, not read-only-ness in the literal
sense: a worker writing a patch file to its own worktree is on the safe side of
it.

## Stay inline when

- There is a single target, or fewer than ~4.
- The change is trivial and mechanical (a rename, a one-line fix, a known edit).
- The answer is one lookup, or the user asked a conversational question.
- Flattening the work into a workflow would be more convoluted than just doing
  it.

**"Inline" means not a `Workflow`, not necessarily serial.**
Falling below this bar rules out the heavy fan-out and its opt-in gate; it says
nothing about whether a single `Agent` call should handle one piece of the work
alongside you.
That lighter delegation is separately pre-authorized, and `CLAUDE.md`'s "Use
subagents when helpful --- and delegate rather than queue" requires it for
anything that would otherwise be announced as queued or next up.
So read a below-the-bar verdict as "do it here, delegating whatever does not
block the edit in front of you", rather than as a reason to work a parallel
track serially.

## The third primitive: agent teams

This fragment governs the `Workflow` tool, and the section above distinguishes
it from a single `Agent` call.
There is a third parallelism primitive it does not cover: an **agent team** ---
several separate Claude Code sessions that message each other through a shared
task list, rather than only reporting back.
It is the right choice when the workers must *communicate with each other* or a
human wants to steer individual workers mid-run --- neither of which a
`Workflow` sweep can do.
But a team is experimental, off by default, and spawned by the user
interactively, so a session can only *recommend* one, never form one.
See [`agent-teams`](agent-teams.md) for the three-way decision and the
never-assume-it-is-available caveat.

## What "propose" looks like in practice

Estimate the fan-out from the target count: roughly one agent per target for a
single-pass sweep, two to three per target when each target also gets an
adversarial verify pass. State the agent count and a rough token figure, name the
inline alternative, and let the user choose. If they decline, do the work inline
--- the proposal is a recommendation, not a gate.

Scale the harness to the ask: a quick "find any bugs" wants a few finders and a
single verify; "thoroughly audit this" wants a larger finder pool, a 3--5 vote
adversarial pass, and a synthesis stage.

## Route each agent's model/effort, don't default every call to the same tier

`agent()`'s own guidance says to omit `model`/`effort` unless "highly
confident" a different tier fits. Use [`select-model`](../../skills/select-model/SKILL.md)'s
decision tree to make that call concretely, instead of defaulting to inherit
out of caution on every single call:

- **Mechanical, bounded work** --- a single-file edit, a doc/changelog sync, a
  formatting sweep, a read-only survey/grep pass, the same verification check
  repeated across many targets --- clears the confidence bar for a cheaper
  tier (Haiku, sometimes Fable) and/or `effort: 'low'`. This is most of a
  Survey phase and most Verify passes in a `pipeline()`.
- **Judgment-heavy work** --- architecture, a subtle-bug hunt, security
  review, synthesizing several agents' findings into a design --- inherit the
  session model (the default) or set `effort: 'high'`/`'xhigh'` explicitly.
  This is almost always a Design/Synthesize phase, not a Survey/Verify one.

Don't build a per-task-type routing matrix beyond this two-bucket split ---
`select-model`'s own decision tree already exists for the finer-grained calls;
point at it rather than re-deriving new criteria inline. And don't trust a
single synthesis-stage agent's output at face value just because it validated
against its schema --- a schema only checks shape, not substance; skim a
judgment-heavy agent's actual result before building on it, the same way a
Verify pass would.
