`set -e` does not apply everywhere, and the places it stops applying are not
obvious.
A failing command aborts the script in most positions, but bash suppresses
`errexit` in several contexts -- and one of them makes a helper's safety
depend on **how it is called** rather than on what it does.

That is the dangerous shape, because a helper can be correct at every call
site today and abort the moment someone calls it one line differently.

## The case that motivated this

```bash
set -euo pipefail

fence_for() {
  local longest
  longest="$(grep -oE '`+' <<<"$1" | awk '{ if (length($0) > m) m = length($0) } END { print m + 0 }')"
  ...
}
```

`grep` exits 1 when it matches nothing.
Under `pipefail` the pipeline then fails, and under `set -e` that aborts.
But whether it actually aborts depends on the caller:

```bash
fence_for "$text"              # aborts, exit 1, no output
x="$(fence_for "$text")"       # survives, runs to completion
```

A command substitution runs in a subshell, and that subshell does **not
inherit `errexit`** by default, so the failing `grep` never aborts anything
and `fence_for` runs to completion.
Every call site happened to use the second form, so the bug was invisible ---
and it would have surfaced only on the inputs with no matches, which here
meant the least informative failures, the ones the code existed to explain.

Two things make this worse than a helper that is merely fragile.

The suppression is a **default, not a guarantee**: `shopt -s inherit_errexit`
makes command substitutions inherit `errexit`, at which point the assignment
form aborts too.
So a repo that later hardens its scripts --- or a single script that sets it
--- turns a dormant bug into a live one, in code nobody touched.

And a plain subshell behaves the *opposite* way, which is why this is easy to
misremember:

```bash
x="$(f)"    # substitution subshell: does not inherit errexit (by default)
( f )       # plain subshell: does inherit it, and aborts
```

Verified on bash 5.2.21: with `inherit_errexit` off the assignment form exits
0 and prints the captured output; with it on the same script exits 1 and
prints nothing.

## The rule

Do not let a helper's correctness rest on the suppression contexts.
Handle the expected non-zero exit **where it happens**, so the behaviour is
the same however the helper is called:

```bash
longest="$( { grep -oE '`+' <<<"$1" || true; } | awk '...' )"
```

This is [`fail-fast`](../principles/fail-fast.md) read in the other
direction.
That rule bans swallowing failures you did not expect; this one says an
*expected* non-zero exit --- grep finding nothing, `diff` reporting a
difference, `[[ ]]` testing false --- is not a failure at all, and must be
stated as tolerated rather than left to whether the caller's syntax happens
to mask it.

The commands that routinely exit non-zero without anything being wrong:
`grep` (no match), `diff`/`cmp` (differences found), `[[ ]]` and `test`
(false), `read` (EOF), `git diff --quiet` (changes present).

## The contexts, so you can recognize them

`errexit` is suppressed for a command in any of these positions:

- the condition of `if`, `while`, or `until`
- any command in an `&&` or `||` list except the last
- a command whose status is inverted with `!`

And, separately from that list, a command substitution's subshell does not
inherit `errexit` unless `shopt -s inherit_errexit` is set --- the case
above.
That one is not a "position" at all, which is part of why it is missed:
the same command aborts or does not depending on whether it sits inside
`$( )`.

All four were confirmed directly rather than recalled, and the third has an
interaction with testing, below.

The second of those positions carries a separate defect that has nothing to do
with `errexit`, so a `||` chain can be silent in two ways at once.
This fragment governs the exit status such a chain suppresses; the branches can
also print output that does not say which of them ran, which
[`fail-fast`](../principles/fail-fast.md) owns under "A fallback chain flattens
which alternative won".

## Testing this is where it goes wrong twice

A regression test for an `errexit` bug is unusually easy to write wrongly,
because the natural way to capture "did it abort?" is itself a suppression
context:

```bash
( fence_for "no backticks" ) || echo "ABORTED"     # always passes
```

The `( ... ) ||` wrapper exempts the subshell, so the buggy version and the
fixed version both survive and the test proves nothing.
The same is true of `if buggy_fn; then`, of `buggy_fn && echo ok`, and of
capturing the result with `x="$(buggy_fn)"` --- every convenient way to ask
"did this abort?" is on the list of things that stop it aborting.

`! buggy_fn` deserves its own mention, because it is the most natural thing
to reach for when the expected result is a non-zero exit, and it fails
twice over: the `!` operand is a suppression context, so the abort does not
happen, *and* `!` inverts the status of whatever did happen.
The test then passes against the buggy and the fixed version alike, for two
independent reasons.

Expect to get this wrong on the first attempt and to notice only because the
buggy version passes.

Run the call as a **plain statement in its own script**, and read the exit
status from outside:

```bash
printf 'set -euo pipefail\n%s\nfence_for "no backticks"\necho survived\n' \
  "$definition" > /tmp/t.sh
bash /tmp/t.sh; echo "EXIT=$?"
```

Then confirm the test actually distinguishes the two versions --- old exits
1 and prints nothing, fixed exits 0 --- per the regression-test rule in
[`ardi`](../workflow/ardi.md).
A test that passes against both is not a test.

- **Do:** tolerate an expected non-zero exit at the point it occurs, with
  `|| true` or an explicit `if`, so the helper behaves identically at every
  call site.
- **Do:** exercise an `errexit` regression test as a plain statement in a
  standalone script, and check it fails before the fix.
- **Don't:** rely on a call site's syntax to suppress a failure you know can
  happen.
- **Don't:** wrap the call in `( ... ) ||`, `if`, or `!` when testing whether
  it aborts --- all three are the very contexts that suppress the abort.

## A status consumed as a predicate cannot say "I could not run"

Everything above is about a script failing to **abort**.
When the suppressed status is fed to an `if`, the script does something worse
than continue: it **chooses a branch** on it.

A command's exit status is a single integer doing two jobs at once, and a
boolean test collapses them.
`grep` answers "no match" with 1, and a command that is not installed never
answers at all --- the shell reports 127 on its behalf.
`if ! cmd` maps both to true.
So a missing dependency does not report a missing dependency.
It reports a negative result, confidently, in the vocabulary the script was
expecting.

Keep those two sources straight when reading a status, because only one of
them is documented anywhere you would think to look.
`man grep` lists 0, 1, and 2 and stops, so a reader who goes looking for 127
there finds nothing and concludes the claim is wrong.
127 is the shell's, for a command it could not find, and it is therefore
available from *any* command --- which is exactly why a predicate cannot
distinguish it from that command's own answer.

The shape, from a git pre-commit hook:

```bash
set -euo pipefail

if ! git diff --cached --name-only | rg -q '^R/.*\.R$'; then
  exit 0
fi

Rscript -e 'devtools::document()'
```

With ripgrep absent the pipeline exits 127, `!` inverts it to true, and the
hook exits 0 having done nothing.
Note that `set -euo pipefail` is present and buys nothing here: the `if`
condition and the `!` operand are both on the suppression list above, so the
hardening is real everywhere except the one line that decides what the script
does.

Two properties make this worse than the cases above.

The wrong branch is usually the **cheap** one.
A guard asks "is there anything to do?", so the error is absorbed into "no",
and the failure mode is skipping the work rather than doing it twice.
That is [`fail-fast`](../principles/fail-fast.md)'s guard rule arriving through
the exit status: an assertion of absence resting on the non-appearance of a
success.

And the result is **machine-dependent**, which is why it survives review.
It behaves correctly for whoever has the tool installed, so the author cannot
reproduce it and the hook looks like it works.
Reach for a portable tool in anything you ship to other people's machines, and
check the dependency up front so a missing one is loud:

```bash
command -v rg >/dev/null || { echo "rg not installed" >&2; exit 1; }
```

Where the three outcomes genuinely differ, read the status rather than testing
it, per [`fail-fast`](../principles/fail-fast.md)'s rule that 0, 1, and
anything else are three answers and not two:

```bash
rc=0
git diff --cached --name-only | grep -qE '^R/.*\.R$' || rc=$?
case $rc in
  0) : ;;                                     # matched
  1) exit 0 ;;                                # no match
  *) echo "grep failed ($rc)" >&2; exit 1 ;;  # broken
esac
```

The `|| rc=$?` is load-bearing rather than decorative, and it is the same
suppression the rest of this fragment warns about, used deliberately: a bare
pipeline under `set -e` aborts on the no-match case before `case` ever runs,
so the status has to be captured somehow before the branch that handles it is
reachable.
That form is the most compact way, not the only one --- `set +e` around the
call, or `if cmd; then rc=0; else rc=$?; fi`, reach the same branch.
All three were measured on bash 5.1.16 and give `rc=1` on no match; the
`|| rc=$?` form gives `rc=127` when the command does not exist.

One residual that `-q` introduces, worth knowing precisely because `-q` is
what a guard reaches for --- and which turns out to prove this section's own
point a second time.

GNU grep's manual says that "if the `-q` or `--quiet` or `--silent` is used
and a line is selected, the exit status is 0 even if an error occurred", so
the flag that makes a check quiet also lets a match **outrank** a genuine
error.
Measured on GNU grep 3.7, matching one readable file and one missing file:
`-q` gives `rc=0` and the same command without `-q` gives `rc=2`.

The reason to measure rather than quote is that the same command on the same
machine disagreed with itself, depending on whether it ran in a script.
Typed at an interactive prompt there, `grep` reported `rc=2` for those
identical inputs.
Put into a file and run with `bash script.sh`, it reported `rc=0`.

That is not `PATH` shadowing, and the distinction decides what to do about
it.
`grep` at that prompt was a **shell function**, installed by the harness and
routing to a `ugrep` bundled inside another binary; `type -aP grep` finds
only `/usr/bin/grep` and `/bin/grep`, both GNU, and no `ugrep` exists on
`PATH` at all.
A function reaches a child shell only if it was exported with `export -f`,
and this one was not --- `type -t grep` in a child reports `file`, the
binary.
The script therefore got GNU grep and masked; the prompt got ugrep and did
not.
Do not shorten that to "functions do not survive into child shells".
`export -f` propagates one, measured, so the load-bearing fact is about this
particular function rather than about functions.

Which makes this worse than a portability footnote for the hook above, since
**a git hook is a child shell**.
It gets GNU grep, so it does mask, and a developer who validates the hook's
behaviour by running the same pipeline in their terminal is measuring a
different program than the one git will run.

The usual identification commands differ in how much they give you here,
which is the part worth memorizing.
`command -v grep` prints a bare `grep` when a function is winning and an
absolute path when one is not, so it does signal that something off-`PATH`
has taken over --- it just does not say what kind of thing.
`type -aP grep` reports only binaries, so it hides the function entirely and
is the one that will actively mislead you.
`type -a grep` names it, and running the command inside a throwaway script
settles what your hook will really get.

Neither implementation reaches the missing-command case above, since a command
that never ran cannot select a line, so 127 arrives intact either way.
What `-q` costs you on GNU grep is the "broken" versus "matched" distinction,
not "broken" versus "no match".
Drop `-q` and redirect to `/dev/null` where that difference matters, and
establish which implementation your *script* gets before trusting any of
these codes --- from inside a script, not from your prompt.

- **Do:** verify a tool exists before branching on its exit status, in
  anything that runs on a machine you do not control.
- **Do:** identify a command with `type -a` and a throwaway script, rather
  than with `type -aP` alone, which reports only binaries and so hides a
  shell function that is winning interactively and absent in the child shell
  your hook runs in.
- **Do:** read a bare name from `command -v` as the signal that something
  off-`PATH` is winning; it is a real tell, and it does not tell you what
  kind of thing, which is what `type -a` adds.
- **Do:** distinguish 0, 1, and 2-or-more when a command's failure and its
  negative answer call for different actions.
- **Don't:** read `set -euo pipefail` at the top of a script as covering an
  `if` condition or a `!` operand -- both are on the suppression list above.
- **Don't:** treat a guard that skipped its work as having found nothing to
  do; on a missing dependency those are the same observation.

(`ucdavis/bcs#554`, 2026-08-03: the hook above is the verbatim one shipped in
that repo.
Observed live on a machine without ripgrep -- a commit staging an `R/*.R` file
printed `.githooks/pre-commit: line 4: rg: command not found` and was accepted,
with `devtools::document()` never running.
Confirmed with a negative control: the same logic with `grep -qE` substituted
takes the other branch on the same staged files, so the branch really was
selected by the missing binary rather than by the file list.
How many other contributors lack ripgrep was not established -- the point is
that the hook's behaviour depends on it and says so nowhere.)

## A pipe discards the status of everything left of it

Everything above is about `errexit` not firing.
The sibling defect is that the status `errexit` would have read is gone before
it gets there: a pipeline's exit status is its **last** command's, so piping a
command into anything at all throws away whether that command succeeded.

The shape is a command piped only to trim or format its output, with a
fallback attached:

```bash
git branch -d "$b" | tail -1 || echo "  (unmerged, keeping $b)"
```

`tail` succeeds on empty input, so the pipeline succeeds whatever `git` did.
The fallback is unreachable, `set -e` sees a zero status and does not abort,
and the branch that failed to delete is silently reported as handled.
Both the check and its own error path are lost in one character.

`set -o pipefail` fixes exactly this, by making the pipeline take the
rightmost non-zero status.
That is worth knowing precisely because it means the bug is **conditional on
the script's options** rather than intrinsic --- the same line is correct in a
`set -euo pipefail` script and broken in a `set -eu` one, so a snippet copied
between two scripts changes meaning with nothing at the call site to show it.
Measured on bash 5.1.16:

```bash
$ bash -c 'set -eu;            false | tail -1 || echo FALLBACK; echo "rc=$?"'
rc=0                      # no fallback, no abort --- the failure vanished
$ bash -c 'set -euo pipefail; false | tail -1 || echo FALLBACK'
FALLBACK
```

Two remedies, and prefer the first.
Set `pipefail` alongside `errexit` in any script that pipes commands whose
success matters --- it is one word and it fixes every such line at once.
Where a single call needs the status and `pipefail` is not in force, take the
status before the pipe rather than after it: capture the output first
(`out="$(cmd)" || fallback`), test the command on its own, or read
`${PIPESTATUS[0]}` immediately after the pipeline.

This is the same [`fail-fast`](../principles/fail-fast.md) shape the
`|| echo "none"` case above has, arriving by a different route: there the
failure and the clean result printed the same thing, here the failure is
never given a chance to print anything.

- **Do:** set `pipefail` with `errexit`, so a pipeline reports the failure of
  any stage rather than only its last.
- **Do:** read `${PIPESTATUS[0]}`, or split the pipeline, when one specific
  stage's status is the thing you need.
- **Don't:** attach `|| fallback` to a pipeline and expect it to fire for a
  failure on the left-hand side.
- **Don't:** pipe a command through `head`, `tail`, `tr`, or `grep` purely to
  tidy its output when its exit status is the point.

(2026-07-29, a bcs branch sweep: `git branch -d "$b" | tail -1 || echo ...`
under `set -eu` reported every branch deleted, including the ones `git` had
refused.)

### An ad-hoc `&&` chain is the same defect with nowhere to put the remedy

The section above assumes a script, so both its examples end in `|| fallback`
and its preferred fix is a `set` line to amend.
A batch of checks run as a single shell invocation has neither.
There is no `set -e`, no `set -o pipefail`, and no file to add either one to,
so the `&&` between the stages is the entire error handling.
Piping a stage then collapses the chain's verdict onto the pipeline's last
command: without `pipefail` the `&&` sees only that final status, so a failure
in an earlier stage is masked whenever the last stage --- typically a formatter
like `tail` --- succeeds, and every later check runs as though the piped one
had passed.

The symptom differs from the `||` case in a way worth seeing.
There the fallback is unreachable, so nothing happens that should have.
Here the chain runs to completion and reports success, which is a stronger and
more misleading claim than silence.
Measured on bash 3.2.57:

```bash
$ bash -c 'false | tail -1 && echo "CHAIN CONTINUED"; echo "rc=$?"'
CHAIN CONTINUED
rc=0
$ bash -c 'set -o pipefail; false | tail -1 && echo "CHAIN CONTINUED"; echo "rc=$?"'
rc=1
```

The trigger is worth naming, because nobody arrives at it by reasoning about
error handling.
A check prints more output than you want to read, so you pipe it through
`tail` to shorten it.
At that moment the pipe is a formatting decision about the output, and the
exit status is not in view at all, which for a verification check is the one
thing that mattered.
So the anti-pattern the bullets above name, tidying output when the status is
the point, is reached precisely when the status is least visible.

- **Do:** open an ad-hoc chain with `set -o pipefail;` when every stage's
  non-zero exit is a genuine failure.
  Where a stage legitimately exits early --- a producer piped to `head`, which
  `SIGPIPE`s the producer once `head` has read enough --- `pipefail` turns that
  into a false failure, so there prefer the split-command remedy in the next
  bullet over blanket `pipefail`.
- **Do:** run a check whose output needs trimming as its own command, and read
  its status, rather than folding it into a chain.
- **Don't:** read "set `pipefail` in any script" as inapplicable because there
  is no script; the same word works at the front of a one-off command line.
- **Don't:** pipe a verification check into `tail` or `head` for readability
  while its exit status is still gating what runs next.

(2026-08-03, preparing a push in `Morrison-Lab/ai-config`: a pre-push check
set was run as one `&&` chain, with `npx markdownlint-cli2 ... | tail -N`
among the stages and no `set` line anywhere.
markdownlint reported a real MD018 failure, `tail` exited 0, and the chain
continued through the remaining checks and reported them all passing.
The failure surfaced only on a later run that did not pipe.)

## An explicit `exit` escapes the capture group

The capture idioms above (`|| rc=$?` on a region, a status consumed by an
`if`) catch **failing commands**, and an explicit `exit` is not one.
`{ ...; exit 2; } || rc=$?` in ordinary statement position terminates the
whole shell at the `exit`.
Braces are not a subshell --- `{ }` runs in the caller's own shell, so no
surrounding command fails and there is no status for the `||` to see.
A parenthesized `( exit 2 )` is a different animal: it forks, so its exit
becomes a catchable status.
The same rescue applies wherever bash already forks around the group ---
command substitution, either side of a pipeline, backgrounding under
`wait` --- which is why the absolute claim stays scoped to statement
position.

The shape to watch for is a validation guard inside a captured region
whose non-zero exit is meant to become a classified, reported failure.
With `exit`, the shell dies before the summary lines run, whatever
consumes the captured output sees nothing, and under a
continue-on-error-style wrapper the job can go green with no verdict at
all.
Express the guard as data instead: assign the code (`rc=2`) or set a flag
inside an `if`, and let ordinary flow carry it to the capture boundary.

- **Do:** express an intended early failure inside a captured region as an
  assigned code or flag that ordinary flow carries to the boundary, and
  keep every path's summary writes reachable after it.
- **Don't:** write a plain `exit` inside a braced capture region and read
  the trailing `|| rc=$?` as covering it --- statement position gives that
  pair nothing to catch.

Measured 2026-08-24 in Morrison-Lab/gha#603: the offline suite caught the
escaped exit within one run --- expected `exitcode=2`, got no line ---
which is the same offline-suite payoff this file argues for above.

## Process substitution does not propagate a status, so `set -e` never fires

The rules above are about a status that is *reported* and misread.
This is the case where no status is reported at all.

`mapfile -t ARR < <(cmd)` runs `cmd` in a process substitution, whose exit
status is not the status of the redirection and is not checked by `mapfile`.
So `set -e` sees a successful `mapfile`, and a failing `cmd` reaches nobody.
A command substitution in an assignment does propagate:

```bash
V="$(bash fail.sh)"                 # set -e ABORTS here
mapfile -t A < <(bash fail.sh)      # set -e does NOT; A is empty, rc is 0
```

Measured on bash 5.3.15 (`REACHED, n=0` for the second form).

The reason to care is what the empty array does next, which is where this
stops being a curiosity.
A helper that fails **closed** --- refusing rather than printing an empty list,
precisely so a caller cannot examine nothing --- has its refusal discarded by
this construct.
The array is empty, and `grep PATTERN "${ARR[@]}"` with no file arguments falls
through to reading **stdin**, which in a CI step is an immediate EOF.
The audit passes, having examined nothing.
That is the pass-path-equals-failure-path shape
[`fail-fast`](../principles/fail-fast.md) names, arriving through the one
construct added to make the check robust.

The tell is that process substitution is what everyone reaches for when
feeding `mapfile`, because it reads as the direct form and avoids a variable.
The safe form is the indirect one.

- **Do:** assign first (`OUT="$(cmd)"`) and feed `mapfile` from a here-string,
  so `set -e` sees the failure.
- **Do:** ask what an empty array does at every use site, since that is the
  state a swallowed failure produces.
- **Don't:** read `set -euo pipefail` at the top of a script as covering
  `< <(...)` --- `pipefail` governs pipelines, and this is not one.
- **Don't:** rely on a helper's fail-closed guard while calling it through a
  construct that discards its status.

(`Morrison-Lab/gha#719`, 2026-08-28.
Two workflow audits were rewritten to take their file list from a helper that
refuses an empty directory.
Both called it through `< <(...)`, so the refusal was inert; the shape was
caught in review before it shipped, and the empty-array consequence was
reproduced directly rather than reasoned about.)

## A `trap ... EXIT` installed inside a function fires when a SUBSHELL exits

`errexit` is the file's subject, and it is one instance of a wider property: a construct you read as "the script" is frequently two shells, and the second one has its own lifetime.
A cleanup trap is the case where that costs you data rather than a status.

A function that installs its own `trap ... EXIT` is installing it in whatever shell is running the function.
Call the function normally and that is the script's shell, so the trap fires at script exit, which is what you wanted.
Capture the function in a command substitution and it runs in a subshell --- so the subshell's exit, one line into the script, fires the cleanup:

```bash
set -euo pipefail
f=$(mktemp); echo hi > "$f"
gather() { trap 'rm -f "$f"' EXIT; echo out; }
out=$(gather)      # subshell exits here -- the trap runs
cat "$f"           # gone
```

Note which case does *not* bite, because assuming the wrong one sends the diagnosis somewhere unproductive.
A trap installed in the parent **before** the substitution is reset to default in the subshell and does not fire, and neither an `exit` inside the substituted function nor a failing command in it reaches a parent-installed trap.
Only a trap installed *within* the subshell fires there.
So the shape to look for is a self-cleaning helper, not a script-level cleanup.

The failure presents far from its cause.
Nothing errors at the substitution;
the next several readers of the file get empty input, and each reports its own unrelated-looking failure.

Guard the trap on the shell it was meant for:

```bash
gather() { trap '[[ $BASHPID == $$ ]] && rm -f "$f"' EXIT; echo out; }
```

`$$` is the script's PID and stays fixed across subshells, while `BASHPID` is the current shell's, so the comparison is false in every subshell and true only in the shell that installed the trap.

- **Do:** guard a function-installed `EXIT` trap with `[[ $BASHPID == $$ ]]` when the function may be called in a command substitution.
- **Do:** install cleanup at the script's top level, where its lifetime is unambiguous, when nothing requires it to be per-function.
- **Don't:** conclude a temp file was never written when several consumers report empty input --- check whether anything between the write and the read ran in a subshell.
- **Don't:** assume a parent's trap is the one that fired;
  the subshell resets inherited traps, so the culprit is a trap set inside it.

(Measured 2026-09-03, bash 5.3.15: `out=$(run_gather ...)` deleted the temp file the next line read, and five downstream checks failed with empty input.
Reproduced and both forms confirmed on the same shell --- the naive form deletes, the `BASHPID`-guarded form survives the substitution and still cleans up at script exit.)

## In review

Flag a pipeline or command under `set -e` whose left-hand side routinely
exits non-zero on a legitimate input, where the tolerance is not stated.
Flag `|| fallback` attached to a pipeline in a script without `pipefail`, and
a piped command whose status the script goes on to rely on.
Flag a piped stage inside an `&&` chain that carries no `pipefail`, including
in a one-off command line rather than a committed script, since there the
`&&` is the only thing sequencing failure at all.
Flag it even when every current call site masks it: the finding is that the
behaviour is call-site dependent, not that it misbehaves today.

Flag an `if` or `!` that branches on a command which might not be installed,
too.
That one has to be asked for separately, and not because the check above
returns the wrong answer.
It returns the right one: `grep -q` really does exit non-zero on legitimate
input, since a no-match is exactly that.
What lets the guard through is the rest of that check --- the tolerance *is*
stated, because an `if` or a `!` is itself the statement that a non-zero exit
is expected and handled.
So the existing check passes cleanly while the missing-command case stays
hidden, and it needs a question of its own.
Ask what the branch does when the command cannot run at all.
