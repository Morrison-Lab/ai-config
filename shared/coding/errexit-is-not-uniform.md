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

## In review

Flag a pipeline or command under `set -e` whose left-hand side routinely
exits non-zero on a legitimate input, where the tolerance is not stated.
Flag it even when every current call site masks it: the finding is that the
behaviour is call-site dependent, not that it misbehaves today.
