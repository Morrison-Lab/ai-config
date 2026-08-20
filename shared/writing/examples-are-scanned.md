An illustrative example sits inside the document, so every mechanical check
that scans the document also scans the example.
When the document's subject *is* a mechanical check, the example is therefore
subject to the rule it is demonstrating -- and writing it the natural way
breaks that rule.

The trap is specific to a narrow case and worth naming because nothing else
fires on it.
Documenting a convention feels like describing a mechanism from outside it,
and the example is the part that feels most inert: it is quoted, often
backticked, and evidently not a real instance of the thing.
None of that is true of a scanner, which reads bytes.
A backtick is not an escape, a fenced block is not a sandbox, and a line that
says "for example" is a line like any other.

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

Before writing an example of a mechanically-checked pattern, ask what would
match it, then render the example so it cannot.
A placeholder that breaks the pattern's own grammar is usually the cheapest
route, and it stays readable: where a scanner requires a letter immediately
after some opening delimiter, an angle-bracketed placeholder in that position
matches nothing while still reading as an example.

Then say in the text why it is spelled that way.
Without the note the odd rendering looks like a typo, and the next editor
tidies it back into a live instance -- which is the same defect reintroduced
by someone being helpful.

Finally, run the detector over the file rather than re-reading it.
If no detector exists locally, that is the finding: build one, per
[`deterministic-tools`](../principles/deterministic-tools.md).

- **Do:** ask what a scanner would match before writing an example of what it
  matches.
- **Do:** render the example so it cannot match, and say in the prose why.
- **Do:** run the check over the finished file, since re-reading confirms the
  claim rather than the token.
- **Don't:** assume a code span, a fenced block, or a "for example" framing
  shields the text -- a line-oriented scanner sees none of those.
- **Don't:** let a later cleanup pass normalize the deliberate spelling back.

See [`examples-are-scanned.cases.md`](examples-are-scanned.cases.md).
