# Fixing your own mistakes is always top priority

When an error, mistake, bad merge, regression, broken test, or policy violation is identified in your work:
- **Remediating it is the absolute top priority** --- it supersedes all feature development, new issue pickup, and backlog progression.
- **Act immediately**: Revert the bad merge (see [revert-premature-merge.md](revert-premature-merge.md)), fix the regression, or resolve the failure before proceeding with any other work.
- **Next top priority: prevent recurrence mechanically**: Immediately after reverting or fixing the mistake, the unconditional next priority is creating or repairing a mechanical system (a harness hook, automated CI check, linter rule, or deterministic test) to ensure that mistake can never be made again (see [`no-mistake-without-a-hook.py`](../../hooks/no-mistake-without-a-hook.py), [`memories/preferences.md`](../../memories/preferences.md), and [no-empty-promises.md](no-empty-promises.md)).
- **Never make empty promises**: Do not substitute verbal assurances or apologies for mechanical gates and concrete fixes (see [no-empty-promises.md](no-empty-promises.md)).
- **Treat user profanity as an urgent defect alert**: Profanity or exasperation from the user signals an urgent failure to diagnose and remediate immediately without tone policing or canned apologies (see [user-profanity-signal.md](user-profanity-signal.md)).
