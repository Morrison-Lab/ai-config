# Debugging: case records

Worked examples moved out of [`debugging.md`](debugging.md), which sits against a 1250-line gate that CI enforces with `--strict`.
The rules themselves stay there; each record here leaves a pointer behind.

Write every cross-reference by name, never by position --- a record here and the entry it belongs to sit in different files, so "above" and "below" are false the moment either moves, and they stay present while becoming false.

## A GNU-only grep flag in an `xargs` child

Belongs to [`debugging.md`](debugging.md)'s "A second route into this section's failure" entry, under the `grep -P` locale section.

Measured 2026-09-10 during a `Morrison-Lab/qwt` CI fix, against `grep (BSD grep, GNU compatible) 2.6.0-FreeBSD` on macOS.

### Which flags BSD grep actually rejects

Two, not the seven a first draft of the guard claimed:

```
-P                 rc=2  grep: invalid option -- P
--perl-regexp      rc=2  grep: unrecognized option `--perl-regexp'
-z                 rc=0  (documented in its own man page)
--null-data        rc=0
--include=*.md     rc=0
--exclude=*.txt    rc=0
--exclude-dir=sub  rc=0
```

The two rejections print *different* stderr lines, so a guard quoting one of them for both misreports the long form.
`/usr/bin/egrep -lP` and `/usr/bin/fgrep -lP` also print `invalid option -- P`; `ggrep` is GNU grep, where `-P` works.

That first draft generalized from the one flag that had been tested, which would have made the guard assert "BSD grep rejects `--include`" over a correct command --- the same unmeasured-claim error as the false zero it exists to catch.

### The exit-code laundering

```
/usr/bin/grep -lP x a.md                      rc=2
printf 'a.md' | xargs -0 /usr/bin/grep -lP x  rc=1
printf 'a.md' | xargs -0 /usr/bin/grep -l ZZZ rc=1   (honest no-match)
```

The second and third are indistinguishable, which is the whole defect.

[`batch-merge-and-resolve`](../shared/workflow/batch-merge-and-resolve.md)'s negative-control section makes the same point for a different detector: a zero matrix and a detector that never ran look alike, so report the population examined rather than only the hits.

### What the false zero cost

Five tracked files contained an em dash.
The scan reported none, the claim went into a commit message, and an adversarial reviewer caught it.
The replacement scan reports `examined 79 of 82 tracked files` alongside the hit count, the other three being two binaries and a submodule, so a zero now carries evidence the scan ran.

### The guard

[`hooks/flag-indirect-gnu-grep-flag.py`](../hooks/flag-indirect-gnu-grep-flag.py) warns when one of the two rejected flags reaches a `grep` that an indirection actually runs.
It pairs the indirection with its utility rather than checking for each independently, because `xargs -0 python3 script.py grep -P f` runs `python3` and never invokes grep.
It is a heuristic and says so: `xargs -n 4 grep -P` leaves the value in the utility slot and is missed, a false negative, which is the safe direction for a guard that only adds context.
