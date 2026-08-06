# Case records: efficient-pr-babysitting

Worked-example case records for the rules in
[`efficient-pr-babysitting.md`](efficient-pr-babysitting.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "A reviewer's 'considered but declined to raise' note is not an open item"

(Morrison-Lab/ai-config#1115, 2026-08-04: a 23-line CLAUDE.md addition earned **Ready for merge** on round one, with one optional cross-link the reviewer noted but declined to raise.
Acting on it drew a second clean verdict plus a fresh declined note -- a forward-pointing phrase the added cross-link introduced -- and acting on that drew a third: three review rounds for a change mergeable after the first.
Copilot's check went green with `get_reviews` empty on every head, including #1118's stable single-push head, so its silence was its no-findings behavior rather than anything the pushes caused -- an earlier version of this entry wrongly called that silence self-inflicted.)

## "Merge first, then commit the fix, then push once"

(ai-config#700: pushed the review fix, then merged `main` and pushed again about a minute later; the first review run was cancelled mid-flight and the round cost an extra cycle.)

## "Run the behind-check as its own step, before composing the push"

(Morrison-Lab/ai-config#957, 2026-07-31: the behind-check was folded into the
same command as the `git push`, so "3 behind" was read only once the push had
gone out.
The follow-up merge push then cancelled review run `30614715159`, in flight on
the commit it superseded.)
