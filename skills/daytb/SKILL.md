---
name: daytb
description: "Decide current question yourself."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# daytb -- do as you think best

A one-shot grant of decision latitude.
The user has read the question and is handing it back rather than answering it:
pick the option you would have recommended, act on it, and say what you picked.

## When this fires

- The bare or slashed keyword `daytb`.
- The phrases it stands in for: "do as you think best", "do as you see fit",
  "do whatever you think is best", "your call", "you decide", "up to you",
  "I trust your judgment here".
- A reply that answers a posed decision by declining to choose --
  "either is fine", "whichever you prefer" -- which is the same grant in
  different words.

## What it grants

Latitude over **the decision in front of you**, and the ones that follow from
it while the same task runs.

It does not silence you.
The user is present, so the point is to stop *asking* rather than to stop
*reporting*: a decision made under `daytb` still gets stated, in the past
tense, with the one reason that settled it.
That is what keeps countermanding cheap.

## What it does not grant

- **Not the rest of the session.**
  `daytb` expires with the task it was given for.
  A later, unrelated decision is a fresh question.
  For a standing session-wide grant, that is [`away`](../away/SKILL.md).
- **Not destructive or irreversible actions.**
  A merge, a force-push, a deletion, anything outward-facing still needs its
  own explicit authorization.
  Merge authority specifically is [`mwc`](../mwc/SKILL.md)'s grant, not this
  one.
- **Not the safety rules.**
  Everything that required confirmation before still does.
- **Not a licence to guess when you genuinely cannot judge.**
  If proceeding either way would be unsafe, or the options differ on a fact
  only the user holds, say so plainly and ask the narrower question.
  That is rare -- treat it as the exception it is, not an escape hatch.

## Procedure

1. **Name the decision(s) the grant covers.**
   Usually the one just posed.
   If several were queued behind it, they are covered too unless answering
   one moots the rest.
2. **Choose the option you would have recommended.**
   Apply the same criteria you would have written into a
   `🧭 RECOMMENDATION` box.
   If you had already stated a recommendation, take it -- handing the
   decision back is agreement to it, not an invitation to reopen it.
3. **Act.**
4. **Report in the past tense**: what you chose, and the single reason that
   decided it.
   One or two sentences.
   Name anything you deliberately did *not* do, so a silent omission does
   not read as an oversight.
5. **Do not re-ask.**
   A follow-up question about the same decision spends the round trip the
   grant existed to save.

## Relationship to other skills

- **[`away`](../away/SKILL.md)** -- the session-scoped sibling, and the one
  most easily confused with this.
  `away` presumes the user is *gone*: it suppresses questions for the rest of
  the session, keeps a decision log, and is revoked by `back`.
  `daytb` presumes the user is *here* and simply declining to adjudicate one
  thing, so it carries no session state and needs no counterpart.
  Reading `daytb` as `away` would silently suspend clarifying questions long
  after the user expected them back.
- **[`back`](../back/SKILL.md)** -- revokes `away`.
  Nothing revokes `daytb`, because it expires on its own.
- **[`mwc`](../mwc/SKILL.md)** -- the grant that *does* extend to merging.
  `daytb` deliberately stops short of it.
- **[`prompt-me`](../prompt-me/SKILL.md) /
  [`prompt-me-all`](../prompt-me-all/SKILL.md)** -- the opposite direction:
  surface the questions rather than resolve them.
- **[`dmmhyh`](../dmmhyh/SKILL.md)** -- built on this skill's procedure for
  resolving the triggering item, but fires when the user is correcting a
  *pattern* of over-asking rather than just handing back one decision. It
  adds a standing in-session recalibration and a durable memory write that
  `daytb` alone doesn't do -- reach for `dmmhyh` instead of `daytb` when the
  user's complaint is about asking too much in general, not this one
  question.

## Anti-patterns

- Treating it as session-wide, and quietly dropping clarifying questions for
  unrelated later work -- that is `away`, and the user did not ask for it.
- Reading it as authorization to merge, delete, or publish.
- Choosing silently, so the user learns what was decided only by noticing the
  result later.
- Asking a confirming question anyway -- "I'll do X, unless you'd rather Y?"
  is the grant declined, not honoured.
- Reopening a recommendation you had already made, instead of simply taking
  it.
