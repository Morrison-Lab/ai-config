Drop any review finding you are about to post if it cannot quote the passage it is about.

## Why this is worth having next to the reviewer-verification rules

[`address-every-comment`](address-every-comment.md) already establishes a family of checks for findings you **receive**: verify a reviewer's premise, their suggested literal, their cited source, before acting on any of them.
This is the same discipline applied in the other direction, to findings **you** produce, before you post them.

The adversarial-verify pattern (a `Workflow` spawning skeptics prompted to refute a finding, keeping it on a majority vote) is a **judgment** filter -- it costs N model calls per finding and returns a probability.
"Can this finding quote the passage it is about?" is a **mechanical** filter -- it costs one string search, has no false negatives worth worrying about, and eliminates the single most common bad finding: one about code or prose that is not there.
Per [`algorithmatize-checks`](algorithmatize-checks.md), the cheap mechanical check should run first, and the expensive judgment filter should only see what survives it.

## The carve-out

A finding about something **missing** -- an absent test, an uncited claim, a gap in coverage -- has no passage to quote by construction.
The rule needs an explicit exception for absence findings, which instead should name the **location** where the missing thing belongs (the function that lacks a test, the section that never cites its source), so the finding stays checkable even without a quotable passage.

## Companion norm

Attack the argument or the data, never the authors.
Reputation, journal status, citation counts, and prior review carry no evidentiary weight in whether a finding is correct.
This is what keeps a critical reviewer usable rather than merely harsh.

## Where this applies

Wherever this corpus already produces or verifies review-shaped findings: `ard`/`ardi`'s self-review step, `code-review`, the prose-review skills (`use-preferred-style`, `find-ai-tells`, `fact-check-prose`), `grade-work`, and any `Workflow` adversarial-verify pattern -- as the pre-filter ahead of the expensive vote, not a replacement for it.

- **Do:** quote the exact passage a finding is about before posting it, or name the passage's location when the finding is about an absence.
- **Do:** run this mechanical check before spending model calls on adversarial verification of the same finding.
- **Do:** attack the argument or the data in a finding, never the author's standing.
- **Don't:** post a finding about code or prose that does not exist in the diff or file under review.
- **Don't:** require a quoted passage for an absence finding -- name the location it belongs at instead.

(Pattern observed in `scdenney/open-science-skills`'s `paper-review-lite`, CC BY-NC 4.0 -- pattern only, nothing copied;
ai-config#881.)
