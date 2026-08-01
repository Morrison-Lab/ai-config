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
    "a line that is only @path is an import",
    ccc.import_paths("intro\n@shared/a.md\ntail\n") == ["shared/a.md"],
)
check(
    "several imports are returned in order",
    ccc.import_paths("@a.md\n@b.md\n") == ["a.md", "b.md"],
)
check(
    "an @mention mid-sentence is NOT an import",
    ccc.import_paths("ask @claude to review, see @a.md for detail\n") == [],
)
check(
    "an @path inside a code span is NOT an import",
    ccc.import_paths("use `@shared/a.md` to import\n") == [],
)
# Claude Code does not evaluate imports inside fenced blocks, and this corpus
# documents its own @-import syntax in examples -- so a walk that ignored
# fences would import whatever those examples happen to name.
check(
    "an @path inside a fenced block is NOT an import",
    ccc.import_paths("```\n@shared/example.md\n```\n@shared/real.md\n")
    == ["shared/real.md"],
)

# --- walk_closure -----------------------------------------------------------

files, missing = ccc.walk_closure(
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
files, _ = ccc.walk_closure(
    "root.md",
    reader_for({"root.md": "@a.md\n@b.md\n", "a.md": "@b.md\n", "b.md": "xxxx"}),
)
check("a file imported twice is counted once", [p for p, _, _ in files].count("b.md") == 1)

# An import cycle must terminate rather than recursing forever.
files, _ = ccc.walk_closure(
    "root.md", reader_for({"root.md": "@a.md\n", "a.md": "@root.md\n"})
)
check("an import cycle terminates", len(files) == 2)

files, missing = ccc.walk_closure(
    "root.md", reader_for({"root.md": "@gone.md\n@here.md\n", "here.md": "y"})
)
check("an unresolvable import is reported as missing", missing == [("gone.md", "root.md")])
check("a missing import does not stop the walk", len(files) == 2)

# Depth limit: Claude Code stops following imports after a few hops, so a
# deeper chain must not be counted as loaded context.
deep = {"f0.md": "@f1.md\n"}
for i in range(1, 12):
    deep[f"f{i}.md"] = f"@f{i + 1}.md\n"
files, _ = ccc.walk_closure("f0.md", reader_for(deep), max_depth=3)
check("the walk stops at max_depth", max(d for _, _, d in files) <= 3)

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

    files, _ = ccc.walk_closure("CLAUDE.md", ccc.local_reader(base))
    check("local_reader reads the working tree", len(files) == 3)

    # The pin-bump report's core claim: the import list is fixed, and only
    # what the submodule contributes changes.
    at_head, _ = ccc.walk_closure(
        "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD")
    )
    at_pin, _ = ccc.walk_closure(
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

# --- corpus facts -----------------------------------------------------------

# The anchored-import scope limit documented in the script's docstring: it
# under-reports if any import is written inline. Pinning it as a corpus fact
# means the claim is checked rather than trusted, and a future inline import
# fails here instead of silently shrinking the measured closure.
root_text = (ccc.REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
inline = [
    line
    for line in root_text.splitlines()
    if "@shared/" in line and not line.strip().startswith("@shared/")
    and "`" not in line and "](" not in line
]
check("every @shared import in CLAUDE.md is on its own line", not inline)

files, missing = ccc.walk_closure("CLAUDE.md", ccc.local_reader(ccc.REPO_ROOT))
check("this repo's own closure has no dangling imports", not missing)
check("this repo's own closure resolves more than just the root", len(files) > 1)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
