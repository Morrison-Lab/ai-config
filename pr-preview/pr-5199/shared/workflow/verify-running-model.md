# Verify the model and effort a session is running; never infer them

A session cannot report its own model or effort by introspection, so a claim such as "I am on Opus at high effort" is a guess until an instrument reads it.
[`scripts/check-session-runtime.py`](../../scripts/check-session-runtime.py) is that instrument ([ai-config#879](https://github.com/Morrison-Lab/ai-config/issues/879)).
It reads the session's own transcript and prints `runtime OK: <model> at <effort>` only when every step held.

## When to gate on it

Run it before work that is only valid on a particular tier, and say which tier you require:

- grading or any other judgment a lower tier would do worse, such as `grade-work`
- an adversarial review whose point is a stronger model than the author's
- recording a model or effort in a note, an issue or a PR body

```
python3 scripts/check-session-runtime.py --expect-model claude-opus-5 --expect-effort high,xhigh
```

There is no built-in default tier, because the right one depends on the task.
`select-model` and `assess-model-fit` choose the tier, and this script confirms it.

## Reading the exit code

- **0:** the running model and effort are in the accepted lists.
- **1:** they are known and are not accepted.
  Switch with `/model`, or say that the work runs below the required tier.
- **2:** the runtime could not be established.
  Do not proceed as if it had matched.
  Causes: no session id, zero or several transcripts, no model or effort in the latest record, or a reroute.

## Limits

- It decides from the latest non-subagent assistant record, so it sees a mid-session `/model` switch and ignores subagents, which run other models on purpose.
- `requestedModel` is in some transcripts and not others (measured 2026-11-05).
  Without it the reroute check cannot fire and passes.
- It checks the session that runs it, not a subagent's model.
  Set a subagent's `model` explicitly instead ([`no-fable-subagents`](no-fable-subagents.md)).
