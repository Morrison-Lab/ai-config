#!/usr/bin/env python3
"""Regression tests for check-context-closure.py."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "ccc", Path(__file__).parent / "check-context-closure.py"
)
ccc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccc)

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


def reader_for(mapping):
    """A `read` callable over a dict of path -> str, for the pure walk."""

    def read(path):
        body = mapping.get(path)
        return None if body is None else body.encode("utf-8")

    return read


# --- import_paths -----------------------------------------------------------

check(
    "a line that is only @path is an anchored import",
    ccc.import_paths("intro\n@shared/a.md\ntail\n")[0] == ["shared/a.md"],
)
check(
    "several anchored imports are returned in order",
    ccc.import_paths("@a.md\n@b.md\n")[0] == ["a.md", "b.md"],
)
# Claude Code's docs say to "reference them with @ syntax anywhere in your
# CLAUDE.md", and their own example is inline prose. So an inline @path is a
# real import and must be measured, not dropped -- otherwise a consumer whose
# imports are written that way reads as under budget while Claude Code loads
# more than was counted.
anchored, inline = ccc.import_paths(
    "See @README.md for the overview and @docs/guide.md for detail.\n"
)
check("an inline @path IS an import", inline == ["README.md", "docs/guide.md"])
check("  ... and is not counted as anchored", anchored == [])
check(
    "trailing punctuation is not part of an inline import path",
    ccc.import_paths("see @a.md, @b.md; and @c.md.\n")[1]
    == ["a.md", "b.md", "c.md"],
)
check(
    "a path written both ways is reported once, as anchored",
    ccc.import_paths("@a.md\nsee @a.md too\n") == (["a.md"], []),
)
check(
    "an @path inside a code span is NOT an import",
    ccc.import_paths("use `@shared/a.md` to import\n") == ([], []),
)
# Claude Code does not evaluate imports inside fenced blocks, and this corpus
# documents its own @-import syntax in examples -- so a walk that ignored
# fences would import whatever those examples happen to name.
check(
    "an @path inside a fenced block is NOT an import",
    ccc.import_paths("```\n@shared/example.md\n```\n@shared/real.md\n")[0]
    == ["shared/real.md"],
)

# --- walk_closure -----------------------------------------------------------

files, missing, inline = ccc.walk_closure(
    "CLAUDE.md",
    reader_for(
        {
            "CLAUDE.md": "@a.md\n@b.md\n",
            "a.md": "@c.md\n",
            "b.md": "bbbb",
            "c.md": "cc",
        }
    ),
)
paths = [p for p, _, _ in files]
check("closure reaches transitive imports", paths == ["CLAUDE.md", "a.md", "c.md", "b.md"])
check("depth is recorded", dict((p, d) for p, _, d in files)["c.md"] == 2)
check("byte counts are the blob lengths", dict((p, n) for p, n, _ in files)["b.md"] == 4)
check("nothing missing when every import resolves", missing == [])

# A file imported twice must be counted once: Claude Code loads it once, so
# double-counting would overstate the budget and cry wolf.
files, _, _ = ccc.walk_closure(
    "root.md",
    reader_for({"root.md": "@a.md\n@b.md\n", "a.md": "@b.md\n", "b.md": "xxxx"}),
)
check("a file imported twice is counted once", [p for p, _, _ in files].count("b.md") == 1)

# An import cycle must terminate rather than recursing forever.
files, _, _ = ccc.walk_closure(
    "root.md", reader_for({"root.md": "@a.md\n", "a.md": "@root.md\n"})
)
check("an import cycle terminates", len(files) == 2)

files, missing, _ = ccc.walk_closure(
    "root.md", reader_for({"root.md": "@gone.md\n@here.md\n", "here.md": "y"})
)
check("an unresolvable anchored import is reported as missing", missing == [("gone.md", "root.md")])
check("a missing import does not stop the walk", len(files) == 2)

# An inline @token that does not resolve is usually prose (`@claude`, an email
# address), so it must NOT be reported as a dangling import -- that would make
# the check cry wolf on a corpus full of bot mentions. It is surfaced
# separately instead, so a genuinely mistyped inline import is still visible.
files, missing, inline = ccc.walk_closure(
    "root.md", reader_for({"root.md": "ask @claude to look\n@real.md\n", "real.md": "z"})
)
check("an unresolved inline @token is NOT a dangling import", missing == [])
check("  ... and is reported separately", inline == [("claude", "root.md")])
check("  ... while the anchored import still resolves", len(files) == 2)

# Relative imports resolve against the CITING file, not the working
# directory -- Claude Code's docs say so explicitly. A root-level CLAUDE.md
# makes the two coincide, so a walk that works on this repo says nothing
# about a consumer whose imports nest one directory down.
check("a relative child resolves against its parent's directory",
      ccc.resolve("b.md", "docs/a.md") == "docs/b.md")
check("  ... and normalises a ../ segment",
      ccc.resolve("../shared/c.md", "docs/sub/a.md") == "docs/shared/c.md")
check("  ... while an absolute path is left alone",
      ccc.resolve("/etc/x.md", "docs/a.md") == "/etc/x.md")
check("  ... as is a ~ path", ccc.resolve("~/x.md", "docs/a.md") == "~/x.md")

files, missing, _ = ccc.walk_closure(
    "CLAUDE.md",
    reader_for({"CLAUDE.md": "@docs/a.md\n", "docs/a.md": "@b.md\n", "docs/b.md": "nested"}),
)
check(
    "a nested relative import is found, not reported missing",
    missing == [] and "docs/b.md" in [p for p, _, _ in files],
)

# Claude Code's documented limit is FOUR hops, so a fifth-level file is not
# loaded and must not be counted -- counting it would inflate both the
# closure total and the pin-bump delta.
check("the shipped depth limit matches the documented four hops",
      ccc.MAX_IMPORT_DEPTH == 4)
deep = {"f0.md": "@f1.md\n"}
for i in range(1, 12):
    deep[f"f{i}.md"] = f"@f{i + 1}.md\n"
files, _, _ = ccc.walk_closure("f0.md", reader_for(deep))
check("the walk stops at the documented depth by default",
      max(d for _, _, d in files) == 4)
files, _, _ = ccc.walk_closure("f0.md", reader_for(deep), max_depth=3)
check("the walk stops at an explicit max_depth", max(d for _, _, d in files) <= 3)

# --- readers ----------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / "CLAUDE.md").write_text("@own.md\n@.ai-config/sub.md\n", encoding="utf-8")
    (base / "own.md").write_text("own", encoding="utf-8")
    sub = base / ".ai-config"
    sub.mkdir()
    (sub / "sub.md").write_text("working-tree version", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=sub, check=True)
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "pinned"], cwd=sub, check=True)
    (sub / "sub.md").write_text("a much longer newer version", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "newer"], cwd=sub, check=True)

    files, _, _ = ccc.walk_closure("CLAUDE.md", ccc.local_reader(base))
    check("local_reader reads the working tree", len(files) == 3)

    # The pin-bump report's core claim: the import list is fixed, and only
    # what the submodule contributes changes.
    at_head, _, _ = ccc.walk_closure(
        "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD")
    )
    at_pin, _, _ = ccc.walk_closure(
        "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD~1")
    )
    check(
        "submodule_reader resolves submodule paths at the given rev",
        sum(n for _, n, _ in at_head) > sum(n for _, n, _ in at_pin),
    )
    check(
        "submodule_reader reads non-submodule paths from disk",
        dict((p, n) for p, n, _ in at_pin)["own.md"] == 3,
    )
    check(
        "the import list is unchanged across revs (only weights differ)",
        [p for p, _, _ in at_head] == [p for p, _, _ in at_pin],
    )

    # A wrong --base must not read as "a small closure, under budget".
    rc = ccc.main(["--base", str(base / "nonexistent")])
    check("an unreadable root exits 2 rather than reporting 0 bytes", rc == 2)

    # A dangling import is a defect, not a size finding, so it fails without
    # --strict.
    (base / "CLAUDE.md").write_text("@own.md\n@gone.md\n", encoding="utf-8")
    rc = ccc.main(["--base", str(base), "--budget", "10000000"])
    check("a dangling import exits 1 even without --strict", rc == 1)

    # An unresolved INLINE token is prose, so it must not fail the check --
    # otherwise every `@claude` mention in a corpus becomes a build failure.
    (base / "CLAUDE.md").write_text("@own.md\nask @claude about it\n", encoding="utf-8")
    check(
        "an unresolved inline @token does not fail the check",
        ccc.main(["--base", str(base), "--budget", "10000000"]) == 0,
    )

    # Advisory by default over budget (ai-config#695), blocking under --strict.
    (base / "CLAUDE.md").write_text("@own.md\n", encoding="utf-8")
    check(
        "over budget is advisory by default",
        ccc.main(["--base", str(base), "--budget", "1"]) == 0,
    )
    check(
        "over budget exits 1 under --strict",
        ccc.main(["--base", str(base), "--budget", "1", "--strict"]) == 1,
    )
    check(
        "under budget exits 0",
        ccc.main(["--base", str(base), "--budget", "10000000"]) == 0,
    )

    # --strict must cover the COMPARED total too. Gating only on the current
    # total prints "this bump would cross the budget" and then exits 0, which
    # contradicts what the flag says it does. The budget below sits between
    # the two totals, so the current pin is under it and the bump is over.
    (base / "CLAUDE.md").write_text("@own.md\n@.ai-config/sub.md\n", encoding="utf-8")
    at_pin_total = sum(
        n for _, n, _ in ccc.walk_closure(
            "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD~1")
        )[0]
    )
    at_head_total = sum(
        n for _, n, _ in ccc.walk_closure(
            "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD")
        )[0]
    )
    between = (at_pin_total + at_head_total) // 2
    check(
        "the fixture straddles the budget (pin under, bump over)",
        at_pin_total <= between < at_head_total,
    )
    args = ["--base", str(base), "--budget", str(between), "--compare", "HEAD"]
    # The working tree holds the newer submodule content, so measure the
    # "current" side at the older pin to make the bump the thing that crosses.
    subprocess.run(["git", "checkout", "-q", "HEAD~1", "--", "sub.md"], cwd=sub, check=True)
    check(
        "a bump that crosses the budget exits 1 under --strict",
        ccc.main(args + ["--strict"]) == 1,
    )
    check(
        "  ... and is still advisory without --strict",
        ccc.main(args) == 0,
    )

# --bytes-per-token 0 previously passed argparse and crashed in render() with
# a ZeroDivisionError; a negative silently produced a nonsense estimate. Bad
# operator input belongs at the boundary (shared/principles/fail-fast.md).
# Exercised through main(), NOT by calling positive_int() directly: a direct
# call passes even when argparse is not wired to use it, so that version of
# this test stayed green against a `type=int` regression. argparse exits 2 on
# a bad value, so SystemExit(2) is the pass condition.
for bad in ("0", "-1", "abc"):
    try:
        ccc.main(["--bytes-per-token", bad])
        rejected = False
    except SystemExit as exc:
        rejected = exc.code == 2
    except Exception:
        # e.g. the ZeroDivisionError this validation exists to prevent.
        # A crash downstream is not "rejected at parse time".
        rejected = False
    check(f"--bytes-per-token {bad} is rejected by the parser", rejected)
check(
    "a positive --bytes-per-token is accepted",
    ccc.main(["--bytes-per-token", "4", "--budget", "100000000"]) == 0,
)
check("positive_int itself rejects zero", ccc.positive_int("4") == 4)

# --- corpus facts -----------------------------------------------------------

# These pin facts about the real corpus rather than fixture behaviour, so a
# future change that breaks them fails here instead of silently shrinking the
# measured closure.
files, missing, inline = ccc.walk_closure("CLAUDE.md", ccc.local_reader(ccc.REPO_ROOT))
check("this repo's own closure has no dangling imports", not missing)
check("this repo's own closure resolves more than just the root", len(files) > 1)

# The inline matcher runs against a corpus full of `@claude` bot mentions and
# email addresses. It must find the real imports without turning that prose
# into dangling-import failures -- the cry-wolf failure mode that would get
# this check switched off.
check(
    "unresolved inline @tokens in this corpus are reported, not fatal",
    ccc.main(["--budget", "100000000"]) == 0,
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
