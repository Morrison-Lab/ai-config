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
