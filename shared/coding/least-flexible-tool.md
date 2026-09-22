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

**Third occurrence, 2026-08-24, after #1947 and #1973 above --- and the shape the `Don't` above does not literally name.**
That `Don't` fires on a second *widening*.
Here a widening and a run of **narrowings** sit in one matcher's history, which is the same rule from the other side: a pattern that cannot locate a token is equally unable to decide either direction.

`COMMENT_FLAG_RE` in `hooks/require-agent-disclosure.py` decides whether a `gh issue|pr close|reopen` segment posts a comment, which it does only when `--comment` or its shorthand `-c` is present.
It is defined on [ai-config#2185](https://github.com/Morrison-Lab/ai-config/pull/2185)'s branch only, that PR being open as of 2026-08-24.
Its short-flag alternative was edited four times on that branch, through five forms.
It began as `-c\s`, matching only the spaced spelling.
`-c(?:\s|=|\S)` accepts the attached and `=` spellings `gh` also takes, and puts `-c` within reach of the middle of a word --- executed against a **compliant** `gh issue close 5 -R Morrison-Lab/ai-config`, it is the one of the five that warns, on the `-co` inside `ai-config`.
Then three left-boundary conditions, in that order: `(?<![\w-])`, `(?<![\w\-"'])` once a preceding quote was found to slip past, and `(?<![^\s])` at `15b63d91`.

Every one of those four edits asks where a token's boundaries are, so they are one finding about tokenization wearing four costumes.
The last of them answered it by hand-rolling a boundary test rather than by asking what already computes one.
`shlex` is in the standard library and nine hooks in this repo already imported it at the first of those forms, so the layer that would answer the question was reachable throughout.
The layer change is **filed rather than shipped**, as [ai-config#2189](https://github.com/Morrison-Lab/ai-config/issues/2189), so this records a diagnosis rather than a demonstrated repair.

**The paragraph above makes no claim about which form answered which, deliberately.**
Two of the commits are concurrent siblings merged back together (see [`claim-pr`](../workflow/claim-pr.md)'s second-occurrence entry), so listing order does not carry the causal order there, and successive review rounds each refuted a different reconstruction of it.
The one attribution it does make --- that `(?<![\w\-"'])` was written against a **quote character** sitting immediately before the flag token --- is safe on both counts: `cf195e46` is an ancestor of `93363481` (`--is-ancestor` exits 0), and the reason is quoted from `93363481`'s own commit message, "a flag token is never preceded by a quote".
The rule never needed the rest: what makes this the third occurrence is that four edits to one matcher all ask where a token's boundaries are, which is a property of the forms rather than of their sequence.

- **Do:** write down the one question a run of fixes shares, before writing the next pattern --- if the answer names a lexical property (token boundaries, quoting, nesting), reach for the lexer.
- **Do:** name the construct you are hand-rolling when a fix adds a boundary test, an escape check, or a quote check to a regex, and search the standard library for it before writing it.
- **Do:** execute each revision of a matcher you are writing up and quote what it matched, rather than describing what its diff appears to do.
- **Do:** run `git merge-base --is-ancestor <claimed-cause> <claimed-response>` before writing that one commit responded to another, and drop the causal claim rather than reconstructing it when that exits **1** --- read any other non-zero status as the check having failed to run, per [`errexit-is-not-uniform`](errexit-is-not-uniform.md), and note that the operand order decides the answer, so a reversed test licenses the claim it was meant to refute.
- **Don't:** read a widening and a narrowing as different classes --- both are the same pattern failing to locate a token, and a widening that forces a narrowing is already the second edit the rule above warns about.
- **Don't:** count a boundary test that *generalizes* an earlier one as having changed layers;
  it is still the same construct answering a question it cannot decide.

(Dates Pacific; the commits are timestamped 2026-08-25 UTC.)

**Fourth occurrence, 2026-09-03 on [ai-config#3101](https://github.com/Morrison-Lab/ai-config/pull/3101), and the one that asks what to write down when the layer change cannot land in the round that found it.**
Everything above settles when to stop and what to reach for.
It leaves open the case where the lexer is a rework rather than a patch, so the round that diagnoses it ships a matcher it has just established cannot work.

The question there was whether an earlier command had *read a config manifest under the root about to be deleted*, which needs the verb, which argument is the operand, and which root that operand sits under.
All three are positional under #3126's remedy --- `argv[0]` membership for the verb, and the argument list for the rest --- and a pattern over raw text can decide none of them, so its revisions kept closing one boundary case while leaving a neighbouring one open.
A sample of what the rounds found, which is how [#3126](https://github.com/Morrison-Lab/ai-config/issues/3126) itself introduces the same list:

- a manifest *name* supplied with no root;
- the right shape under the wrong root;
- the deletion command clearing its own warning;
- a `grep` **for** the manifest string, over `.py` files;
- the root supplied as the search *pattern*, with the manifest belonging to a different root;
- a quoted pattern spelling out a whole path;
- `locate` matching because the word contains `cat`;
- a verb and an operand in two different commands, where the second one *deletes* the manifest.

The layer change is again filed rather than shipped --- `shlex` the command, then ask whether a read verb's argv holds a manifest under a targeted root --- which is [ai-config#2189](https://github.com/Morrison-Lab/ai-config/issues/2189)'s disposition arriving a second time
and is not what this occurrence adds.

**What it adds is the ceiling, written into the artifact.**
Three parts, and none of them stands alone.
Narrow the **comment** that overclaims, so the code stops asserting a guarantee it only approximates.
Add a limits section naming the residual cases in **both** directions, since what still slips through is only half of what a later reader needs and the false-positive half is the one that gets omitted.
File the layer change as its own issue, so the ceiling reads as temporary rather than accepted.

Note the boundary with [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s "A review flagging an overclaimed check is a prompt to build it, not to soften the claim".
That section rejects deleting an overclaiming sentence *in place of* building the instrument the finding asked for.
It also permits deletion outright for a genuine one-off --- "state plainly when a property is a genuine one-off, and delete the claim then" --- so deletion is not forbidden, only deletion standing in for an instrument that is still wanted.
This case is neither: the property is real and recurring, and the instrument is wanted but is a whole rework.

- **Do:** narrow an overclaiming comment to what the code actually does, in the same round that files the layer change.
- **Do:** write a limits section naming the residual cases in both directions --- what still fires wrongly, and what still slips through.
- **Don't:** ship a matcher you have just established cannot answer the question while its comment still claims it does.
- **Don't:** narrow the overclaim and stop where the instrument is still wanted --- without the filed issue that is the softening `algorithmatize-checks` refuses.

**Fifth occurrence, 2026-09-15 on [ai-config#3697](https://github.com/Morrison-Lab/ai-config/issues/3697) --- and the first where the raw text being matched is a whole session TRANSCRIPT rather than one live command.**

`hooks/warn-partial-validation-before-push.py` decides two things: whether a push should be warned about, and whether a named script already ran.
Both were first answered by substring search over command text, and an adversarial review found both directions broken.

`grep -r "run-local-validation.py" memories/` set the "the sweep already ran" flag and silenced the guard.
So did paging that script's own source.
That is the self-referential case this ladder had not yet produced: the text describing a check is input the check's own matcher reads, and a guard a grep of its own filename can switch off is treating its own documentation as evidence.
The mirror direction was live at the same time --- `grep -rn "scripts/check-ascii-punctuation.py" README.md` counted as having RUN that checker, so the warning asserted a run that never happened.

The fix is this rule's middle rung applied to a log of many commands instead of one: a script counts as invoked only when it occupies **command position** in some parsed command --- the program token itself, or an interpreter's first non-flag argument --- never when its name appears as somebody else's argument.
Finding command position is then its own ladder, and two rounds were spent climbing the wrong one.
`uv run <script>`, `timeout 60 python3 <script>` and `sudo -u someone python3 <script>` each hide the program behind a wrapper, so `argv[0]` reports `uv`, `60` and `-u`.
`shellcmd`'s `strip_env` does not rescue this, and for two different reasons worth keeping straight.
`sudo` IS one of its wrappers, so it peels that one and then returns unpeeled tokens when the bounded window after it holds no `git`.
`uv` is not a wrapper it knows at all, so it returns immediately without looking.
Either way the caller gets tokens whose head is not the program, and each wrapper needed its own case.

The escape was to stop asking which token is the program, and the FIRST attempt at that was still wrong in the same direction.
Asking instead whether the path is an argument to something that READS files --- `grep`, `cat`, `sed`, an editor --- is a blacklist, and a blacklist of this kind cannot be completed.
`flake8 <script>`, `some-linter --file=<script>` and `echo x > <script>` are all not-readers that were never listed, so each counted as a run and SILENCED the guard.

The same question asked as a whitelist works, and the FIRST whitelist written still did not.
Accepting a runner anywhere earlier in the argv reads `grep python3 scripts/run-local-validation.py` --- an ordinary way to inspect a shebang --- as a run of that script, and a Python file's own text carries the word `python3` constantly.
That silenced the guard again, which is the failure the whitelist was adopted to prevent, arriving one round later in a new costume.
What holds is requiring the runner to occupy command position itself: the script IS `argv[0]`, or `argv[0]` is a runner and the script is its first non-flag argument.

The cost is then explicit and runs one way.
`timeout 60 python3 <script>`, `sudo -u me python3 <script>`, `make check` and `$PY <script>` each genuinely run the thing and are not credited, so the warning fires when it need not have.
That spends a line of noise; the alternative spent the guard.
[`fail-fast`](../principles/fail-fast.md) settles which way an incomplete rule should lean, and that is what this rule's ladder does not say on its own: when no construct can be complete, take the one whose incompleteness fails closed, and write the residue down as a stated limit rather than leaving it to be rediscovered. (`bash -c "<script>"` is separate, and `shell_c_expansions` is the shared helper for it.)

The same commit had independently hand-rolled a `git push` regex, which missed a long global option taking a separate argument (`git --git-dir <path> push`) exactly as the first occurrence above did.
`scripts/lib/shellcmd.py` already exposes `git_subcommand`, which four other hooks consume.
Re-deriving it is this file's own `Don't` arriving as a second derivation rather than as a second widening --- and it is the defect the hook itself warns about, since a duplicated derivation is precisely what drifts from the thing it duplicates.

- **Do:** require command position, in a parsed command, when deciding from a log or transcript whether a script ran.
- **Do:** skip wrappers and interpreters before reading the program token, rather than trusting `argv[0]`.
- **Do:** call the shared parser for a CLI whose grammar the repo already models.
- **Don't:** count a path that appears as an argument to `grep`, `cat`, `sed` or an editor as an invocation.
- **Don't:** let a check read its own source or documentation as evidence about the world --- test that naming the guard does not disarm it.

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

A pattern meant to match **one line** is routinely written `^prefix.*$`,
and the flags are added later, for the sake of some other alternative in the same pattern.
That is where this bites,
because the two flags disagree about what a line is,
and the disagreement is silent:

- `re.M` makes `$` match before *any* newline, which is the reason it was added.
- `re.S` makes `.` match a newline too,
  which is usually wanted for a triple-backtick fence alternative sitting beside it.

Together, `.*` consumes the rest of the string and `$` is satisfied at the final position,
so the "one line" alternative matches **everything from the prefix onward**.
Nothing errors.
The pattern still matches the intended input.
It just also matches far more of it.

```python
re.compile(r"```.*?```|^\s*>.*$", re.S | re.M)          # the > branch eats the whole tail
re.compile(r"```.*?```|^[ \t]*>[^\n]*$", re.S | re.M)   # bounded, correct
```

Two properties make it hard to catch by reading.

**The flags are usually justified by a different alternative than the one they break.**
`re.S` is there for the fence; the damage lands on the blockquote.
So the line you would scrutinize and the line that is wrong are not the same line.

**It fails toward silence in a stripper.**
A function that removes regions before matching gets *more* removal than intended,
so its consumer simply stops firing --
which looks like "no findings" rather than like a bug.
A suite of positive tests passes.

The general rule this instantiates:
`.` and `\s` are the two most flexible character constructs available,
and reaching for either inside a line-anchored pattern discards the anchor's meaning under `re.S`.
Use the explicit negated class instead --
`[^\n]` for "rest of this line", `[ \t]` for "horizontal space" --
which says what is meant and is immune to the flag.

- **Do:** write `[^\n]*` when you mean "to the end of this line",
  in any pattern compiled with `re.S`.
- **Do:** write `[ \t]` rather than `\s` for leading indentation,
  since `\s` matches a newline regardless of flags.
- **Do:** add a negative test whose *removed* region is followed by real content,
  since an over-broad stripper is invisible to positive tests.
- **Don't:** add `re.S` for one alternative
  without re-reading every other alternative in the same pattern for `.` and `$`.
- **Don't:** trust that a passing suite covers this --
  over-removal reads as correct silence.

(Measured on
[ai-config#2024](https://github.com/Morrison-Lab/ai-config/pull/2024),
2026-08-23.
`hooks/no-unfiled-finding.py`'s code-region stripper was written with `re.S | re.M`
and a blockquote alternative of `^\s*>.*$`.
It deleted every character after the first `>` line,
so any real assertion following a quoted one went unexamined.
The whole suite passed --- every case in it, not a subset.
(The exact figure is method-dependent and so deliberately not quoted here;
see ai-config#2030.)
A reviewer found it and suggested `^[ \t]*>[^\n]*$`;
that plus a regression test -- a genuine unquoted assertion following a blockquote --
is what shipped.)

## A descent closes the detection asymmetry and opens an exemption one

Everything above is about *reaching* the wrapped command.
The mirror case arrives once you have: a guard that descends into `-c` now
evaluates the same push twice, under two code paths, and the paths that
decide an **exemption** are not the paths the descent was written for.

The direction of the asymmetry flips, and that is what makes it hard to see.
Before the descent, the bare form is caught and the wrapped form escapes, so
every test you write is a wrapped command that ought to be refused.
After it, the exemption path can honour a spelling for the wrapped command that
the bare-command path still refuses --- and no test of the shape "is the
wrapper still caught" can fail on that, because the wrapper *is* caught,
just not when the author asks for the escape hatch.

An escape hatch that works only for the wrapped spelling teaches wrapping.
It is a worse outcome than the original bypass, because the original was an
oversight nobody was steered toward, while this one trains the habit on the
exact author who read the refusal and tried to comply.

Measured 2026-09-15 on `hooks/no-clobbering-push.py` at `8711c8d4`
(the [ai-config#1973](https://github.com/Morrison-Lab/ai-config/issues/1973)
branch), running the hook with `--dry-run`:

```
export ALLOW_FORCE_PUSH=1; git push --force origin main          -> deny
export ALLOW_FORCE_PUSH=1; sh -c "git push --force origin main"  -> silent
ALLOW_FORCE_PUSH=1 git push --force origin main                  -> silent
sh -c "git push --force origin main"                             -> deny
```

`_override_before_wrapper` grew an `export` arm so the hatch works in its most
natural spelling for a wrapped push.
`_lead_prefix`, which decides the override for the unwrapped push, still reads
an assignment only from the same simple command's own head, so `export` does
not reach it.
Filed as
[ai-config#3664](https://github.com/Morrison-Lab/ai-config/issues/3664).

The check is one table, and it costs nothing once the descent exists: for each
spelling of the exemption, record the verdict for the bare command and for the
wrapped one, and read any row where they differ as a defect whichever way it
leans.
A row that is stricter for the wrapped form is the over-warning complaint;
a row that is looser is this one.

- **Do:** enumerate the exemption spellings and run each one bare and wrapped,
  as a table, after adding a descent.
- **Do:** fix a disagreeing row in either direction --- teach the bare path the
  spelling, or drop it from the wrapped path --- rather than picking the arm
  that is easier to edit.
- **Don't:** read "the wrapped form is still caught" as covering the exemption
  paths; those tests pass on exactly the command the hatch is not being used on.
- **Don't:** leave the looser arm standing because the escape hatch is meant to
  be usable --- usable in one spelling only is a lesson in how to wrap.
