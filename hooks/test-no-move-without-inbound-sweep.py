#!/usr/bin/env python3
"""Tests for `no-move-without-inbound-sweep.py`.

Each case names the behaviour it pins rather than the input it feeds, so a
failure says what broke. The mutation checks at the bottom are the point of the
file: a test that passes against a deliberately broken guard is not testing the
guard, and this suite has one mutation per branch that matters.

**Runtime.** Expect tens of seconds, dominated almost entirely by the mutation
harness: it spawns one `python3 ... --against-mutant` subprocess per mutation,
and each re-executes this whole module. Nothing is shared between those
subprocesses --- `_DEEP_CACHE` starts empty in every one --- so the memoization
below saves only a repeated `deep_json()` call *within* a single process,
measured at roughly 110 ms. Recorded because a commit message once credited
that memoization with a 98-to-37-second speedup, comparing a figure measured on
one machine against a figure measured on another and attributing the difference
to the change between them. The mechanism cannot produce a saving of that size,
and the two commits run at the same speed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "no-move-without-inbound-sweep.py")

spec = importlib.util.spec_from_file_location("guard", TARGET)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

failures = []


def check(name, cond):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        failures.append(name)


_DEEP_CACHE = {}


def deep_json(payload='""'):
    """A JSON string nested deeply enough to raise `RecursionError`, verified.

    The depth cannot be hard-coded. `json` uses the C-accelerated scanner by
    default, which recurses on the C stack rather than the Python one, so
    `sys.setrecursionlimit` does not move the threshold and the threshold is a
    property of the platform's stack: measured at roughly 116,000 levels here,
    against a `sys.getrecursionlimit()` of 1000.

    An earlier version of these fixtures hard-coded 998 levels, on the
    assumption that the Python recursion limit governed. It does not, so those
    fixtures parsed cleanly and never entered the branch they claimed to pin ---
    indistinguishable from a passing test.

    Raising rather than returning `None` is deliberate, and it is the second
    fix this defect needed. The first returned `None` and left each call site
    to check it, which is a precondition three places must remember: two of
    them did not, so on a platform where no depth in range raises, those checks
    would have skipped silently --- the same unreached-branch failure one level
    up. A single raise cannot be forgotten at a call site.
    """
    if payload in _DEEP_CACHE:
        return _DEEP_CACHE[payload]
    n = 200_000
    for _ in range(5):
        text = "[" * n + payload + "]" * n
        try:
            json.loads(text)
        except RecursionError:
            _DEEP_CACHE[payload] = text
            return text
        n *= 2
    raise AssertionError(
        "no depth up to 3.2M levels raised RecursionError on this platform, "
        "so the RecursionError fixtures cannot pin what they claim; "
        "widen the search or reconsider whether the catch is reachable here")


# --------------------------------------------------------------------------
# `is_commit`
# --------------------------------------------------------------------------

def test_is_commit():
    print("is_commit")
    check("a plain commit is one", guard.is_commit("git commit -m x"))
    check("a commit with a global flag is one",
          guard.is_commit("git -C /repo commit -F msg.txt"))
    check("a commit chained after another command is one",
          guard.is_commit("git add -u && git commit --quiet"))
    check("a commit after a semicolon is one",
          guard.is_commit("cd /repo; git commit -F f"))
    check("git status is not one", not guard.is_commit("git status --short"))
    check("git log is not one", not guard.is_commit("git log --oneline -3"))
    # The words appearing inside an unrelated argument must not match. This is
    # the case a substring search gets wrong.
    check("the words inside a quoted argument are not one",
          not guard.is_commit("echo 'run git commit later'"))


# --------------------------------------------------------------------------
# `significant`
# --------------------------------------------------------------------------

def test_significant():
    print("significant")
    check("prose counts", guard.significant("+The reader who follows one lands."))
    check("a blank line does not", not guard.significant("+   "))
    check("a fence does not", not guard.significant("+```bash"))
    check("a bare Do label does not", not guard.significant("+- **Do:**"))
    check("a table rule does not", not guard.significant("+|---|---|"))
    check("a Do label WITH content counts",
          guard.significant("+- **Do:** enumerate the inbound links first."))


# --------------------------------------------------------------------------
# `moves`
# --------------------------------------------------------------------------

def _diff(src, dst, lines, *, rename=False):
    """A staged diff moving `lines` from `src` to `dst`."""
    minus = "\n".join("-" + l for l in lines)
    plus = "\n".join("+" + l for l in lines)
    # Real git names both sides; the guard collects only the source, so a
    # test that pins the source check must not also mark the destination.
    rn = f"rename from {src}\nrename to {src}.moved\n" if rename else ""
    return (
        f"diff --git a/{src} b/{src}\n{rn}--- a/{src}\n+++ b/{src}\n"
        f"@@ -1,{len(lines)} +1,0 @@\n{minus}\n"
        f"diff --git a/{dst} b/{dst}\n--- /dev/null\n+++ b/{dst}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n{plus}\n"
    )


BIG = [f"sentence number {i} of the moved block." for i in range(20)]


def test_moves():
    print("moves")
    found = list(guard.moves(_diff("memories/a.md", "memories/b.md", BIG)))
    check("a 20-line cross-file move is reported", len(found) == 1)
    if found:
        src, dst, n = found[0]
        check("it names the source", src == "memories/a.md")
        check("it names the destination", dst == "memories/b.md")
        check("it counts the moved lines", n == 20)

    small = BIG[:guard.MIN_MOVED_LINES - 1]
    check("a move under the threshold is not reported",
          not list(guard.moves(_diff("a.md", "b.md", small))))

    check("a pure rename is not reported",
          not list(guard.moves(_diff("a.md", "b.md", BIG, rename=True))))

    # Two files that merely share boilerplate must not register.
    boiler = ["- **Do:**", "```", "|---|---|", "   "] * 8
    check("shared boilerplate alone is not a move",
          not list(guard.moves(_diff("a.md", "b.md", boiler))))

    # Deletion with no destination is not a move.
    only_del = (f"diff --git a/a.md b/a.md\n--- a/a.md\n+++ b/a.md\n"
                f"@@ -1,20 +1,0 @@\n" + "\n".join("-" + l for l in BIG) + "\n")
    check("a deletion with no destination is not a move",
          not list(guard.moves(only_del)))

    # A rename carrying edits prints `--- a/OLD` against `+++ b/NEW`, so a
    # parser keyed on the `+++` side credits removals to a path that did not
    # exist before the commit. Found by adversarial review, round 2.
    split_rename = (
        "diff --git a/a.md b/c.md\n"
        "similarity index 90%\n"
        "rename from a.md\nrename to c.md\n"
        "--- a/a.md\n+++ b/c.md\n@@ -1,20 +1,1 @@\n"
        + "\n".join("-" + l for l in BIG) + "\n+NEW HEADER LINE FOR THE RENAMED FILE\n"
        "diff --git a/b.md b/b.md\n--- /dev/null\n+++ b/b.md\n"
        "@@ -0,0 +1,20 @@\n" + "\n".join("+" + l for l in BIG) + "\n"
    )
    got = list(guard.moves(split_rename))
    check("a modified rename does not report its DESTINATION as the source",
          all(src != "c.md" for src, _, _ in got))
    check("a modified rename is exempted by its source name",
          not got)

    # Detection is prose-scoped: the warning's rationale and its remediation
    # command are both about prose citation, so a code refactor must not get
    # them.
    check("a .py to .py move is not reported",
          not list(guard.moves(_diff("hooks/a.py", "hooks/b.py", BIG))))
    check("a .md to .md move is reported",
          len(list(guard.moves(_diff("a.md", "b.md", BIG)))) == 1)
    check("a .qmd source is reported",
          len(list(guard.moves(_diff("a.qmd", "b.md", BIG)))) == 1)

    # An edit within ONE file must not count as moving to itself.
    same = (f"diff --git a/a.md b/a.md\n--- a/a.md\n+++ b/a.md\n@@ -1,20 +1,20 @@\n"
            + "\n".join("-" + l for l in BIG) + "\n"
            + "\n".join("+" + l for l in BIG) + "\n")
    check("a within-file rewrite is not a move",
          not list(guard.moves(same)))


# --------------------------------------------------------------------------
# `swept`
# --------------------------------------------------------------------------

def _transcript(commands):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for c in commands:
            fh.write(json.dumps({
                "message": {"content": [
                    {"name": "Bash", "input": {"command": c}}]}}) + "\n")
    return path


def test_swept():
    print("swept")
    p = _transcript(["grep -rn 'preferences.md' --include='*.md' ."])
    check("a repo-wide grep counts", guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["git grep -n 'preferences.md' -- '*.md'"])
    check("git grep counts", guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["rg 'preferences.md' --glob '*.md'"])
    check("rg counts", guard.swept(p, "preferences.md"))
    os.unlink(p)

    # Reading one file is not an enumeration of who links to it. This is the
    # distinction the guard exists to draw.
    p = _transcript(["grep -n 'worktree' memories/preferences.md"])
    check("grepping INSIDE the source file does not count",
          not guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["grep -rn 'something-else' --include='*.md' ."])
    check("a repo-wide grep for a DIFFERENT name does not count",
          not guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["cat memories/preferences.md"])
    check("reading the file does not count", not guard.swept(p, "preferences.md"))
    os.unlink(p)

    check("an unreadable transcript is treated as swept",
          guard.swept("/nonexistent/path.jsonl", "preferences.md"))

    # A malformed RECORD must not clear the whole transcript. Found by review:
    # `commands()` raised AttributeError on a truthy non-dict `message`, an
    # outer `except Exception` caught it, and the guard reported everything
    # swept when nothing had been searched. The record must MENTION the
    # basename, or the line filter short-circuits before `commands()` runs and
    # the probe exercises nothing -- which is how the first attempt at this
    # test passed against the broken code.
    fd, p2 = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"message": "mentions preferences.md as a string"}) + "\n")
    check("a non-dict message does not clear the transcript",
          not guard.swept(p2, "preferences.md"))
    os.unlink(p2)

    fd, p2 = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write("{not json at all, preferences.md}\n")
    check("an unparseable line does not clear the transcript",
          not guard.swept(p2, "preferences.md"))
    os.unlink(p2)

    # Every `.get()` target, not only the reported one. Narrowing the module's
    # blanket `except Exception` closed the `message` hole and exposed this
    # sibling in `input`, turning a silent fail-open into a crash.
    for label, blk in (("a list", [1, 2]),
                       ("a JSON string decoding to a list", "[1,2]"),
                       ("a number", 7)):
        rec = {"message": {"content": [{"name": "Bash", "input": blk}],
                           "_x": "preferences.md"}}
        try:
            got = guard.commands(rec)
            ok = got == []
        except Exception:
            ok = False
        check(f"a Bash block whose input is {label} does not crash", ok)

    check("a non-dict record yields no commands",
          guard.commands("not a dict") == [])

    # `RecursionError` is a `RuntimeError`, not a `ValueError`, so a catch
    # written for malformed JSON does not cover deeply nested JSON.
    deep = deep_json()
    rec = {"message": {"content": [{"name": "Bash", "input": deep}],
                       "_x": "preferences.md"}}
    try:
        ok = guard.commands(rec) == []
    except Exception:
        ok = False
    check("a deeply nested input string does not crash", ok)

    # A bad record must not hide a real sweep on a LATER line either.
    fd, p2 = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"message": "preferences.md as a string"}) + "\n")
        fh.write(json.dumps({"message": {"content": [
            {"name": "Bash", "input": {
                "command": "grep -rn 'preferences.md' --include='*.md' ."}}]}}) + "\n")
    check("a bad record does not hide a later real sweep",
          guard.swept(p2, "preferences.md"))
    os.unlink(p2)

    # The basename must appear as a LEAF, or the line filter short-circuits
    # before the parse and the probe exercises nothing.
    fd, p2 = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(deep_json('"preferences.md"') + "\n")
    try:
        ok = guard.swept(p2, "preferences.md") is False
    except Exception:
        ok = False
    check("a deeply nested transcript line does not crash", ok)
    os.unlink(p2)

    # Found by adversarial review of this guard: each of the four below was a
    # real defect in the first draft, in one direction or the other.
    p = _transcript(["grep --recursive 'preferences.md' ."])
    check("the LONG recursion flag counts", guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["grep -nr 'preferences.md' ."])
    check("a clustered short flag counts either way round",
          guard.swept(p, "preferences.md"))
    os.unlink(p)

    # `-report.md` is a filename, not a recursion flag.
    p = _transcript(["grep -n 'preferences.md' -report.md"])
    check("a dash-prefixed FILENAME is not a recursion flag",
          not guard.swept(p, "preferences.md"))
    os.unlink(p)

    # A sweep for a LONGER name must not clear a move out of a shorter one
    # whose basename is a suffix substring of it.
    p = _transcript(["grep -rn 'data.md' --include='*.md' ."])
    check("a sweep for data.md does not clear a move out of a.md",
          not guard.swept(p, "a.md"))
    os.unlink(p)

    p = _transcript(["grep -rn 'memories/preferences.md' --include='*.md' ."])
    check("a path-qualified sweep still names the file",
          guard.swept(p, "preferences.md"))
    os.unlink(p)

    # `git -C <path> grep` is the same pre-subcommand option shape `is_commit`
    # already handled. Found by adversarial review, round 2.
    p = _transcript(["git -C /repo grep -n 'preferences.md'"])
    check("git -C <path> grep counts", guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["git --git-dir=/repo/.git grep -n 'preferences.md'"])
    check("git --git-dir=... grep counts", guard.swept(p, "preferences.md"))
    os.unlink(p)

    p = _transcript(["git -C /repo log --oneline 'preferences.md'"])
    check("git -C <path> log is not a sweep",
          not guard.swept(p, "preferences.md"))
    os.unlink(p)


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------

def _run(payload, env=None):
    e = dict(os.environ)
    e.pop("ANTIGRAVITY_AGENT", None)
    e.update(env or {})
    out = subprocess.run(
        [sys.executable, TARGET], input=json.dumps(payload),
        capture_output=True, text=True, env=e, timeout=30)
    return out


def _repo_with_staged_move():
    """A real git repo with a staged cross-file move."""
    d = tempfile.mkdtemp()
    run = lambda *a: subprocess.run(a, cwd=d, capture_output=True, text=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    with open(os.path.join(d, "src.md"), "w") as fh:
        fh.write("\n".join(BIG) + "\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "base")
    os.unlink(os.path.join(d, "src.md"))
    with open(os.path.join(d, "src.md"), "w") as fh:
        fh.write("moved out\n")
    with open(os.path.join(d, "dst.md"), "w") as fh:
        fh.write("\n".join(BIG) + "\n")
    run("git", "add", "-A")
    return d


def test_end_to_end():
    print("end to end")
    d = _repo_with_staged_move()

    p = _transcript(["echo hello"])
    out = _run({"tool_name": "Bash", "cwd": d,
                "tool_input": {"command": "git commit -m x"},
                "transcript_path": p})
    check("exits 0 even when it fires", out.returncode == 0)
    check("warns on an unswept move", "inbound-link sweep" in out.stdout)
    check("names the source file", "src.md" in out.stdout)
    check("prints the deriving command", "grep -rn 'src.md'" in out.stdout)
    # It must never take the permission decision away from the user.
    check("never emits an allow decision",
          "permissionDecision" not in out.stdout)
    os.unlink(p)

    p = _transcript(["grep -rn 'src.md' --include='*.md' ."])
    out = _run({"tool_name": "Bash", "cwd": d,
                "tool_input": {"command": "git commit -m x"},
                "transcript_path": p})
    check("silent when the sweep ran", out.stdout.strip() == "")
    os.unlink(p)

    p = _transcript(["echo hello"])
    out = _run({"tool_name": "Bash", "cwd": d,
                "tool_input": {"command": "git status"},
                "transcript_path": p})
    check("silent on a non-commit command", out.stdout.strip() == "")

    out = _run({"tool_name": "Read", "cwd": d,
                "tool_input": {"path": "x"}, "transcript_path": p})
    check("silent on a non-Bash tool", out.stdout.strip() == "")

    out = _run({"tool_name": "Bash", "cwd": d,
                "tool_input": {"command": "git commit -m x"},
                "transcript_path": p}, env={"ANTIGRAVITY_AGENT": "1"})
    check("no systemMessage under ANTIGRAVITY_AGENT",
          "systemMessage" not in out.stdout)
    os.unlink(p)

    out = _run({})
    check("silent on an empty payload", out.stdout.strip() == "")
    check("exits 0 on an empty payload", out.returncode == 0)

    # Every field a payload carries is harness-shaped, and `json.load`
    # guarantees only the syntax. Four crash sites came from assuming types.
    for label, pay in (
            ("tool_input is a list",
             {"tool_name": "Bash", "tool_input": ["a", "list"]}),
            ("command is a list",
             {"tool_name": "Bash", "tool_input": {"command": ["a", "b"]}}),
            ("command is a number",
             {"tool_name": "Bash", "tool_input": {"command": 42}}),
            ("transcript_path is a list",
             {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
              "cwd": d, "transcript_path": ["not", "a", "string"]}),
            ("cwd is a list",
             {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
              "cwd": ["x"], "transcript_path": ""})):
        out = _run(pay)
        check(f"exits 0 when {label}", out.returncode == 0)

    e2 = dict(os.environ)
    e2.pop("ANTIGRAVITY_AGENT", None)
    out = subprocess.run([sys.executable, TARGET], input=deep_json(),
                         capture_output=True, text=True, env=e2, timeout=60)
    check("exits 0 on a deeply nested payload", out.returncode == 0)

    # A syntactically valid payload that is not an object.
    e = dict(os.environ)
    e.pop("ANTIGRAVITY_AGENT", None)
    out = subprocess.run([sys.executable, TARGET], input="[1,2,3]",
                         capture_output=True, text=True, env=e, timeout=30)
    check("exits 0 on a bare-list payload", out.returncode == 0)
    check("silent on a bare-list payload", out.stdout.strip() == "")


# --------------------------------------------------------------------------
# Mutation checks
#
# Each mutation breaks one branch of the guard. If the suite still passes with
# the mutation applied, the suite is not testing that branch.
# --------------------------------------------------------------------------

MUTATIONS = [
    ("threshold ignored", "if n >= MIN_MOVED_LINES:", "if n >= 0:"),
    ("renames not skipped", "if src in renamed:", "if False:"),
    ("self-move not excluded", "if dst == src:", "if False:"),
    ("sweep detection always true", "return False\n\n\ndef commands",
     "return True\n\n\ndef commands"),
    ("trivial lines counted", "return not TRIVIAL.match(body)", "return True"),
    ("fires on any command", "if not is_commit(command):", "if False:"),
    ("prose gating removed", "if not src.lower().endswith(PROSE_SUFFIXES):",
     "if False:"),
    ("basename matched as a bare substring",
     "return re.search(r\"(?:\\A|[^\\w.-])\" + re.escape(basename) + r\"(?:\\Z|[^\\w.-])\",\n"
     "                     word + \" \") is not None",
     "return True"),
    ("recursion not required", "if not recursive:\n            continue",
     "if False:\n            continue"),
    ("removals credited to the + side",
     'removed.setdefault(old_path, set()).add(line[1:])',
     'removed.setdefault(new_path, set()).add(line[1:])'),
    ("git pre-subcommand options not skipped",
     "    while i < len(words) and words[i].startswith(\"-\"):",
     "    while False:"),
    # Anchored with its following lines: the catch clause alone appears three
    # times now, so the anchor carries what makes this one the swept() loop.
    ("a bad record clears the transcript",
     "            except (ValueError, RecursionError):\n                continue\n            for cmd in commands(rec):",
     "            except (ValueError, RecursionError):\n                return True\n            for cmd in commands(rec):"),
    ("payload not type-checked", "    if not isinstance(payload, dict):",
     "    if False:"),
    ("as_dict passes non-dicts through",
     "    return value if isinstance(value, dict) else {}",
     "    return value"),
    ("as_str passes non-strings through",
     "    return value if isinstance(value, str) else \"\"",
     "    return value"),
    ("RecursionError not caught at the payload parse",
     "    except (ValueError, RecursionError):\n        # `RecursionError` is a",
     "    except ValueError:\n        # `RecursionError` is a"),
    ("RecursionError not caught at the record parse",
     "                rec = json.loads(line)\n            except (ValueError, RecursionError):",
     "                rec = json.loads(line)\n            except ValueError:"),
    ("RecursionError not caught at the tool-input parse",
     "                args = json.loads(args)\n            except (ValueError, RecursionError):",
     "                args = json.loads(args)\n            except ValueError:"),
]


def test_mutations():
    print("mutation checks")
    original = open(TARGET, encoding="utf-8").read()
    for name, old, new in MUTATIONS:
        if original.count(old) != 1:
            check(f"mutation anchor is unique: {name}", False)
            continue
        d = tempfile.mkdtemp()
        mutant = os.path.join(d, "mutant.py")
        with open(mutant, "w", encoding="utf-8") as fh:
            fh.write(original.replace(old, new))
        # Run this suite against the mutant by pointing TARGET at it.
        env = dict(os.environ)
        env["MUTANT_TARGET"] = mutant
        out = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--against-mutant"],
            capture_output=True, text=True, env=env, timeout=120)
        check(f"suite CATCHES mutation: {name}", out.returncode != 0)


def main():
    global TARGET, guard
    if "--against-mutant" in sys.argv:
        TARGET = os.environ["MUTANT_TARGET"]
        spec2 = importlib.util.spec_from_file_location("mutant", TARGET)
        guard = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(guard)

    test_is_commit()
    test_significant()
    test_moves()
    test_swept()
    test_end_to_end()
    if "--against-mutant" not in sys.argv:
        test_mutations()

    print()
    if failures:
        print(f"{len(failures)} failure(s): " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
