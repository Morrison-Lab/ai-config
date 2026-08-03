# brainstorm — pre-implementation Socratic planning

Run a short, structured clarifying-question loop with the user **before** any code is written or issue is filed, then capture the agreed approach in a plan file. This runs *before* `st`: `st` assumes the decision to act and the rough shape of the work are already settled, and jumps straight to filing a tracking issue. `brainstorm` is for when the task is vague enough that filing an issue now would lock in the wrong scope.

## When this fires

- “brainstorm”, “brainstorm this”, “let’s brainstorm”, “think this through with me first”, “plan this out before we start”.
- A request is underspecified — multiple reasonable interpretations exist, a design choice has real tradeoffs, or “done” can’t yet be stated in one sentence (the same bar `st` uses to decide an issue isn’t ready to file).
- Not for well-scoped work: a bug fix with a clear repro, a one-line change, or anything where `st`’s “restate the task and ‘done’ criteria” step already produces an unambiguous answer — skip straight to `st` there.

## Procedure

1.  **State the request as you understand it**, one or two sentences, and name the specific thing you’re unsure about — don’t ask a generic “any requirements?” question.
2.  **Ask 2-4 targeted clarifying questions per round**, focused on the decision that most changes the shape of the work, not everything at once. Use `AskUserQuestion` for genuine either/or choices; plain questions for open-ended ones.
3.  **Repeat** for as many rounds as it takes to reach a shape you could restate as an unambiguous “done” criterion — usually 1-3 rounds. Stop asking once further questions would be bikeshedding rather than resolving a real fork in the approach.
4.  **Write the plan file.** Once the approach is agreed, write it to `plans/<slug>.md` in the target repo (create the directory if it doesn’t exist yet), covering: the problem/context, the chosen approach (not every alternative considered), the specific files/areas it touches, and how “done” will be verified. Keep it scannable — a few paragraphs plus a short list of concrete steps, not an exhaustive spec.
5.  **Hand off to `st`** (or `gi` if an issue already exists): the plan file becomes the input `st` restates into an issue body, instead of writing the issue from scratch. Reference the plan file’s path in the issue.

## Relationship to other skills

- **`st`** — `st` is for work whose shape is already settled; it restates the task in 1-2 sentences and jumps straight to filing an issue. This skill runs *before* that: when the shape isn’t settled yet, resolve it here first, then hand the resulting plan file to `st` to turn into an issue.
- **`gi`** — if an issue already exists but its scope is unclear or disputed, use this skill to resolve the ambiguity before implementing, then resume `gi`’s normal flow.
- **`split-concerns`** — if brainstorming reveals the request is really several independent concerns, split them into separate plan files/issues rather than one combined plan.

## Anti-patterns

- ❌ Asking one giant list of questions instead of focused rounds — floods the user and buries the one question that actually matters.
- ❌ Continuing to ask questions after the shape is already clear, just to seem thorough — that’s stalling, not brainstorming.
- ❌ Writing a plan file so long and exhaustive it duplicates what the eventual issue/PR description will say.
- ❌ Skipping straight to `st`/code on a genuinely ambiguous request because asking felt like friction — the point of this skill is a little friction now instead of building the wrong thing.
- ❌ Treating a well-scoped, unambiguous task as needing a brainstorm round — that’s added latency for no benefit; use `st` directly.

Back to top
