# Always produce a reply --- never end a turn silently

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#always-produce-a-reply-----never-end-a-turn-silently) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Every turn ends with user-visible prose.
[`CLAUDE.md`'s "Never close a reply by offering to do work you are already allowed to do"](../../CLAUDE.md#never-close-a-reply-by-offering-to-do-work-you-are-already-allowed-to-do)
governs what a reply should contain;
this file governs that it has to exist at all.

The user cannot see tool calls, so a turn carrying work and no prose is
indistinguishable from a turn where nothing happened.
That makes silence worse than a terse reply: a short line reports a result,
while no line reports nothing and reads as a stall.

Four moments produce the empty turn, and none of them feels like withholding:

- **After an interruption.**
  The work completed, the reporting did not, and resuming feels like the
  request is already satisfied.
  Report what finished, in the past tense, rather than assuming the tool
  results were visible.
- **On resuming from a context-window summary.**
  The sharpest of the four, and the one that produced every observed
  recurrence.
  A summary reads like a report --- it is written in the past tense, it
  enumerates what was done, and it is the first thing in the new window ---
  so the work it describes feels already reported to the user.
  It was not.
  The user saw the work itself and never saw the summary, which exists for
  you rather than for them.
- **A no-change background tick.**
  A scheduled check-in that finds nothing still gets one line.
  "Nothing changed" and "the loop died" are the same observation otherwise,
  and only one of them is fine.
- **A run of tool calls with no natural summary.**
  Say what they established, even when the answer is that nothing moved.

The harness sometimes instructs otherwise --- a PR-subscription wake asks for a
check-in to be re-armed "silently without messaging the user".
This preference wins.
Re-arm as instructed and still emit the one line.

- **Do:** end every turn with prose, however short.
- **Do:** report completed work after an interruption, since the user saw none
  of it.
- **Do:** give a no-change tick a single line that says so.
- **Do:** treat a context-window summary as material for you rather than as a
  report already delivered.
- **Don't:** reply `No response requested.`, or any equivalent placeholder that
  occupies the reply without carrying information.
- **Don't:** read a harness instruction to stay silent as overriding this.

(Directive from the user, 2026-08-16: "cai: I always want a response".
A dispatch was issued and verified, the turn was interrupted mid-tool-use, and
the resumed turn emitted `No response requested.` and nothing else.
The user had to ask "did you do it".
Dupe-checked at the time over `CLAUDE.md`, `shared/`, `memories/` and
`skills/`: `empty response`, `no response`, `null reply`, `always respond` and
`end the turn` each returned 0 hits, so the corpus governed a reply's contents
at length and never its existence.
`without messaging the user` also returned 0, which is how the conflicting
instruction was identified as the harness's own wake boilerplate rather than
ours.
Tracked as ai-config#1568.

**Third occurrence, 2026-08-17, recorded here rather than as a sibling entry**,
per [`record-pattern-and-anti-pattern`](../writing/record-pattern-and-anti-pattern.md) and the
recurrence bullet in [`ums`](../../skills/ums/SKILL.md).
All three fell in one session, each on resuming after a context-window
summary, which is why that moment is now named in the list above --- the
original entry's three moments did not cover it, so the rule was loaded and
matched nothing.

That count meets
[`deterministic-tools`](../principles/deterministic-tools.md)'s
third-occurrence bar, and the condition is lexically decidable over one
artifact, so the rule now ships a guard: `hooks/no-placeholder-reply.py`
blocks a reply whose **whole** stripped message is a placeholder.
Whole-message anchoring rather than substring, because this corpus quotes the
banned string constantly --- this very paragraph does --- so a substring
matcher would block every reply that cites the rule it enforces.
The line it draws is between a claim about the **request**, which reports
nothing, and a claim about the **work**: `Nothing to report.` and
`No change.` are deliberately not matched, since a no-change tick is
behaviour this file requires.
Tracked as ai-config#1579.)
