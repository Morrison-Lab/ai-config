# File pre-existing violations of guidelines as issues

When you notice pre-existing violations of our guidelines during work in a repository,
file them as issues in the owning repository's tracker rather than letting them pass unrecorded.

A pre-existing violation is a defect, drift, or anti-pattern that already existed in the codebase,
workflows, or documentation before the active task began.
Finding such a violation does not license expanding the active task's scope to fix it in place,
and it does not license ignoring it either.
File it as an issue so it can be triaged, evaluated, and addressed as its own scoped change.

## Post-hoc DRW violations and tool retirement

A primary example of a pre-existing violation is a post-hoc Don't Reinvent the Wheel (DRW) violation.
When an internal tool, script, or helper was originally built,
no suitable external or upstream tool may have existed.
Over time, upstream packages and external ecosystems evolve,
and a new external tool may become available that replicates the internal tool's functionality.

If the new external tool matches or exceeds our internal tool's capabilities,
maintaining the internal tool becomes an unnecessary software maintenance burden.
Retiring the internal tool in favor of the upstream dependency decreases maintenance overhead,
avoids drift, and benefits from upstream maintenance and community fixes.

When you notice that an internal tool now replicates an external tool that matches or exceeds its functionality:
1. Do not delete or rewrite the internal tool inside an unrelated task.
2. File an issue in the owning repository detailing the external tool, how it matches or exceeds the internal tool's capabilities, and proposing the migration and retirement.
3. If the external tool has minor gaps, evaluate whether to contribute improvements upstream before retiring the internal tool (see [`upstream-issues`](upstream-issues.md)).

## General guideline violations

The same rule applies across all lab guidelines:
- **Math macros**: encountering equations in documentation or papers using bare LaTeX rather than shared semantic macros from `Morrison-Lab/macros` (see [`use-math-macros`](../../skills/use-math-macros/SKILL.md)).
- **Workflows & CI**: discovering outdated or copy-pasted CI workflows that should migrate to canonical `Morrison-Lab/gha` reusable workflows (see [`upgrade-to-gha`](upgrade-to-gha.md)).
- **Documentation & style**: noticing informal definitions, AI tells, unlinked forge references, or broken links outside the current task's scope.
- **Hooks & automation**: noticing missing automated guards or gaps where a deterministic hook should be installed.

When you notice any such pre-existing condition:
- If it is outside your active task's scope, file a dedicated issue per [`defer-issue`](../../skills/defer-issue/SKILL.md) and [`issue-first`](issue-first.md).
- Follow the issue-filing conventions in [`label-agent-filed-issues`](label-agent-filed-issues.md), including labels `ai-authored` and `model:<model-id>`.

## Summary rules

- **Do:** file every noticed pre-existing guideline violation as an issue in its owning repository's tracker.
- **Do:** identify post-hoc DRW violations where new external tools match or exceed internal tools, and propose retiring the internal tools to decrease maintenance burden.
- **Do:** search the issue tracker (including closed issues) before filing to ensure the issue is not already tracked.
- **Don't:** silently ignore pre-existing violations because they were not caused by the current turn.
- **Don't:** expand the active feature or bug fix branch to repair unrelated pre-existing violations in place.
