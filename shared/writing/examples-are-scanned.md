An illustrative example sits inside the document, so a mechanical check that
scans the document may scan the example too.
When the document's subject *is* a mechanical check, the example can therefore
be subject to the rule it is demonstrating -- and writing it the natural way
breaks that rule.

Whether it does turns on one property of the checker, which is worth
establishing rather than assuming in either direction.
A **line-oriented** scanner -- a `grep`, a `readLines()` loop, a substring
test -- sees a code span as characters like any other, so backticks and
fenced blocks shield nothing.
A **structure-aware** one strips code regions first and never sees the
example at all.
This corpus contains both kinds, so neither is the safe default here.

The trap is specific to a narrow case and worth naming because nothing else
fires on it.
Documenting a convention feels like describing a mechanism from outside it,
and the example is the part that feels most inert: it is quoted, often
backticked, and evidently not a real instance of the thing.
None of that is true of a line-oriented scanner, which reads bytes.
To one of those a backtick is not an escape, a fenced block is not a sandbox,
and a line that says "for example" is a line like any other.

Two properties make it worse than an ordinary slip.

**The failure implicates the passage that explains it.**
A section documenting a rule, which trips that rule, will be read by whoever
next hits the rule -- so the one artifact meant to prevent the mistake is the
artifact demonstrating it.

**Self-review is structurally poor at catching it.**
Re-reading the passage confirms the *claim*, which is correct; the defect is
in a token the prose is discussing rather than asserting.
Nothing about reading it again changes what the scanner sees.
So the remedy is not more care but running the detector, per
[`algorithmatize-checks`](../workflow/algorithmatize-checks.md).

## What to do

Start by reading the checker, since that decides which of the two remedies
below applies.
The question is narrow -- does it strip code regions before matching? -- and
one look at the source settles it.

**When you own the checker, teach it about code regions.**
This is the better fix where it is available, because it removes the hazard
for every example anyone writes later rather than for the one in front of you.
This repo has done it twice: `scripts/lib/fences.py` is a shared
CommonMark-compliant fence and code-span stripper, used by `check-links.py`
and others precisely so that link-shaped examples inside fences are not
mistaken for real links.
`hooks/no-placeholder-reply.py` reaches the same end differently, anchoring on
the whole message rather than a substring, so that a reply quoting the rule it
enforces is not blocked by it.

**When you do not own the checker, render the example so it cannot match.**
A placeholder that breaks the pattern's own grammar is usually the cheapest
route, and it stays readable: where a scanner requires a letter immediately
after some opening delimiter, an angle-bracketed placeholder in that position
matches nothing while still reading as an example.

Then say in the text why it is spelled that way.
Without the note the odd rendering looks like a typo, and the next editor
tidies it back into a live instance -- which is the same defect reintroduced
by someone being helpful.

The two are not alternatives to choose between on taste, per
[`avoid-false-dichotomies`](../workflow/avoid-false-dichotomies.md).
Ownership of the checker decides which is even available, and where you own it
and the example is already written, both are worth doing.

Finally, run the detector over the file rather than re-reading it.
If no detector exists locally and the same check has come up before, that is
the finding: build one, per
[`deterministic-tools`](../principles/deterministic-tools.md), whose own
trigger is recurrence rather than a first occurrence.

- **Do:** read the checker first, and establish whether it strips code regions
  before deciding anything else.
- **Do:** make the checker code-aware when you own it, since that fixes every
  future example rather than this one.
- **Do:** render the example so it cannot match when you do not, and say in the
  prose why.
- **Do:** run the check over the finished file, since re-reading confirms the
  claim rather than the token.
- **Don't:** assume a code span or a fenced block shields the text -- it does
  for a structure-aware checker and not for a line-oriented one, and which you
  face is a fact to look up.
- **Don't:** assume the reverse either, and deform an example a fence-aware
  checker was never going to see.
- **Don't:** let a later cleanup pass normalize the deliberate spelling back.

See [`examples-are-scanned.cases.md`](examples-are-scanned.cases.md).
