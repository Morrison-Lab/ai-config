Every algorithmic check has two companions: an instruction to the writer that prevents the defect, and an instruction to the reviewer agent that looks for it.
Ezra, 2026-11-09, on a check that flags content removed without landing anywhere else (gha#1791): "every algorithmic check should also have corresponding writer and reviewer instructions, to create defense in depth".

This is [defense in depth](https://morrison-lab.github.io/psc/chapters/coding-practices.html#sec-defense-in-depth) applied to the lab's own checks.
Each guarantee gets layers that fail for different reasons, and each layer works without the others:

- **The check** decides what a computation can decide, and fails the PR.
- **The writer instruction** names the rule where the author reads it before writing, so the defect is not introduced.
- **The reviewer instruction** names the rule in the reviewer agent's checklist, so a reviewer looks for it when the check is absent, skipped, misconfigured or blind to the case.

A check alone fails silently when it is not run, when its detector matches nothing, or when the defect has a shape it cannot see.
An instruction alone is context a session reads past ([ai-config#4741](https://github.com/Morrison-Lab/ai-config/issues/4741)).
Together a defect has to slip through three unrelated layers.

## What a new check ships with

A PR that adds an algorithmic check (a `gha` workflow or script, a hook, a `scripts/check-*.py`) also adds or updates:

- a writer instruction in the fragment that owns the rule, stated as a Do/Don't pair in the example format that document already uses (an ai-config fragment uses bold **Do:** and **Don't:** bullets, while a psw chapter uses a `> ❌` and `> ✅` blockquote pair, and [psw#553](https://github.com/Morrison-Lab/psw/pull/553) was flagged for the first inside the second);
- a reviewer instruction in the checklist of [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md), or of the reviewer agent that owns the domain (`prose-fact-checker`, `hallucination-detector` and the others in `.claude/agents/`);
- a link from each layer to the other two, so a reader who finds one finds all three.

The PR description names the three layers.

## Writing the layers so they are independent

- The reviewer instruction describes the defect, not the check's name, so it still applies when the check is off.
  "Content removed from a page appears elsewhere or the diff says why" is a defect.
  "Pass the content-preservation check" is not.
- The reviewer does not run the check's script and report its output as its own finding.
  It reads the diff, because a reviewer that repeats the check's verdict is the same layer twice.
- The writer instruction states the rule's reason, so an author can apply it to a case the check's pattern does not match.

## Existing checks

A check that lacks a writer or reviewer layer gets one issue naming the check and the missing layer, labeled `ai-authored`.
Do not fix them in one sweep.

- **Do:** ship the writer and reviewer instruction in the PR that adds the check.
- **Do:** write the reviewer instruction against the defect.
- **Don't:** treat a passing check as the reviewer's answer.
- **Don't:** add the instruction to one agent and call the check covered.

## The check for this rule

`scripts/check-check-has-instructions.py` ([ai-config#5174](https://github.com/Morrison-Lab/ai-config/issues/5174)) fails a PR that adds a `scripts/check-*.py` script or a hook without also changing a writer instruction (a `.md` under `shared/`, `AGENTS.md`, `CLAUDE.md` or a `SKILL.md`) and a reviewer instruction (`.claude/agents/*.md`).
A PR that cannot supply a layer puts `check-instructions: exempt - <reason>` in its body.
It sees only added files, so a check added as a workflow in another repository, or a layer that is present but vacuous, still needs the reviewer's checklist item.
