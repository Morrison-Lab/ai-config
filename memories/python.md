# Python and CPython runtime behavior

Cross-project notes on Python-the-language and CPython-the-implementation:
compiled-code introspection, platform-divergent stdlib behavior, and the
measurements that settled each.

## A literal inside a list/tuple display is invisible to a top-level `co_consts` probe

`assert "gh" not in fn.__code__.co_consts` reads like a guard against the
literal `"gh"` reappearing in `fn`, and it is vacuous for the commonest way
the literal appears: inside a list or tuple display
(`["gh", "search", ...]`), which CPython's compiler folds into a single
nested tuple constant.
The string then lives one level down --- `co_consts` is
`(None, ('gh', 'search', ...))` --- and top-level membership never sees it,
so the assertion passes on exactly the reverted code it exists to catch.
A green check that measures nothing is worse than no check, because it
attests coverage that does not exist.

Search nested collection consts as well:

```python
assert not any(
    value == "gh"
    for const in fn.__code__.co_consts
    for value in (const if isinstance(const, (tuple, list)) else (const,)))
```

(Wrapping the non-collection case in a one-tuple avoids iterating a string's
characters.)
And negative-control the guard: compile a simulation of the revert and
confirm the assertion fails on it, since this failure mode is precisely a
guard that cannot fail.

- **Do:** search nested tuple/list consts when asserting a literal's absence
  from compiled code, and negative-control the guard against a compiled
  revert.
- **Don't:** assert membership on `co_consts` directly for a literal that
  would sit inside a collection display --- constant folding hides it.

(Measured 2026-08-23 during ai-config#1976's review loop: the top-level form
passed on both the fixed code and a compiled revert simulation; the
adversarial reviewer caught it, and the nested search discriminated in both
directions.)

## `os.kill(pid, 0)` on Windows CPython 3.13 is a liveness probe, not a kill

Old lore (and older documentation) says `os.kill` on Windows routes any
signal other than `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` to `TerminateProcess`,
which would make a signal-0 liveness probe lethal.
Measured 2026-08-23 on Windows 11, CPython 3.13.7: `os.kill(pid, 0)` against
a live child returned without error and the child survived the probe.
So the POSIX idiom (probe with signal 0, treat `OSError` as "gone") works on
this platform and Python version.

The claim is version- and platform-scoped, so re-measure before relying on
it elsewhere; the probe is three lines:

```python
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
os.kill(p.pid, 0)
assert p.poll() is None  # survived the probe
```

Two adjacent facts from the same session, both POSIX-relevant: the probe
succeeds on a zombie (an unreaped child) until it is reaped, and on Windows
it succeeds on a terminated child while any handle to it stays open (a
`subprocess.Popen` object holds one) --- so in test topologies a dead child
often stays "observable" and a wait-for-death loop keyed on the probe times
out rather than confirming the death.
Design such a loop with a distinct timeout outcome, per
[`fail-fast`](../shared/principles/fail-fast.md).

- **Do:** measure the probe's semantics on the target platform and version
  before building a wait loop on it, and keep the measurement's date and
  version beside the claim.
- **Don't:** carry the Windows-`TerminateProcess` claim into a design without
  re-measuring --- on CPython 3.13 it is out of date for signal 0.
- **Don't:** treat a succeeding probe as proof of a live process --- zombies
  and open-handle corpses both pass it.
