# awk brace handling differs by implementation, in both directions

Split out of [`tools.md`](tools.md) (ai-config#694 pattern) at the 1250-line gate.

[`tools.md`](tools.md)'s "Two awk gotchas when an awk program is embedded in a single-quoted shell string" covers two gotchas met when writing an awk program into such a string.
Only the first of that pair is *caused* by the quoting;
its second, POSIX ERE having no backreferences, is a property of awk itself and reproduces from a program file.

This file is about which **implementation** the machine happens to provide: the same program text is accepted by one awk and rejected by another.

`mawk` is `awk` on Debian and Ubuntu, so a script that says `awk` gets it by default there, and it mishandles braces in two opposite ways:

- **A brace you meant literally is read as an interval.**
  `/\^{}$/` dies with `regular expression compile failed (bad interval expression)`.
  Bracket each brace (`\^[{][}]`) to make it a literal in every awk.
  [`memories/git-tags.md`](git-tags.md) records this one, in the tag-peeling one-liner that needed it.
- **An interval you meant as an interval can abort the process.**
  On `mawk 1.3.4 20240123`, the Ubuntu 24.04 build, `/^#{1,6}([ \t]|$)/` dies with `REcompile() - panic: values still on machine stack`:
  ```console
  $ echo '## heading' | mawk '{ if ($0 ~ /^#{1,6}([ \t]|$)/) print "M"; else print "NO-M" }'
  REcompile() - panic:  values still on machine stack for ^#{1,6}([ \t]|$)
  ```
  It prints **neither** branch.
  Bracketing does not help, because here the interval is the thing you want: avoid `{m,n}` outright, with `^#+([ \t]|$)` plus a length check on the run, or the unrolled `^##?#?#?#?#?([ \t]|$)`.

Three things about the pair.

**Neither error leads a reader to the other.**
[`memories/git-tags.md`](git-tags.md) records the first direction only, inside a tag-peeling one-liner and indexed by the literal-brace symptom that produced it --- it names neither the panic nor an interval you actually want.
So arriving with the panic finds nothing there, and arriving with the bad-interval error finds a note that stops at the first direction.
That is why both directions are written out here rather than cross-referenced.

**The second direction fails toward silence at the caller.** mawk dies rather than returning a verdict, so a script that pipes a body through the awk gets an empty stream and reports whatever its no-match branch says --- which for a matcher is `false` on every input.

**CI being green says nothing about it.**
Whichever awk GitHub's `ubuntu-latest` provides does not hit the panic, so a `{m,n}` can sit in a shipped script indefinitely while every run passes.
It surfaces only where `runs-on` is a consumer-settable input, or in a container.

(Morrison-Lab/gha#448, 2026-08-12, in `strip-non-invoking-markup.sh` again: the panic took `detect-review-request.sh`'s verdict with it, so its own suite reported `30 of 64 detect-review-request case(s) did not behave as expected` while `_selftest.yml` was green on `main`.)

- **Do:** assume `awk` is `mawk` in any program that ships to Debian or Ubuntu, and bracket every brace you mean literally (`\^[{][}]`).
- **Do:** express a bounded repetition without `{m,n}` --- `^#+([ \t]|$)` plus a length check on the run, or the unrolled `^##?#?#?#?#?([ \t]|$)` --- when the awk runs anywhere you do not control.
- **Don't:** reach for the bracketing remedy on an interval you meant as an interval;
  that is the fix for the opposite direction, and the two errors are filed apart.
- **Don't:** read a green `ubuntu-latest` run as evidence the awk is portable --- whatever awk that runner provides does not hit the panic, so the defect stays latent until a consumer sets `runs-on`.

