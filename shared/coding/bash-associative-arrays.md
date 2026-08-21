# Bash associative arrays: an empty subscript is fatal, not a miss

`${arr["$key"]:-}` is the idiom for "look this up, tolerate absence".
It tolerates a **missing** key.
It does not tolerate an **empty** one.

```bash
declare -A m=([a]=1)
key=""
echo "${m["$key"]:-fallback}"   # bad array subscript -- fatal, not "fallback"
```

Under `set -euo pipefail` that aborts the script with a bash-internal
diagnostic naming a line number, which reads as a crash in the surrounding
logic rather than as a rejected input.

The consequence for control flow is the part worth remembering:
**the `:-` default cannot guard this, because the expansion never completes.**
A validator built around `[ -z "${m["$k"]:-}" ] && reject` therefore looks
airtight and dies on exactly the input it exists to reject.
Test the key before the lookup:

```bash
if [ -z "$key" ] || [ -z "${m["$key"]:-}" ]; then
  reject "$key"
fi
```

`||` short-circuits, so the empty-key branch returns before the expansion is
ever attempted.
Ordering the two tests the other way round reintroduces the crash.

An empty key is likelier than it looks whenever the key is **derived** rather
than supplied --- `"${stem##*.}"` over a filename, a `cut` field, a regex
capture.
Each yields the empty string on a shape the author did not picture, and that
shape is usually the malformed input the validator was written for.

- **Do:** test a derived key for emptiness before using it as a subscript.
- **Do:** put the emptiness test first in an `||` chain, so short-circuiting
  prevents the expansion.
- **Don't:** read `${arr[$k]:-}` as a total function; it is defined on missing
  keys and undefined on empty ones.
- **Don't:** diagnose `bad array subscript` as a bug in the line it names --
  it names the lookup, and the defect is wherever the key was derived.

(Measured 2026-08-21 on
[Morrison-Lab/gha#563](https://github.com/Morrison-Lab/gha/pull/563).
A changelog-fragment validator derived each file's category as
`"${stem##*.}"` and rejected any category outside a configured map.
A fragment named `slug..md` yields an empty category, so the validator died
with `assemble-news.sh: line 123: heading_for: bad array subscript` instead of
reporting the file.
Caught in review; fixed by testing the key first.)
