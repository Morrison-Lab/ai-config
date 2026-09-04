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

## A negation is not an escape either

Everything above is about the *example* ---
a quoted instance of the pattern, which a line-oriented scanner reads as bytes.
A negated sentence is a second way to write the pattern without meaning it,
and it is easier to miss because nothing about it looks like an example.
A sentence beginning `no issue is worth filing` contains the assertion a declarative-claim detector exists to catch,
and the word that reverses its meaning is a word the detector cannot read.

The two are not the same case, and the difference decides the remedy.
Rendering is a property of the *text*, so a structure-aware checker strips it once and covers every example anyone writes later.
Negation is a property of the *meaning*, so nothing a code-region stripper does reaches it:
it has to be modelled explicitly, cue by cue, and each cue is a fresh guess about how the sentence will be phrased.
That is why the parent section's first remedy applies to one and not the other.
`hooks/no-unfiled-finding.py` is worth reading here as the worked instance:
it strips fenced blocks, blockquote lines, and inline code spans before matching,
so backticking the phrase above really does shield it ---
and no rendering choice whatever changes what it makes of the bare negated sentence.
GitHub's own parser is the opposite corner,
closing an issue on `KEYWORD #N` inside a sentence written to say the keyword is not being used ---
see [`issue-first`](../workflow/issue-first.md)'s
"A closing keyword plus #N closes #N even when the sentence negates it".

**Which direction it fails in decides how much fixing it is worth, and "safe direction" is not the same as "cheap".**
GitHub's parser fails destructively and invisibly:
it closes somebody's live work, and the sentence's author gets no signal at all.
`no-unfiled-finding.py` fails in the safe direction and still `block`s the reply,
so the cost is a stalled turn plus a dupe-check the session should arguably have run anyway ---
recoverable, unlike a closed issue, and not free either.
Rank the fix from both axes rather than from the direction alone:
a blocking guard that fires on a negation is worth fixing sooner than a warning one,
even though both fail safely.
Settle which you have by reading the value the hook emits,
since a guard's severity is the one property nothing about its subject matter implies.

- **Do:** read the checker for whether it strips code regions, and treat that answer as settling rendering only.
- **Do:** check whether the sentence you are writing contains the literal pattern a detector matches, independently of whether the sentence asserts it.
- **Do:** classify a negation-blind detector by its failure direction *and* by whether it warns or blocks, before ranking the fix.
- **Do:** read the guard's emitted decision value to settle that, rather than assuming a false positive merely warns.
- **Don't:** expect a negation to be read as one --- it is the case no rendering remedy reaches,
  and the case a matcher covers only for the cues someone thought to enumerate.
- **Don't:** generalize a line-oriented checker's blindness to every checker,
  since this file's own opening says which you face is a fact to look up.
- **Don't:** rewrite a true sentence into a vaguer one to dodge a safe-direction false positive --- absorb it, or fix the detector.

(Measured 2026-09-03: a `Stop` hook fired on a negated sentence declining to file an issue,
reading it as the assertion it guards against.
Recorded on [#2988](https://github.com/Morrison-Lab/ai-config/issues/2988).)
