# Python and CPython runtime behavior

Cross-project notes on Python-the-language and CPython-the-implementation:
compiled-code introspection, platform-divergent stdlib behavior, and the
measurements that settled each.

## A literal inside a collection display can be invisible to a top-level `co_consts` probe

`assert "gh" not in fn.__code__.co_consts` reads like a guard against the
literal `"gh"` reappearing in `fn`, and it is vacuous whenever the literal
sits inside a collection display that CPython's compiler constant-folds:
the display becomes a single nested constant, the string lives one level
down --- `co_consts` is `(None, ('gh', 'search', ...))` --- and top-level
membership never sees it, so the assertion passes on exactly the reverted
code it exists to catch.
A green check that measures nothing is worse than no check, because it
attests coverage that does not exist.

The folding is shape- and threshold-dependent, so probe it rather than
assuming either way (measured on CPython 3.13.7: a 2-element list display
was left unfolded and the top-level probe saw its elements; 3-element and
longer lists folded; tuple displays folded at every length; an `in {...}`
membership set folded to a `frozenset` constant; nested displays folded
into tuples of tuples, two levels down).

Search the constant tree recursively, not one level:

```python
def constant_literals(consts):
    for const in consts:
        if isinstance(const, (tuple, list, set, frozenset)):
            yield from constant_literals(const)
        else:
            yield const

assert "gh" not in set(constant_literals(fn.__code__.co_consts))
```

(A function whose body defines nested functions or comprehensions carries
their code objects in `co_consts` too; extend the walk into
`const.co_consts` when guarding one of those.)
And negative-control the guard: compile a simulation of the revert and
confirm the assertion fails on it, since this failure mode is precisely a
guard that cannot fail.

- **Do:** walk nested collection consts recursively when asserting a
  literal's absence from compiled code, and negative-control the guard
  against a compiled revert.
- **Do:** re-probe the folding threshold on the interpreter you target
  before relying on a shape claim --- it is an optimizer detail, not a
  language guarantee.
- **Don't:** assert membership on `co_consts` directly for a literal that
  would sit inside a collection display --- folding hides it at three
  elements on 3.13.7, and `{...}` membership sets hide it in a `frozenset`.

(Measured 2026-08-23, CPython 3.13.7, during ai-config#1976's review loop:
the top-level form passed on both the fixed code and a compiled revert
simulation; the adversarial reviewer caught that, and a second round caught
the one-level search missing the `frozenset` and two-level-tuple shapes.)

## `os.kill(pid, 0)` on Windows is `GenerateConsoleCtrlEvent`, not a liveness probe

On Windows, `signal.CTRL_C_EVENT == 0`, so `os.kill(pid, 0)` takes the
console-control branch of CPython's `os_kill_impl`: it calls
`GenerateConsoleCtrlEvent(CTRL_C_EVENT, pid)`, where `pid` names a process
**group**.
Every signal value other than `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` goes to
`OpenProcess` + `TerminateProcess` --- and the documentation's
"any other value for sig" sentence has always excluded 0, so the folk
belief that a signal-0 probe is lethal on Windows was wrong in both
directions: 0 was never routed to `TerminateProcess`, and what it does
instead is not a probe either.

Three measured consequences (2026-08-23, Windows 11, CPython 3.13.7):

- Against the caller's own `subprocess` child: the call returned without
  error and the child survived, so in that topology it walks and quacks
  like the POSIX probe.
- Against a live unrelated process (`explorer.exe`): `OSError`
  (WinError 87), byte-identical to what a dead pid raises --- so read as a
  probe, it reports a live process as gone.
- Success keys on console/process-group reachability, and a reachable
  group actually receives a CTRL_C --- the call is not side-effect-free,
  and `os.kill(0, 0)` (the POSIX self-group probe) would signal the
  caller's own console group.

So the POSIX idiom (probe with signal 0, treat `OSError` as gone) is
POSIX-only.
The one Windows context that tolerates it is a wait-for-death loop over a
process you have already signalled to die: there a false "gone" only ends
the wait early, and a delivered CTRL_C lands on a process you are killing
anyway.
For a real Windows liveness check, ask the process API
(`OpenProcess`/`GetExitCodeProcess` via `ctypes`, or `psutil.pid_exists`).

Two POSIX caveats for wait-for-death loops keyed on the probe: it succeeds
on a zombie (an unreaped child) until the reap, and on Windows it succeeds
on a terminated child while any handle stays open (a `subprocess.Popen`
object holds one) --- so in test topologies a dead child often stays
"observable" and the loop times out rather than confirming the death.
Give the timeout its own observable outcome, per
[`fail-fast`](../shared/principles/fail-fast.md).

- **Do:** treat `os.kill(pid, 0)` as a liveness probe on POSIX only, and
  use a process-API check for liveness on Windows.
- **Do:** record both halves of the correction: the retired belief was
  "Windows `os.kill` routes signal 0 to `TerminateProcess`"; the
  replacement is "signal 0 IS `CTRL_C_EVENT`, routed to
  `GenerateConsoleCtrlEvent`, which conflates dead with unreachable and
  can deliver a real signal".
- **Don't:** generalize a probe that behaved on your own subprocess
  children to arbitrary pids --- the reachability semantics are what you
  measured, not existence.
- **Don't:** treat a succeeding probe as proof of a live process anywhere
  --- zombies and open-handle corpses both pass it.
