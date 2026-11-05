# Never launch a subagent on Fable without explicit, specific permission

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#never-launch-a-subagent-on-fable-without-explicit-specific-permission) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

An `Agent` call that omits `model` inherits the conductor's model.
In a Fable session that makes the cheapest thing to type the most expensive thing to run, and nothing reports the substitution: the call reads as "default", the transcript records `claude-fable-5-1`, and the account hits its usage limit.
Measured 2026-09-01: 10 launches in one session, 8 of them inherited Fable (six adversarial reviews, two sidecars), and only the two that set `model: sonnet` did not.

The rule is the user's, verbatim: never spawn a subagent on Fable without their explicit, specific permission.
"Specific" means for that launch, not a standing yes for the session.
`hooks/no-fable-subagent.py` is the mechanism: it denies an `Agent` launch that names Fable, or that omits `model` while the session's own model is Fable, and warns on a `Workflow` launch in a Fable session, whose `agent()` calls it cannot inspect.
`FABLE_SUBAGENT_OK=1` on the one approved command is how a grant is recorded.
Exporting it for a session is the violation wearing an environment variable.
The persona files under `.claude/agents/` and `.opencode/agents/` deliberately carry no `model:` (per `skills/agent-builder/SKILL.md`, the tier is pinned at the call site so one persona serves every tier), which is exactly why the call site has to name it: every `Agent()`, `Task`, or `Workflow` `agent()` invocation passes `model`, and the hook denies the Claude Code launch that does not.

- **Do:** pass `model` on every `Agent` call, `sonnet` or `haiku` for bounded or mechanical work, and ask before naming Fable.
- **Do:** set `FABLE_SUBAGENT_OK=1` only on the single command the user approved, after they approved it.
- **Don't:** omit `model` and let the launch inherit, which in a Fable session is a Fable launch nobody chose.
- **Don't:** treat a `daytb`, `away`, or `mwc` grant as covering the model tier; none of them does.

(Directive from the user, 2026-09-01: "have you been spawning subagents using fable?
don't ever do that without my explicit specific permission".
Tracked as ai-config#2927.)
