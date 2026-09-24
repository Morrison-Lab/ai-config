When authoring regular expressions that handle variable user or reviewer text,
ensure that repeated groups and quantifiers cannot backtrack catastrophically
on non-matching or pathological inputs.

## Self-ambiguous alternatives under repetition

A regular expression engine exploring a repeated group `(A|B)*` or quantifier
attempts every combination of alternatives when an input fails to match
downstream.
Even when every alternative branch consumes at least one character,
an alternative that can match the same token in multiple chunk sizes
is **self-ambiguous** and partitions input exponentially.

For example, `={3,}` under an outer `*` quantifier
can partition a run of `=` characters into chunks of size 3 or greater
in exponentially many distinct ways.
When matching a trailing tolerance group followed by non-matching text,
the engine evaluates all partitions before rejecting the input:

```python
# Backtracks exponentially on non-matching text following repeated '=':
pattern = re.compile(
    r"Reviewed-Commit:\s*[a-f0-9A-F]+(?:\s*(?:[A-Za-z]+|={3,}|\s*))*\Z"
)
```

Measured on an increasing prefix of a `"=" * 60` banner followed by non-matching text:
- 36 characters: 0.50s
- 42 characters: 4.01s
- 45 characters: 14.18s

Removing an empty `\s*` alternative is necessary but not sufficient:
`={3,}` alone under an outer `*` still partitions runs of `=` exponentially.

## Overlapping alternation branches

Alternation branches under a quantifier must remain disjoint on their matchable
character classes and prefixes.
If branch A and branch B can consume the same leading character
(such as `\([^()\n]{0,120}\)` and `[^,:;.!?]`, both of which consume `(`),
a failing input like `"(1) " * 24` triggers exponential backtracking.

## Backtracking through an optional group can defeat a following negative lookahead

Catastrophic backtracking wastes time; this failure wastes correctness while
running instantly, so nothing about a slow run flags it.
A negative lookahead placed immediately after an optional group is
positioned to reject the specific token that follows the group when it is
present --- but a regex engine tries the group's "present" branch first and
only falls back to its "absent" branch if the rest of the pattern then
fails.
So a lookahead written to suppress one phrase can still match, provided some
*other* token after the optional group makes the whole match succeed with
the group absorbed as absent.

```python
r"no (?:\w+ ){0,3}(?:can|will|could) (?:ever )?(?!be\b)\w+"
```

`(?!be\b)` was added to stop this pattern matching "will be needed" and
"will be required" --- ordinary, non-absolute prose.
It stops the literal case, "no X will be ...", because there the group is
empty and the lookahead sits directly before `be`.
It does not stop "no X will *ever* be ...": the engine first tries `(?:ever
)?` present, lands on `be`, and the lookahead --- which only inspects the
text immediately to its right --- has nothing to say about the `ever` that
already matched behind it.
The suppression and the phrase it was written for are separated by exactly
the group the fix never accounted for.

(Measured 2026-09-17 on `ai-config#3737`,
`hooks/warn-unmeasured-capability-claim.py`'s `RX_ABSOLUTE`.
Reproduced directly against the shipped pattern: `"No hooks can be read"` ---
a genuine absolute-capability claim, the true positive this hook exists to
catch --- does not match, because there the lookahead does sit directly
before `be`.
`"No changes will ever be needed"` --- ordinary prose, the exact false
positive `(?!be\b)` was added to suppress --- does match, at `"No changes
will ever"`, because the optional `ever` gave the engine a way in that skips
past the lookahead's blind spot entirely.)

- **Do:** test a negative lookahead placed after an optional group against
  the phrase with the optional part **both present and absent**; a fix
  verified only on the absent case has not exercised the group at all.
- **Do:** move the exclusion to look past the optional group too --- a
  lookahead of `(?!(?:ever )?be\b)` covers both branches the group can take
  --- when the group's content should not change what gets excluded.
- **Don't:** trust that a lookahead "right before" the token it excludes
  covers every path to that token; an optional group upstream is a second
  path the lookahead never sees.
- **Don't:** treat the false positive the lookahead was written for as
  fixed once one phrasing of it stops matching; vary the optional pieces of
  the match and re-test.

## Quadratic cost can come from restart positions, not from backtracking

Every section above describes a pattern that is slow **on one match
attempt**, so every remedy below targets the attempt: make the quantifiers
disjoint, flatten the nesting, scan line by line.
A `finditer` sweep has a second cost axis those remedies never touch.
`finditer` restarts the engine at each position where the pattern can begin,
and when the tail of the pattern can run to the end of the string, each
restart scans the whole remainder.
The total is then quadratic in the number of **start positions**, with no
backtracking anywhere.

The tell is that rewriting the quantifier changes nothing, which reads as
"I have not found the pathological construct yet" and is really "the cost is
not in the construct".
Confirm it by holding the input length fixed and varying the number of
positions the pattern can start at.
If time tracks the starts rather than the length, no rewrite of the pattern
will help.

Measured 2026-09-24 against a heredoc matcher whose opener is `<<` and whose
body runs to a terminator that an unterminated heredoc never supplies:

```text
openers   chars   seconds
    200    1614     0.020
    400    3214     0.080
    800    6414     0.314
   1600   12814     1.207
   3200   25614     4.787
```

Doubling the openers quadruples the time.
The same matcher over ONE terminated heredoc is untroubled by length:
240024 characters take 0.003s --- ten times the input of the 3200-opener case
and a sixteen-hundredth of the time.

Rewriting the body quantifier as a negated character class, in place of a
DOTALL `.`, is equivalent to the engine and changed nothing.

**The cost is the number of start positions multiplied by the work each start
does, and both factors need bounding.**
An earlier revision of this section stated the first factor alone and wrote
"length is not the variable", on the strength of a measurement that had held
openers-per-line fixed at one and never varied the other factor.
That is false for the very matcher it cites.
The pattern opens with a capturing `([^\n]*)` that may match empty, so the
engine also restarts at every character of every line and each restart walks
that line to its end, which makes the second factor the sum of the SQUARES of
the line lengths.
At an identical 25600 bytes, one long line took 1.65s and the same bytes
broken into 80-character lines took 0.007s, with no opener in either.
So a short input with many starts is one expensive case and a long LINE with
no start at all is another.

**Bound both, and bound them over the region the matcher will actually
scan.**
The shipped guard refuses past 32 heredoc openers and past a restart-cost
budget, counting neither over heredoc BODIES, which the matcher never
rescans.
Skipping bodies is what makes the cost bound safe for the case a plain length
cap would have broken: a single heredoc carrying a 60KB body still matches, in
0.0008s, because its body scores nothing.
A 20000-opener command is refused in 0.036s, essentially all of it the split
into lines.

Say which way the refusal falls, because that is a separate decision from the
bound.
This one is an EXEMPTION -- past the bound the body is unreadable and the hook
stays silent -- which is right for a warn-only guard and wrong for a guard
whose silence is an approval.

- **Do:** vary each factor with the other held fixed, before concluding a
  pattern backtracks.
- **Do:** bound the start count AND the span each start scans.
- **Do:** compute either bound over the region the matcher rescans, so the
  input's own inert bulk does not vote.
- **Don't:** read "rewriting the quantifier changed nothing" as evidence you
  have not found the construct --- it is evidence the cost is elsewhere.
- **Don't:** treat a length cap as a proxy for the start count, or the start
  count as a proxy for length; they are independent, and a measurement that
  varied only one of them cannot say the other is inert.

## Remedies

1. **Replace nested quantifiers with linear scans.**
   When scanning for a structured marker or header preceded by delimiters,
   use line-by-line scans or string operations rather than nested regex
   quantifiers.
   A linear line scan cannot backtrack across line boundaries and runs in
   sub-millisecond time even on thousands of characters.
2. **Enforce first-character disjointness on alternations.**
   Ensure that branches under a shared quantifier cannot match the same starting
   characters or prefixes.
3. **Time pathological non-matching inputs.**
   Test regular expressions against repeated runs of delimiter characters
   followed by non-matching text (e.g. 60+ repeated characters) to confirm linear
   performance.

- **Do:** replace nested or repeated quantifiers with linear line scans
  or string operations.
- **Do:** ensure alternation branches under a quantifier have disjoint character
  classes.
- **Do:** test regular expressions with pathological non-matching inputs
  and measure execution time.
- **Don't:** assume non-empty token consumption prevents catastrophic
  backtracking --- self-ambiguous quantifiers partition inputs exponentially.
- **Don't:** rely on regex timeout defaults when parsing untrusted or multiline
  input.

(Measured on Morrison-Lab/ai-config PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736):
`scripts/pre-push-review.py`'s fingerprint matcher backtracked on its own 60-character
banner separator.
Replacing the nested quantifier with a linear line scan reduced execution time
from 14.18s at 45 characters to 0.36ms at 4000 characters.)
