Use the least-flexible construct that does the job.
When two constructs both work, prefer the one that can do less, because a
narrower construct announces its own purpose and a general one does not.

*Advanced R* states this directly and builds a ladder from it.
On loops, in
[Related tools](https://adv-r.hadley.nz/control-flow.html#for-family):

> You can rewrite any `for` loop to use `while` instead, and you can rewrite
> any `while` loop to use `repeat`, but the converses are not true.
> That means `while` is more flexible than `for`, and `repeat` is more
> flexible than `while`.
> It's good practice, however, to use the least-flexible solution to a
> problem, so you should use `for` wherever possible.

And one rung further up, in
[Functionals](https://adv-r.hadley.nz/functionals.html):

> the real downside of for loops is that they're very flexible: a loop
> conveys that you're iterating, but not what should be done with the
> results.
> Each functional is tailored for a specific task, so when you recognise the
> functional you immediately know why it's being used.

## The ladder

From most flexible to least, prefer the last one that fits:

`repeat` -> `while` -> `for` -> a functional (`map()`, `reduce()`,
`some()`, ...) -> a vectorised call over the whole object.

Reading `repeat` tells you nothing but that something recurs.
Reading `map_dbl(x, f)` tells you the length of the result, its type, and
that each element is handled independently.
That information is carried by the choice of construct, so it costs the
reader nothing and it cannot go stale.

## Beyond loops

The same argument decides several rules already in this corpus, which is
the sign it is the general form rather than a loop-specific tip:

- [`per-operation-grouping`](per-operation-grouping.md) prefers `.by=` over
  `group_by()`/`ungroup()`, because `.by=` cannot outlive the verb it is
  attached to.
- [`type-stable-outputs`](type-stable-outputs.md) prefers `map_dbl()` over
  `map()` plus `unlist()`, because `map_dbl()` cannot return anything but a
  double vector.
- A constant belongs in `const`-equivalent form, a helper stays local rather
  than exported, and a script's scope stays as small as it can be.

## The escape hatch

Do not reach past the ladder for a construct that does not actually fit.
The book is explicit that forcing the fit is worse than the loop:

> If one doesn't exist, don't try and torture an existing functional to fit
> the form you need.
> Instead, just leave it as a for loop!

A `map()` call carrying a lambda that mutates shared state, threads an
index, and returns `NULL` is a `for` loop wearing a functional's name.
It has given up the readability that motivated the ladder while keeping the
cost.
Write the loop, and apply [`loop-hygiene`](loop-hygiene.md) to it.

The book adds the useful trigger for revisiting that decision: once the same
loop has been written two or more times, that is the moment to consider
writing your own functional for it.

## Parsing, where the ladder costs more to climb

Every rung above is free.
A `for` loop is no more code than a `while`, and `map_dbl()` is less code than
either, so the narrower construct is cheaper as well as clearer.

Parsing inverts that, which is why it needs stating rather than leaving to the
general rule.
The narrow construct is the one that costs more up front, so the general
construct wins every local comparison and loses over the life of the code.

The ladder, for the question "does this command do X?":

a regex over the raw command string
-> token comparison over a real lexer's output
-> resolving the *effective* command, by descending into an interpreter's
`-c` argument.

**A regex over a shell command matches shapes, and the question is about
grammar.**
"Is this token being executed?" depends on word splitting, on quoting, and on
which token sits in command position --- none of which is a property of
character adjacency.
Shell grammar also nests, since a `-c` argument holds another command, so no
finite pattern over the raw string decides it in principle rather than merely
in practice.
A regex can enumerate the shapes someone has already seen.
That is a different thing from answering the question, and the difference only
shows up one bypass at a time.

The observable trigger is the second patch.
When a second fix to the same matcher closes a second instance of one class,
[`learn-from-review-findings`](../workflow/learn-from-review-findings.md)'s
recurrence rule already says to stop asking what else the pattern should match.
This fragment says what to reach for instead when the subject is a command.

**Climbing one rung is not arriving, and the corpus is the worked example.**
Measured 2026-08-22 across the 36 non-test hooks in this repo.
Six decide what a command does by comparing tokens rather than by matching the
raw string, and not one of them descends into an interpreter's argument.
So the bare form is caught and the wrapped form is not:

```
git push --force origin main          # denied
sh -c "git push --force origin main"  # no output, rc=0
```

`hooks/flag-reset-hard-uncommitted-work.py` reproduces it on
`git reset --hard`.
Token comparison closed the adjacency class and left the wrapper class open,
which is the middle rung mistaken for the top one.
Tracked as
[ai-config#1973](https://github.com/Morrison-Lab/ai-config/issues/1973).

The cost argument is worth stating plainly, because it is what makes the
regex tempting each time.
A pattern is one line.
Tokenizing is about five, and the descent perhaps ten more, paid once.
On [ai-config#1947](https://github.com/Morrison-Lab/ai-config/pull/1947) the
one-line version cost four review rounds, each closing one wrapper shape and
leaving the next.

- **Do:** reach for a lexer when the question is about a command's structure,
  and treat the up-front cost as bought rather than spent.
- **Do:** name the rung you stopped on, so a reader can tell a deliberate stop
  from an assumed top.
- **Do:** descend into an interpreter's `-c` argument when the guard's subject
  is what actually runs.
- **Don't:** widen a pattern over a raw command string a second time --- the
  second widening is the signal that the construct cannot answer the question.
- **Don't:** read "it tokenizes" as "it is correct" --- that is one rung, and
  the wrapper class lives above it.

## In review

Flag these with the same weight as the other coding rules:

- A `while` or `repeat` where the set of values to iterate over is known up
  front, and `for` would do.
- A `for` loop whose body is a single independent transformation per
  element, where a `map_*()`/`vapply()` call would say the same thing.
- A regex over a raw shell command string deciding what that command
  does, where tokenizing would answer the question instead of matching
  one more shape of it.
- A functional twisted to fit a shape it does not have --- a lambda mutating
  enclosing state, or one whose return value is discarded --- where the loop
  it replaced was clearer.

The last one is a finding in the opposite direction from the others, and
that is deliberate: this rule is not "use functionals", it is "let the
construct match the job".

## `re.S` and `re.M` together: `.*$` runs to the end of the string, not the line

A pattern meant to match **one line** is routinely written `^prefix.*$` and the
flags are added later, for the sake of some other alternative in the same
pattern. That is where this bites, because the two flags disagree about what a
line is and the disagreement is silent:

- `re.M` makes `$` match before *any* newline, which is the reason it was added.
- `re.S` makes `.` match a newline too, which is usually wanted for a
  `` ```.*?``` `` fence alternative sitting beside it.

Together, `.*` consumes the rest of the string and `$` is satisfied at the final
position, so the "one line" alternative matches **everything from the prefix
onward**. Nothing errors, and the pattern still matches the intended input --
it just also matches far more of it.

```python
re.compile(r"```.*?```|^\s*>.*$", re.S | re.M)   # the > branch eats the whole tail
re.compile(r"```.*?```|^[ \t]*>[^\n]*$", re.S | re.M)   # bounded, correct
```

Two properties make it hard to catch by reading.

**The flags are usually justified by a different alternative than the one they
break.** `re.S` is there for the fence; the damage lands on the blockquote. So
the line you would scrutinize and the line that is wrong are not the same line.

**It fails toward silence in a stripper.** A function that removes regions
before matching gets *more* removal than intended, so its consumer simply stops
firing -- which looks like "no findings" rather than like a bug. A test that
only checks the intended positives passes.

The general rule this instantiates: `.` and `\s` are the two most flexible
character constructs available, and reaching for either inside a
line-anchored pattern discards the anchor's meaning under `re.S`. Use the
explicit negated class -- `[^\n]` for "rest of this line", `[ \t]` for
"horizontal space" -- which says what is meant and is immune to the flag.

- **Do:** write `[^\n]*` when you mean "to the end of this line", in any
  pattern compiled with `re.S`.
- **Do:** write `[ \t]` rather than `\s` for leading indentation, since `\s`
  matches `\n` regardless of flags.
- **Do:** add a negative test whose *removed* region is followed by real
  content, since an over-broad stripper is invisible to positive tests.
- **Don't:** add `re.S` for one alternative without re-reading every other
  alternative in the same pattern for `.` and `$`.
- **Don't:** trust that a passing suite covers this -- over-removal reads as
  correct silence.

(Measured on
[ai-config#2024](https://github.com/Morrison-Lab/ai-config/pull/2024),
2026-08-23. `hooks/no-unfiled-finding.py`'s code-region stripper was written as
`` r"```.*?```|^\s*>.*$" `` with `re.S | re.M`; the blockquote alternative
deleted every character after the first `>` line, so any real assertion
following a quoted one went unexamined. Twenty-seven tests passed. A reviewer
found it, suggested `^[ \t]*>[^\n]*$`, and that plus a regression test -- a
genuine unquoted assertion following a blockquote -- is what shipped.)
