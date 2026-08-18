# heal-skill

Close the feedback loop on skill quality: when a skill misbehaves in a real session, repair it *now*, while the failure is in front of you. This is the retrospective complement to *authoring* a skill and to `ums` (which records learnings) — it fixes a skill that already shipped and then misfired.

## When this fires

- A skill triggered on the wrong input, or failed to trigger on the right one.
- A skill fired correctly but its body led the work astray (bad steps, stale instructions, wrong assumptions).
- The user says “that skill confused you”, “heal that skill”, “the description is too greedy”, “that shouldn’t have fired”, or `/heal-skill`.

## Procedure

### 1. Identify the culprit

Determine which skill misfired. If it’s not named, infer it from what just happened — the slash command invoked, the description that matched, or the behavior that went wrong. Confirm the skill name with the user if ambiguous. Read its `skills/<name>/SKILL.md` in full before changing anything.

### 2. Diagnose the root cause

Classify the failure — the fix differs by type:

- **False trigger** (fired when it shouldn’t): the `description` is too broad, or its trigger phrases overlap a more general request. Fix: tighten the description, narrow the trigger phrases, add an explicit “don’t fire when…” note.
- **Missed trigger** (didn’t fire when it should): the `description` lacks the user’s phrasing. Fix: add the missing trigger phrases / synonyms.
- **Ambiguous overlap** (two skills compete for the same request): fix the boundary in *both* descriptions so each owns its lane; cross-link them.
- **Bad body** (fired right, acted wrong): a step is wrong, stale, or underspecified. Fix the offending step; verify any file/flag/command it names still exists.

State the diagnosis in one or two sentences before proposing the fix.

### 3. Propose a minimal fix

Draft the smallest change that addresses the root cause — usually a few lines of the frontmatter `description` or one body step. Show the user the exact diff and the reasoning. Don’t rewrite the whole skill; don’t add unrelated polish.

### 4. Apply with approval, then validate

On approval, edit the SKILL.md. Then sanity-check it still parses and is internally consistent: run `scripts/validate-skills.py` if the repo has it, and re-read the trigger against the failure that prompted the heal. If this repo ships skills via branch + PR, follow that flow rather than committing to main.

### 5. Record the lesson

If the misfire reflects a pattern worth remembering (a recurring over-trigger, a phrasing the user favors), hand off to `ums` to persist it, so the next skill is authored without the same flaw.

## Relationship to other skills

- **`skill-builder`** — the authoring counterpart; it writes a skill, this skill repairs one after it ships and misfires.
- **`agent-builder`** — the authoring counterpart for a `.claude/agents/*.md` subagent. If a heavy skill’s fan-out step misbehaves because the *spawned agent’s* prompt or tool-scoping is wrong (not the calling skill’s body), fix the agent file via `agent-builder`’s conventions instead of editing the skill.
- **`link-skills`** — the proactive, whole-corpus cross-link audit; `heal-skill` is the single-skill reactive repair, and fixing an ambiguous overlap here means cross-linking the two skills (exactly what `link-skills` sweeps for).
- **`consolidate-skills`** — when two skills have real bodies for the same workflow, that’s a merge, not a heal; hand it there.
- **`ums` / `record-learnings`** — hand off to persist a recurring misfire as a remembered lesson, so the next skill is authored without the same flaw.

## What NOT to do

- Don’t delete or disable a skill to “fix” a single misfire — repair the trigger or body instead. If a skill is genuinely redundant with another (two real bodies for one workflow), that’s a merge, not a heal — hand it to `consolidate-skills`.
- Don’t broaden a description so far that it starts stealing other skills’ triggers; healing a missed-trigger shouldn’t create a false-trigger.
- Don’t make unrelated edits in the same pass — keep the heal minimal and reviewable.
- Don’t change behavior the user was happy with; only touch what misfired.

------------------------------------------------------------------------

*The idea for this skill (a retrospective “repair the skill that just confused you” loop) is credited in [CREDITS.md](../../CREDITS.md).*

Back to top
