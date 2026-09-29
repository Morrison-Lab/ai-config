# Status requests do not make issues report-only

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#status-requests-do-not-make-issues-report-only) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Treat a request for status as a request to inspect live state and finish every
safe, in-scope, concrete action that inspection reveals. A report is the recap
after the work, not a substitute for it. When an issue cannot be fixed
directly, carry it forward with an actual next action. **Every issue noticed,
however small or outside the current task's scope, must at minimum be filed in
the owning GitHub, GitLab, or equivalent tracker.** File it before reporting
it; use the correct private tracker and redact sensitive details when needed.

- **Do:** fix an actionable CI defect, review finding, or configuration gap
  before reporting it as status; revalidate and continue the sweep.
- **Do:** turn an issue outside current authority into a filed/routed blocker,
  not an unowned observation.
- **Do:** file every noticed issue in its owning tracker, even when it is
  trivial, already fixed locally, or outside the active task.
- **Don't:** interpret "status" as report-only after discovering a concrete,
  safe, in-scope repair.
- **Don't:** end with "this failed" or "this needs a fix" when the fix is
  available to perform in the same turn.
- **Don't:** leave a noticed issue as chat prose because it seems too small or
  too far outside the current scope to track.
