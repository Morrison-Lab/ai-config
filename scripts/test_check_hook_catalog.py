#!/usr/bin/env python3
"""Regression tests for check-hook-catalog.py.

Every case runs the real script as a subprocess against a scratch repo, so the
control enters at the same entry point CI uses rather than at an internal
function that is already trusted.

The cases that matter most are the negative ones: a check nobody has watched
fail is a guess about what it covers. Each drift shape the script claims to
catch gets a case here that exits non-zero, and the "vacuous parse" pair covers
the way this particular check could silently pass forever -- a README whose
table shape changed would otherwise make every set comparison compare nothing.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-hook-catalog.py"
ROOT = Path(__file__).parent.parent

# Mirrors KNOWN_UNREGISTERED in the script under test. Fixtures must account
# for these two, since the script fails an allowlisted hook that has no README
# row -- so a "clean" fixture has to document them.
ALLOWLISTED = ["no-handrolled-verdict-parse.py", "remind-brief-premises.py"]

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def hooks_json(entries):
    """entries: list of (script, event, matcher). Returns JSON text."""
    events = {}
    for script, event, matcher in entries:
        events.setdefault(event, {}).setdefault(matcher, []).append(script)
    groups = {}
    for event, by_matcher in events.items():
        out = []
        for matcher, scripts in by_matcher.items():
            group = {"hooks": [{"type": "command", "script": s} for s in scripts]}
            if matcher:
                group["matcher"] = matcher
            out.append(group)
        groups[event] = out
    import json
    return json.dumps({"hooks": groups}, indent=2)


def readme(rows, heading="## Enforcement hooks (`hooks/`)"):
    """rows: list of (script, event, matcher, rest). Returns README text."""
    body = [
        "# Title", "", "## Something else", "", "prose", "", heading, "",
        "| hook | event | enforces |", "|---|---|---|",
    ]
    for script, event, matcher, rest in rows:
        ev = f"`{event}`" + (f" ({matcher})" if matcher else "")
        body.append(f"| `{script}` | {ev} | {rest} |")
    body += ["", "trailing prose", "", "## After", "", "more"]
    return "\n".join(body) + "\n"


def make_repo(tmpdir, entries, rows, heading=None):
    root = Path(tmpdir)
    (root / "scripts").mkdir()
    (root / "hooks").mkdir()
    (root / "scripts" / "check-hook-catalog.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "hooks" / "hooks.json").write_text(
        hooks_json(entries), encoding="utf-8")
    kwargs = {"heading": heading} if heading else {}
    (root / "README.md").write_text(readme(rows, **kwargs), encoding="utf-8")
    return root


def run(root):
    proc = subprocess.run(
        [sys.executable, str(Path(root) / "scripts" / "check-hook-catalog.py")],
        capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


# The two allowlisted hooks, documented with the required marker. Every fixture
# starts from these so the allowlist checks are satisfied by default.
ALLOW_ROWS = [(s, "PreToolUse", "Bash", "**not registered ([#1505](u))** --- would block")
              for s in ALLOWLISTED]


def case(name, entries, rows, want_fail, needle=None, heading=None):
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(td, entries, rows, heading)
        rc, out = run(root)
    ok = (rc != 0) if want_fail else (rc == 0)
    if ok and needle:
        ok = needle in out
    check(name, ok)
    if not ok:
        print(f"      rc={rc} needle={needle!r}\n{out}")


# --- the clean baseline: sets match, events match -------------------------
case("clean catalog passes",
     [("a.py", "Stop", ""), ("b.py", "PreToolUse", "Bash")],
     [("a.py", "Stop", "", "blocks x"),
      ("b.py", "PreToolUse", "Bash", "blocks y")] + ALLOW_ROWS,
     want_fail=False)

# --- the two drift directions from ai-config#1206 -------------------------
case("registered but undocumented fails",
     [("a.py", "Stop", ""), ("b.py", "PreToolUse", "Bash")],
     [("a.py", "Stop", "", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="b.py is registered")

case("documented but unregistered fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x"),
      ("c.py", "Stop", "", "blocks z")] + ALLOW_ROWS,
     want_fail=True, needle="never fires")

# --- the event/matcher direction, which a set comparison cannot see -------
case("event mismatch fails",
     [("a.py", "Stop", "")],
     [("a.py", "UserPromptSubmit", "", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="README says UserPromptSubmit")

case("matcher mismatch fails",
     [("a.py", "PreToolUse", "Bash")],
     [("a.py", "PreToolUse", "Agent", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="hooks.json binds PreToolUse (Bash)")

# --- allowlist hygiene, mirroring KNOWN_UNTESTED's reverse check ----------
case("allowlisted row without the marker fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x"),
      (ALLOWLISTED[0], "PreToolUse", "Bash", "blocks a verdict parse"),
      (ALLOWLISTED[1], "PreToolUse", "Agent", "**not registered** --- reminds")],
     want_fail=True, needle="reads as an active guard")

case("allowlisted hook that is now registered fails",
     [("a.py", "Stop", ""), (ALLOWLISTED[0], "PreToolUse", "Bash")],
     [("a.py", "Stop", "", "blocks x"),
      (ALLOWLISTED[0], "PreToolUse", "Bash", "blocks a verdict parse"),
      ALLOW_ROWS[1]],
     want_fail=True, needle="drop it from KNOWN_UNREGISTERED")

case("allowlisted hook with no README row fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x"), ALLOW_ROWS[1]],
     want_fail=True, needle="has no README row")

# --- fail-fast: a parse that finds nothing must not pass vacuously --------
case("missing section fails loudly",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="cannot run", heading="## Some Other Heading")

with tempfile.TemporaryDirectory() as td:
    root = make_repo(td, [("a.py", "Stop", "")], ALLOW_ROWS)
    # Strip every table row, leaving the section heading in place. The set
    # comparison would then compare against nothing and report clean.
    p = root / "README.md"
    kept = [ln for ln in p.read_text(encoding="utf-8").splitlines()
            if not ln.startswith("| `")]
    p.write_text("\n".join(kept) + "\n", encoding="utf-8")
    rc, out = run(root)
    check("empty table fails loudly rather than passing vacuously",
          rc != 0 and "parsed 0 hook rows" in out)

# --- the live corpus: a holding-constant regression guard -----------------
proc = subprocess.run([sys.executable, str(SCRIPT)],
                      capture_output=True, text=True, cwd=str(ROOT))
check("the real repo's catalog is consistent", proc.returncode == 0)
if proc.returncode != 0:
    print(proc.stdout + proc.stderr)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
