# Accidentally triggering the bot by naming it

The bot's caller gates on `contains(github.event.comment.body, '@claude')` --- a
raw substring test over the body, with no notion of Markdown --- so writing the
literal string dispatches a full agent run whether or not you meant to summon
one.
Backticks, a code span, a code fence, a heading, and plainly descriptive
framing all leave the mention live.

[`claude-bot-workflows.md`](claude-bot-workflows.md) owns that mechanism and
the incident history: the canonical statement, the five numbered instances
under "@claude CI action", the `@v1`-versus-`@v2` pin analysis for gha#342's
markup stripper, and the fact that a fired run cannot be called back.
Read it for any of those.

This file exists for what that history could not fix by being written down
again.

## Sixth instance, `UCD-SERG/lab-manual#461`, 2026-08-17

A fallback self-review's own **heading** named the reviewer, in backticks,
while explaining that the reviewer had been quota-skipped.
Run `32071736901` was created three seconds later on `event: issue_comment`,
acknowledged itself at 21:33:48Z, and at 21:40:38Z posted the org spend-limit
message.
About seven minutes of runner and two bot comments of noise, for no review, on
a PR that already carried a quota-exhausted warning from twelve minutes
earlier.

That repo pins `Morrison-Lab/gha/.github/workflows/claude.yml@v1`, so the
stripper was never in play, exactly as the pin analysis in
[`claude-bot-workflows.md`](claude-bot-workflows.md) predicts.

## Every Do/Don't bullet scopes the warning to its own incident's surface, and the gate has no surfaces

The bullets in
[`claude-bot-workflows.md`](claude-bot-workflows.md)'s "A comment a workflow
*posts* is a mention-trigger surface" section each attach the backtick warning
to a narrower case than the mechanism has.
One says not to trust a code span "in a body your workflow posts"; another
covers "a quoted rule title".
A hand-written PR comment whose heading names the reviewer in ordinary
descriptive prose is neither, so a reader holding both bullets can write one
and violate the rule they just read.

That is not a wording slip.
Each bullet was written from the incident that produced it, so each names that
incident's surface rather than the gate's --- and `contains()` reads the raw
body of every comment, review, issue body, and issue title, whoever wrote it
and whatever markup surrounds the string.
Read those bullets as instances, and the substring gate itself as the rule.

## The recurrence is a placement problem rather than a missing rule

This is the more useful half, because the rule was not missing.

By the sixth instance the hazard was stated in five places: the numbered
instance sequence and the mention-trigger section in
[`claude-bot-workflows.md`](claude-bot-workflows.md),
[`github-actions.md`](github-actions.md)'s "it retriggers even in backticks"
bullet, and the trigger-phrase-leak bullets in
[`ardi`](../skills/ardi/SKILL.md) and [`ard`](../skills/ard/SKILL.md).
([`github-mcp-tools.md`](github-mcp-tools.md) cites the gate too, but as an
*analogy* for its own URL sanitizer rather than as a statement of this rule,
so it is not a sixth home.)
None of the five is auto-loaded: `memories/` is read on demand, and a skill
body loads only when that skill is invoked.

Meanwhile the one fragment that *instructs* a session to write the comment
that keeps carrying the mention ---
[`self-review-fallback`](../shared/workflow/self-review-fallback.md), whose
whole subject is a comment explaining which reviewer was unavailable --- is
auto-loaded via `CLAUDE.md`, and carried no warning and no pointer.
Its two nearest siblings did.
Derived against `86cc8233`, the last commit before this file:
`grep -c claude-bot-workflows` returned 5 for
`shared/workflow/review-verdict-pitfalls.md` and 1 for
`efficient-pr-babysitting.md`, against 0 for `self-review-fallback.md`, which
now carries the pointer.

That is the shape
[`read-canonical-doc-before-starting`](../shared/workflow/read-canonical-doc-before-starting.md)
names: a citation elsewhere is invisible to a session that never takes the
extra step of reading it.
So when a documented rule recurs anyway, the useful move is to put a pointer
where the *instruction* lives, rather than to restate the rule a sixth time
where it already sits.

- **Do:** read the backtick warning as covering every body you write --- a
  comment, a review, an issue title --- not only one a workflow emits or a
  rule title you quote.
- **Do:** name the workflow (`claude-review`) or write "the Claude reviewer"
  when a self-review has to say which reviewer was unavailable.
- **Do:** put the pointer where the instruction lives when a documented rule
  recurs anyway, and say which auto-loaded surface was missing it.
- **Don't:** treat a mention as inert because it is descriptive, backticked,
  or inside a heading --- the gate sees one string and no markup.
- **Don't:** read the narrower bullets in
  [`claude-bot-workflows.md`](claude-bot-workflows.md) as the boundary of the
  rule; they name the incidents that produced them.
- **Don't:** answer a recurrence by restating the rule in a file that already
  carries it --- that is the move which had already failed five times.
