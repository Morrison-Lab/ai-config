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
Piping any stage then removes that stage from the chain's verdict, and every
later check runs as though it had passed.

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

- **Do:** open an ad-hoc chain with `set -o pipefail;` whenever any stage in
  it is piped.
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
