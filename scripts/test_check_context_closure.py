#!/usr/bin/env python3
"""Regression tests for check-context-closure.py."""
import importlib.util
import os
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

files, missing, inline, _amb = ccc.walk_closure(
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
files, _, _, _amb = ccc.walk_closure(
    "root.md",
    reader_for({"root.md": "@a.md\n@b.md\n", "a.md": "@b.md\n", "b.md": "xxxx"}),
)
check("a file imported twice is counted once", [p for p, _, _ in files].count("b.md") == 1)

# An import cycle must terminate rather than recursing forever.
files, _, _, _amb = ccc.walk_closure(
    "root.md", reader_for({"root.md": "@a.md\n", "a.md": "@root.md\n"})
)
check("an import cycle terminates", len(files) == 2)

files, missing, _, _amb = ccc.walk_closure(
    "root.md", reader_for({"root.md": "@gone.md\n@here.md\n", "here.md": "y"})
)
check("an unresolvable anchored import is reported as missing", missing == [("gone.md", "root.md")])
check("a missing import does not stop the walk", len(files) == 2)

# An inline @token that does not resolve is usually prose (`@claude`, an email
# address), so it must NOT be reported as a dangling import -- that would make
# the check cry wolf on a corpus full of bot mentions. It is surfaced
# separately instead, so a genuinely mistyped inline import is still visible.
files, missing, inline, _amb = ccc.walk_closure(
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

files, missing, _, _amb = ccc.walk_closure(
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
files, _, _, _amb = ccc.walk_closure("f0.md", reader_for(deep))
check("the walk stops at the documented depth by default",
      max(d for _, _, d in files) == 4)
files, _, _, _amb = ccc.walk_closure("f0.md", reader_for(deep), max_depth=3)
check("the walk stops at an explicit max_depth", max(d for _, _, d in files) <= 3)

# --- readers ----------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / "CLAUDE.md").write_text("@own.md\n@.ai-config/sub.md\n", encoding="utf-8")
    (base / "own.md").write_text("own", encoding="utf-8")
    sub = base / ".ai-config"
    sub.mkdir()
    (sub / "sub.md").write_text("working-tree version", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=sub, check=True)
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "pinned"], cwd=sub, check=True)
    (sub / "sub.md").write_text("a much longer newer version", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "newer"], cwd=sub, check=True)

    files, _, _, _amb = ccc.walk_closure("CLAUDE.md", ccc.local_reader(base))
    check("local_reader reads the working tree", len(files) == 3)

    # The pin-bump report's core claim: the import list is fixed, and only
    # what the submodule contributes changes.
    at_head, _, _, _amb = ccc.walk_closure(
        "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD")
    )
    at_pin, _, _, _amb = ccc.walk_closure(
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
# This real-corpus call, and the one at the end of this file, raise the char
# cap deliberately. Both assert things about the PARSER, and leaving them on
# the real cap would make them fail the day `CLAUDE.md` grows past it -- a
# test failing because corpus content grew, reported as a parser regression.
# The cap's own signal belongs to the check step, which reports it once and
# says what it means.
check(
    "a positive --bytes-per-token is accepted",
    ccc.main(
        ["--bytes-per-token", "4", "--budget", "100000000",
         "--root-char-cap", "100000000"]
    ) == 0,
)
check("positive_int accepts a positive value", ccc.positive_int("4") == 4)

# --- round-2 review findings ------------------------------------------------

# An unresolved inline token must not claim a path and downgrade a later
# ANCHORED import of the same path from a hard failure to a warning. The bug
# was purely traversal-order dependent, so it needs both citations present.
files, missing, inline, _amb = ccc.walk_closure(
    "root.md",
    reader_for(
        {
            "root.md": "@a.md\n@b.md\n",
            "a.md": "mentions @gone.md inline\n",
            "b.md": "@gone.md\n",
        }
    ),
)
check(
    "an inline mention does not downgrade a later anchored dangling import",
    missing == [("gone.md", "b.md")],
)
check("  ... and it is not double-reported as inline", inline == [])

# Code spans and fences use RUNS of markers. A single-backtick pattern strips
# the two empty pairs around ``@x`` and leaves the token; a `~~~` block was
# not recognised at all. Either way a documented example becomes an import.
check(
    "a double-backtick code span is not an import",
    ccc.import_paths("use ``@a.md`` and @real.md\n") == ([], ["real.md"]),
)
check(
    "a ~~~ fenced block is not an import",
    ccc.import_paths("~~~\n@a.md\n~~~\n@real.md\n") == (["real.md"], []),
)
# A code span must not span NEWLINES. A `[\\s\\S]*?` version pairs a stray
# backtick with another much later in the file and strips everything between,
# swallowing real imports -- measured on this repo, 69 anchored imports fell
# to 50. This is a regression guard, not a hypothetical.
check(
    "a code span does not swallow imports across lines",
    ccc.import_paths("a `span` here\n@real.md\nlater `another` span\n")[0]
    == ["real.md"],
)
# CommonMark allows a code span to contain line endings but NOT a blank
# line. That bound is what stops a stray backtick pairing with another far
# later in the file: the damage is confined to one paragraph.
check(
    "a stray backtick cannot swallow across a blank line",
    ccc.import_paths("stray ` backtick\n\n@real.md\n\nmore ` text\n")[0]
    == ["real.md"],
)
check(
    "a genuine multi-line code span IS stripped (CommonMark)",
    ccc.import_paths("a `code\n@gone.md\nmore` b\n@real.md\n")[0] == ["real.md"],
)
# The body deliberately contains a BLANK LINE. Without one, the code-span
# rule strips an indented fence incidentally, so a simpler fixture passes
# even with the indentation allowance removed -- it tests nothing. A blank
# line is exactly what a span may not contain, so only the fence rule can
# handle this.
check(
    "a fence indented up to three spaces is still a fence",
    ccc.import_paths("   ```\n@gone.md\n\nstill inside\n   ```\n@real.md\n")[0]
    == ["real.md"],
)

check(
    "a 4-backtick fence is not an import",
    ccc.import_paths("````\n@a.md\n````\n@real.md\n") == (["real.md"], []),
)

# Claude Code documents `@~/.claude/my-project-instructions.md` as the way to
# share personal instructions across worktrees, so a ~ import is real context.
# Joining it to --base would look under <base>/~/... and report it dangling.
#
# HOME is redirected at the temp dir rather than probing the real home: a
# fixed filename there collides with whatever the user happens to have, so
# the earlier version could fail even with local_reader working correctly.
with tempfile.TemporaryDirectory() as tmp:
    fake_home = Path(tmp) / "home"
    fake_home.mkdir()
    (fake_home / "personal.md").write_text("probe", encoding="utf-8")
    _saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    os.environ["HOME"] = str(fake_home)
    os.environ["USERPROFILE"] = str(fake_home)
    try:
        check(
            "a ~ import is expanded, not joined to --base",
            ccc.local_reader(Path(tmp))("~/personal.md") == b"probe",
        )
        (Path(tmp) / "CLAUDE.md").write_text("@~/personal.md\n", encoding="utf-8")
        files, missing, _, _amb = ccc.walk_closure(
            "CLAUDE.md", ccc.local_reader(Path(tmp))
        )
        check(
            "  ... so a ~ import is counted, not reported dangling",
            missing == [] and len(files) == 2,
        )
    finally:
        for k, v in _saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# --- gitlink baseline -------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=base, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=base, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=base, check=True)
    sub = base / ".ai-config"
    sub.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=sub, check=True)
    (sub / "sub.md").write_text("old pinned content", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "pin"], cwd=sub, check=True)
    old_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=sub, capture_output=True, text=True, check=True
    ).stdout.strip()

    (base / "CLAUDE.md").write_text("@.ai-config/sub.md\n", encoding="utf-8")
    subprocess.run(["git", "add", "CLAUDE.md"], cwd=base, check=True)
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo",
         f"160000,{old_sha},.ai-config"], cwd=base, check=True,
    )
    subprocess.run(["git", "commit", "-qm", "record pin"], cwd=base, check=True)

    check("gitlink_rev reads the parent's recorded pin",
          ccc.gitlink_rev(base, ".ai-config") == old_sha)
    check("gitlink_rev returns None when the path is not a gitlink",
          ccc.gitlink_rev(base, "CLAUDE.md") is None)

    # The pin-bump workflow itself: the submodule is checked out at the TARGET
    # while the parent still records the old pin. Baselining on the working
    # tree would compare the target against itself and report a zero delta --
    # the one number this tool exists to produce, wrong exactly when consulted.
    (sub / "sub.md").write_text("much longer new content here", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "newer"], cwd=sub, check=True)

    from io import StringIO
    import contextlib

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ccc.main(["--base", str(base), "--budget", "100000000",
                       "--compare", "HEAD"])
    out = buf.getvalue()
    check("compare mode succeeds with a checked-out-ahead submodule", rc == 0)
    check(
        "  ... and does NOT report a zero delta (baselined on the gitlink)",
        "+0 B" not in out and "(+0%)" not in out,
    )

    # --strict must cover the COMPARED total too. Gating only on the current
    # total prints "this bump would cross the budget" and then exits 0, which
    # contradicts what the flag says it does. The budget below sits between
    # the two totals, so the pin is under it and the bump is over.
    pin_total = sum(
        n for _, n, _ in ccc.walk_closure(
            "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", old_sha)
        )[0]
    )
    head_total = sum(
        n for _, n, _ in ccc.walk_closure(
            "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", "HEAD")
        )[0]
    )
    between = (pin_total + head_total) // 2
    check(
        "the fixture straddles the budget (pin under, bump over)",
        pin_total <= between < head_total,
    )
    strict_args = ["--base", str(base), "--budget", str(between), "--compare", "HEAD"]
    with contextlib.redirect_stdout(StringIO()):
        strict_rc = ccc.main(strict_args + ["--strict"])
        advisory_rc = ccc.main(strict_args)
    check("a bump that crosses the budget exits 1 under --strict", strict_rc == 1)
    check("  ... and is still advisory without --strict", advisory_rc == 0)

    # An import that resolves at the pin but not at the target shrinks
    # after_total for the wrong reason, so the delta would read as a
    # favourable bump rather than an incomplete comparison. Built by
    # recording a pin that HAS the file and comparing against an earlier
    # revision that lacks it -- `old_sha` predates `only-old.md`.
    subprocess.run(["git", "checkout", "-q", old_sha], cwd=sub, check=True)
    (sub / "only-old.md").write_text("present at the pin only", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "add only-old"], cwd=sub, check=True)
    pin2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=sub, capture_output=True, text=True, check=True
    ).stdout.strip()
    # The second citation is INLINE on purpose. An anchored one that fails at
    # the target is already caught by the after_missing guard above, so only
    # an inline one exercises the `lost` check -- a distinction the first
    # version of this test missed, passing for the wrong reason.
    (base / "CLAUDE.md").write_text(
        "@.ai-config/sub.md\nsee @.ai-config/only-old.md for detail\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "CLAUDE.md"], cwd=base, check=True)
    subprocess.run(
        ["git", "update-index", "--cacheinfo", f"160000,{pin2},.ai-config"],
        cwd=base, check=True,
    )
    subprocess.run(["git", "commit", "-qm", "repin"], cwd=base, check=True)

    check(
        "fixture: the recorded pin resolves both files",
        ccc.gitlink_rev(base, ".ai-config") == pin2
        and len(ccc.walk_closure(
            "CLAUDE.md", ccc.submodule_reader(base, ".ai-config", pin2)
        )[0]) == 3,
    )
    with contextlib.redirect_stdout(StringIO()):
        lost_rc = ccc.main(["--base", str(base), "--budget", "100000000",
                            "--compare", old_sha])
    check("a file lost at the target invalidates the comparison", lost_rc == 2)

# --- round-3 review findings ------------------------------------------------

# A diamond: `deep.md` is reachable at depth 4 down a chain and at depth 1
# directly. Reached via the chain first, its own imports sit at depth 5 and
# are skipped for exceeding the limit; a plain `loaded` SET then suppressed
# the shallower revisit, so `child.md` was never counted although it is well
# inside four hops. The result depended on which citation came first.
_diamond = {
    "root.md": "@a1.md\n@deep.md\n",
    "a1.md": "@a2.md\n",
    "a2.md": "@a3.md\n",
    "a3.md": "@deep.md\n",
    "deep.md": "@child.md\n",
    "child.md": "CHILD BYTES",
}
chain_first, _, _, _amb = ccc.walk_closure("root.md", reader_for(_diamond))
_reversed = dict(_diamond, **{"root.md": "@deep.md\n@a1.md\n"})
direct_first, _, _, _amb = ccc.walk_closure("root.md", reader_for(_reversed))
names_chain = [p for p, _, _ in chain_first]
names_direct = [p for p, _, _ in direct_first]
check(
    "a file reached first at depth 4 is re-walked via a shallower route",
    "child.md" in names_chain,
)
check(
    "  ... so the closure is traversal-order independent",
    sorted(names_chain) == sorted(names_direct),
)
check(
    "  ... and byte totals agree across orders",
    sum(b for _, b, _ in chain_first) == sum(b for _, b, _ in direct_first),
)
check(
    "  ... with each file still counted exactly once",
    names_chain.count("deep.md") == 1 and names_chain.count("child.md") == 1,
)
# The four-hop limit must still bind on a chain with no shallower route.
_chain = {"f0.md": "@f1.md\n"}
for i in range(1, 9):
    _chain[f"f{i}.md"] = f"@f{i + 1}.md\n"
files, _, _, _amb = ccc.walk_closure("f0.md", reader_for(_chain))
check("re-walking does not defeat the depth limit",
      max(d for _, _, d in files) == 4)

# --- compare mode validates BOTH closures independently ---------------------

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=base, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=base, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=base, check=True)
    sub = base / ".ai-config"
    sub.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=sub, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=sub, check=True)
    # Baseline is BROKEN: it cites gone.md, which does not exist at the pin.
    (sub / "sub.md").write_text("@.ai-config/gone.md\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "broken pin"], cwd=sub, check=True)
    broken_pin = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=sub, capture_output=True, text=True, check=True
    ).stdout.strip()
    # The TARGET fixes it, which is exactly the state the old condition
    # (`after_missing and not before_missing`) accepted silently.
    (sub / "sub.md").write_text("all good now\n", encoding="utf-8")
    (sub / "gone.md").write_text("now present", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
    subprocess.run(["git", "commit", "-qm", "fixed"], cwd=sub, check=True)

    (base / "CLAUDE.md").write_text("@.ai-config/sub.md\n", encoding="utf-8")
    subprocess.run(["git", "add", "CLAUDE.md"], cwd=base, check=True)
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo",
         f"160000,{broken_pin},.ai-config"], cwd=base, check=True,
    )
    subprocess.run(["git", "commit", "-qm", "record broken pin"], cwd=base, check=True)

    buf = StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = ccc.main(["--base", str(base), "--budget", "100000000",
                       "--compare", "HEAD"])
    check("a dangling import at the BASELINE fails, even when the target fixes it",
          rc == 2)
    check("  ... and the error names the pin side", "recorded pin" in buf.getvalue())

# --- round-5 review findings ------------------------------------------------

# A CRLF checkout, or a trailing space, silently downgraded EVERY anchored
# import: `$` will not match before a `\r` and `[^\s`]+` cannot consume it,
# so the anchored matcher found nothing while the inline matcher still found
# the token -- turning a hard dangling-import failure into a non-fatal
# warning, repo-wide, on Windows.
check(
    "CRLF line endings still yield ANCHORED imports",
    ccc.import_paths("@a.md\r\n@b.md\r\n") == (["a.md", "b.md"], []),
)
check(
    "trailing horizontal whitespace does not downgrade an anchored import",
    ccc.import_paths("@a.md  \n")[0] == ["a.md"],
)
check(
    "a CRLF dangling import is fatal, not a warning",
    ccc.walk_closure("root.md", reader_for({"root.md": "@gone.md\r\n"}))[1]
    == [("gone.md", "root.md")],
)

# An unclosed fence is REPORTED rather than swallowed to EOF. Implementing
# CommonMark's rule verbatim is catastrophic on real content: this repo's own
# CLAUDE.md has same-length nested fences, so its outer closer reads as a
# fresh unclosed opener and everything after becomes code -- measured, 19
# genuine imports lost and the closure down from 70 files to 51.
check(
    "an unclosed fence does not swallow the rest of the document",
    ccc.import_paths("```\n@inside.md\n\n@after.md\n")[0]
    == ["inside.md", "after.md"],
)
check(
    "an unclosed fence is counted as unbalanced",
    ccc.unbalanced_fences("```\n@inside.md\n") == 1,
)
check(
    "a balanced document reports no unbalanced fences",
    ccc.unbalanced_fences("```\n@x.md\n```\n") == 0,
)
_f, _m, _i, _amb = ccc.walk_closure(
    "root.md", reader_for({"root.md": "```\n@x.md\n", "x.md": "y"})
)
check("walk_closure surfaces the ambiguous file", _amb == [("root.md", 1)])

# This repo's own CLAUDE.md is the real instance, so pin it: the count must
# stay at 4 anchored imports whatever the fence handling does. (Was 69 until
# ai-config#1065 added @shared/workflow/learn-from-review-findings.md; 70 until
# ai-config#1205 added @shared/workflow/agent-teams.md; 71 until ai-config#1325
# added @shared/writing/ambiguous-reference.md; 72 until ai-config#1334 moved
# the existing-PR-branch section out to
# @shared/workflow/use-existing-pr-branch.md; 79 after the CLAUDE.md
# char-cap trim decomposed six inline sections into
# @shared/workflow/run-ums-proactively.md,
# @shared/workflow/flag-session-boundaries.md,
# @shared/workflow/keep-checkouts-fresh.md,
# @shared/workflow/self-review-fallback.md,
# @shared/workflow/use-subagents.md, and
# @shared/writing/reorganize-prose.md; 80 after
# UCD-SERG/serocalculator#661 added
# @shared/workflow/read-canonical-doc-before-starting.md; 60 after converting
# 20 heavy @shared fragments to on-demand markdown links; 8 after consolidating
# overhead context across AI models; 4 after ai-config#2393 converted four more
# heavy workflow imports to on-demand markdown links; 5 after ai-config#2652
# added @shared/workflow/revert-merge.md.)
#
# The pin is deliberately a magic number rather than a value derived from
# CLAUDE.md. Deriving it would make the guard vacuous, since it would then
# agree with whatever the file happens to say -- the one thing a regression
# guard must not do. The cost is that an @-import edit has to bump it by hand,
# so the assertion name below carries that remedy: `check` prints only the
# name, and this is the failure an import-list edit actually produces.
check(
    "this repo's CLAUDE.md still yields 5 anchored imports "
    "(adding or removing an @-import bumps this pin -- update the count and "
    "record the bump in the annotation style of the comment above)",
    len(ccc.import_paths(
        (ccc.REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    )[0]) == 5,
)

# --- round-6 review findings ------------------------------------------------

# Run lengths must be PRESERVED, not backtracked. Python shrinks `+`/`{3,}`
# on demand, so a four-backtick fence was "closed" by three and a
# double-backtick span paired with a single-backtick closer -- stripping
# content that is not code and hiding the imports inside it.
check(
    "a 4-backtick fence is NOT closed by 3 backticks",
    ccc.import_paths("````\n@a.md\n```\n@b.md\n")[0] == ["a.md", "b.md"],
)
check(
    "a 4-backtick fence IS closed by 4",
    ccc.import_paths("````\n@a.md\n````\n@b.md\n")[0] == ["b.md"],
)
check(
    "a longer closer still closes",
    ccc.import_paths("```\n@a.md\n`````\n@b.md\n")[0] == ["b.md"],
)
check(
    "a tilde fence does not close a backtick fence",
    ccc.import_paths("```\n@a.md\n~~~\n@b.md\n")[0] == ["a.md", "b.md"],
)
check(
    "a closer with a mixed marker suffix is rejected",
    ccc.import_paths("```\n@a.md\n```~~\n@b.md\n")[0] == ["a.md", "b.md"],
)
check(
    "an orphan fence marker is not reused as a code-span delimiter",
    ccc.strip_code("```\n@a.md\n```~~\n@b.md\n").count("@") == 2,
)
# A code span's delimiters must be MAXIMAL runs, and its opener must not be
# preceded by a backtick. Without both guards the engine backtracks: ``@x`
# pairs its second backtick with the single closer, and ```@x`` pairs a
# shrunken opener with the double closer -- stripping text that is not a
# code span at all. Asserted through strip_code rather than import_paths,
# because an @ immediately preceded by a backtick is not an inline import
# either, so import_paths cannot distinguish these.
# Mid-line on purpose: a LINE-INITIAL run of three or more backticks is a
# fence opener, whose info string is legitimately dropped, so a line-initial
# fixture would pass for the wrong reason.
check(
    "an unmatched double-backtick opener does not strip following text",
    "@a.md" in ccc.strip_code("x ``@a.md` y\n"),
)
check(
    "a triple opener does not pair with a double closer",
    "@a.md" in ccc.strip_code("x ```@a.md`` y\n"),
)
check(
    "a properly matched span IS still stripped",
    "@a.md" not in ccc.strip_code("x `@a.md` y\n"),
)

# A file first reached deeply and then via a shallower route had `loaded`
# corrected but kept the ORIGINAL depth in the reported tuple, so the report
# showed the route it happened to be found by first, not its real depth.
_dia, _, _, _ = ccc.walk_closure("root.md", reader_for(_diamond))
_depths = {p: d for p, _, d in _dia}
check("a shallower revisit corrects the REPORTED depth", _depths["deep.md"] == 1)
check("  ... and its children get the shallower depth too",
      _depths["child.md"] == 2)

# --- round-7 review findings ------------------------------------------------

# Every line-ending construct must accept CRLF. Two separate omissions, both
# of which turn a Windows checkout into a differently-wrong measurement:
#
#   * a fence closer whose `[ \\t]*$` cannot consume the `\\r` leaves a
#     BALANCED block looking like two orphan markers, so strip_code drops the
#     marker lines and KEEPS the body -- counting documented `@path` examples
#     inside a code block as real imports;
#   * a blank-line bound written `\\n(?![ \\t]*\\n)` never fires on CRLF, which
#     reopens the swallow bug this module already fixed once for LF.
check(
    "a balanced CRLF fence is stripped, not read as two orphans",
    ccc.import_paths("```\r\n@gone.md\r\n```\r\n@real.md\r\n")[0] == ["real.md"],
)
check(
    "  ... and reports no unbalanced fences",
    ccc.unbalanced_fences("```\r\n@x.md\r\n```\r\n") == 0,
)
check(
    "a CRLF tilde fence is stripped",
    ccc.import_paths("~~~\r\n@gone.md\r\n~~~\r\n@real.md\r\n")[0] == ["real.md"],
)
check(
    "a CRLF indented fence with a blank body line is stripped",
    ccc.import_paths(
        "   ```\r\n@gone.md\r\n\r\nx\r\n   ```\r\n@real.md\r\n"
    )[0] == ["real.md"],
)
check(
    "the blank-line bound fires on CRLF, so a stray backtick cannot swallow",
    ccc.import_paths("stray ` x\r\n\r\n@real.md\r\n\r\ny ` z\r\n")[0]
    == ["real.md"],
)
check(
    "a genuine CRLF multi-line span is still stripped",
    ccc.import_paths("a `code\r\n@gone.md\r\nmore` b\r\n@real.md\r\n")[0]
    == ["real.md"],
)
check(
    "run-length rules still hold under CRLF",
    ccc.import_paths("````\r\n@a.md\r\n```\r\n@b.md\r\n")[0] == ["a.md", "b.md"],
)

# --- corpus facts -----------------------------------------------------------

# These pin facts about the real corpus rather than fixture behaviour, so a
# future change that breaks them fails here instead of silently shrinking the
# measured closure.
files, missing, inline, _amb = ccc.walk_closure("CLAUDE.md", ccc.local_reader(ccc.REPO_ROOT))
check("this repo's own closure has no dangling imports", not missing)
check("this repo's own closure resolves more than just the root", len(files) > 1)

# The inline matcher runs against a corpus full of `@claude` bot mentions and
# email addresses. It must find the real imports without turning that prose
# into dangling-import failures -- the cry-wolf failure mode that would get
# this check switched off.
check(
    "unresolved inline @tokens in this corpus are reported, not fatal",
    ccc.main(["--budget", "100000000", "--root-char-cap", "100000000"]) == 0,
)

# --- the root file's hard character cap -------------------------------------
# The harness's own cap on the auto-loaded CLAUDE.md, which differs from the
# byte budget in kind: it is external, it is denominated in characters, and
# crossing it is a defect rather than a prompt. See DEFAULT_ROOT_CHAR_CAP.

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / "CLAUDE.md").write_text("x" * 100 + "\n", encoding="utf-8")

    check(
        "the root's character count is read from the decoded text",
        ccc.root_char_count(base, "CLAUDE.md") == 101,
    )
    check(
        "an unreadable root yields None rather than 0",
        ccc.root_char_count(base, "absent.md") is None,
    )

    # Blocking WITHOUT --strict is the whole point: the byte budget is ours
    # to miss, this cap is the harness's. Both directions are asserted, so a
    # future change that quietly gates it on --strict fails here.
    check(
        "over the char cap exits 1 without --strict",
        ccc.main(
            ["--base", str(base), "--budget", "100000000", "--root-char-cap", "50"]
        ) == 1,
    )
    check(
        "under the char cap exits 0",
        ccc.main(
            ["--base", str(base), "--budget", "100000000", "--root-char-cap", "500"]
        ) == 0,
    )

    # Characters, not bytes. A file of multi-byte glyphs is comfortably under
    # a character cap it would blow through if the check measured bytes --
    # which is the one test that distinguishes the two implementations, and
    # this corpus's prose is not pure ASCII.
    # \u2014 (em-dash) is 3 bytes in UTF-8 and 1 character. Written as an
    # escape rather than the glyph, per ascii-punctuation-in-source: the
    # rule covers string literals in code, and the escape is the form it
    # prescribes when the character itself is the point.
    (base / "CLAUDE.md").write_text("\u2014" * 100, encoding="utf-8")
    check(
        "the cap counts characters rather than bytes",
        ccc.root_char_count(base, "CLAUDE.md") == 100
        and (base / "CLAUDE.md").stat().st_size == 300,
    )
    check(
        "a multi-byte file under the char cap passes",
        ccc.main(
            ["--base", str(base), "--budget", "100000000", "--root-char-cap", "150"]
        ) == 0,
    )

over, text = ccc.render_root_chars(95, "CLAUDE.md", 100, 0.90)
check("the warning band fires below the cap", not over and "WARNING" in text)
check("the warning band reports the remaining headroom", "5 to spare" in text)

over, text = ccc.render_root_chars(50, "CLAUDE.md", 100, 0.90)
check("a comfortable margin reports the count without warning", not over
      and "WARNING" not in text and "50 " in text)

over, text = ccc.render_root_chars(101, "CLAUDE.md", 100, 0.90)
check("over the cap reports by how much", over and "over by 1" in text)

over, text = ccc.render_root_chars(None, "CLAUDE.md", 100, 0.90)
check(
    "an unreadable root says the cap was NOT checked rather than passing quietly",
    not over and "NOT checked" in text,
)


def _fc_rejects_zero():
    """argparse exits 2 on a non-positive --fragment-cap rather than accepting it."""
    try:
        ccc.main(["--fragment-cap", "0"])
    except SystemExit as exc:
        return exc.code == 2
    return False


# --- render_fragment_caps ---------------------------------------------------

# depth 0 is the root, which --root-char-cap already governs under a
# different limit in a different unit. Gating it twice would let the two
# reports disagree about one path.
over, text = ccc.render_fragment_caps(
    [("CLAUDE.md", 500, 0), ("shared/a.md", 10, 1)], 100)
check("the root file is exempt from the per-file cap", not over)
check(
    "the root file is not counted among the fragments examined",
    "1 fragment(s) examined" in text,
)

over, text = ccc.render_fragment_caps(
    [("CLAUDE.md", 10, 0), ("shared/a.md", 101, 1)], 100)
check("a fragment over the cap fails", over)
check("a breach names the file", "shared/a.md" in text)
check("a breach reports by how much", "(+1)" in text)
# The remedy this message prescribes -- a `.cases.md` split -- is itself the
# operation that strands positional references, and that defect is invisible
# to every other check here. So the message that triggers the split names the
# sweep, per shared/writing/reorganize-prose.md.
# Pin the WHOLE canonical pattern, not a prefix of it: a substring
# assertion on the leading alternatives passes against a sweep narrowed to
# them, which is the failure forward-references.md's own section describes.
check("a breach names the positional-reference sweep",
      r"\b(above|below|here|earlier|later)\b|this (section|file)" in text)
check("a breach names the remedy, not just the sweep",
      "naming its subject" in text)
# A clean run must not print the sweep, or the advice detaches from the
# moment it applies to and becomes noise every reader learns to skip.
_, clean_text = ccc.render_fragment_caps(
    [("CLAUDE.md", 10, 0), ("shared/a.md", 10, 1)], 100)
check("a clean run does not print the sweep",
      "above|below|here|earlier|later" not in clean_text)

over, text = ccc.render_fragment_caps(
    [("CLAUDE.md", 10, 0), ("shared/a.md", 100, 1)], 100)
check("a fragment exactly at the cap passes", not over)

# Reports what it examined, not only what it found: a walk that resolved no
# fragments and a corpus with none over the cap both print zero breaches
# otherwise, per shared/principles/fail-fast.md.
over, text = ccc.render_fragment_caps([("CLAUDE.md", 10, 0)], 100)
check("no fragments still reports the examined count", not over
      and "0 fragment(s) examined" in text)

over, text = ccc.render_fragment_caps(
    [("shared/a.md", 300, 1), ("shared/b.md", 200, 1), ("shared/c.md", 10, 2)],
    100,
)
check("every breach is reported, not just the largest", over
      and "shared/a.md" in text and "shared/b.md" in text)
check("breaches are ordered largest first",
      text.index("shared/a.md") < text.index("shared/b.md"))
check("a fragment under the cap is not listed", "shared/c.md" not in text)
check("the examined count covers every depth below the root",
      "3 fragment(s) examined" in text)

# The gate is NOT --strict-gated: unlike the advisory byte budget, a
# fragment over the cap fails on its own, so a run that never passes
# --strict still returns 1.
with tempfile.TemporaryDirectory() as d:
    base = Path(d)
    (base / "CLAUDE.md").write_text("@big.md\n")
    (base / "big.md").write_text("x" * 500)
    check(
        "a fragment over the cap fails without --strict",
        ccc.main(
            ["--base", str(base), "--budget", "100000000", "--fragment-cap", "100"]
        ) == 1,
    )
    check(
        "the same closure passes under a cap it fits",
        ccc.main(
            ["--base", str(base), "--budget", "100000000", "--fragment-cap", "1000"]
        ) == 0,
    )

check(
    "--fragment-cap rejects zero, like the other positive_int thresholds",
    _fc_rejects_zero(),
)

# --- --baseline: this repo's own per-PR closure delta -----------------------
# Distinct from --compare, which needs a submodule gitlink. The fixture is a
# single repo with two commits, so the closure genuinely differs between the
# baseline rev and the working tree.

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / "CLAUDE.md").write_text("@frag.md\n", encoding="utf-8")
    (base / "frag.md").write_text("short", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=base, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=base, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=base, check=True)
    subprocess.run(["git", "add", "-A"], cwd=base, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=base, check=True)
    first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=base, capture_output=True, text=True
    ).stdout.strip()
    # Grow the fragment in the working tree only; the baseline rev keeps "short".
    (base / "frag.md").write_text("a considerably longer fragment", encoding="utf-8")

    at_base, _, _, _ = ccc.walk_closure("CLAUDE.md", ccc.baseline_reader(base, first))
    in_tree, _, _, _ = ccc.walk_closure("CLAUDE.md", ccc.local_reader(base))
    check(
        "baseline_reader resolves this repo's own files at the given rev",
        sum(n for _, n, _ in at_base) < sum(n for _, n, _ in in_tree),
    )
    # An ABSOLUTE import points outside the repo, so no revision of this repo
    # has a version of it and it must fall through to disk -- the same
    # fall-through `local_reader` and `submodule_reader` already do, and the
    # same set `resolve()` calls "already absolute". Routing it to
    # `git show REV:/abs/path` fails outright, which reported a file that is
    # present and unchanged as dangling and excluded its bytes from the
    # baseline, inflating the growth by that file's full size on every run.
    _abs = base / "outside.md"
    _abs.write_text("z" * 300, encoding="utf-8")
    for _spelling, _label in (
        (str(_abs), "/-prefixed"),
        ("~/.nonexistent-xyz.md", "~-prefixed"),
        ("C:/Users/test/file.md", "drive-letter-prefixed"),
    ):
        _r = ccc.baseline_reader(base, first)(_spelling)
        _l = ccc.local_reader(base)(_spelling)
        check(
            f"baseline_reader routes an {_label} import to disk, like local_reader",
            _r == _l,
        )
    check(
        "the import list is unchanged across revs, only weights differ",
        [p for p, _, _ in at_base] == [p for p, _, _ in in_tree],
    )

    common = ["--base", str(base), "--budget", "100000000"]
    check(
        "--baseline alone is advisory and exits 0",
        ccc.main(common + ["--baseline", first]) == 0,
    )
    # The growth here is len("a considerably longer fragment") - len("short") = 25.
    check(
        "--max-growth fails when the closure grew past the limit",
        ccc.main(common + ["--baseline", first, "--max-growth", "10"]) == 1,
    )
    check(
        "--max-growth passes when the growth fits",
        ccc.main(common + ["--baseline", first, "--max-growth", "100"]) == 0,
    )
    check(
        "--max-growth is exclusive, so a limit equal to the growth passes",
        ccc.main(common + ["--baseline", first, "--max-growth", "25"]) == 0,
    )
    # The dangerous case: an unresolvable rev makes every file read as absent,
    # so a naive implementation reports the WHOLE closure as growth. It must
    # be a hard error instead, per fail-fast.md.
    check(
        "an unresolvable baseline rev is a hard error, not a huge fake delta",
        ccc.main(common + ["--baseline", "no-such-rev-xyz"]) == 2,
    )
    check(
        "--max-growth without --baseline is refused rather than silently inert",
        ccc.main(common + ["--max-growth", "10"]) == 2,
    )
    # Assert the MESSAGE, not just the exit code. This fixture has no
    # `.ai-config` gitlink, so `--compare` exits 2 on its own for an unrelated
    # reason -- an exit-code-only check passes identically whether or not the
    # ambiguity guard exists, which mutation testing confirmed (removing the
    # guard changed nothing). "Passes by coincidental balance" is ardi.md's
    # phrase for this; fail-fast.md covers the general shape, a check whose
    # failure path and whose pass path produce the same observable.
    import contextlib as _ctx
    from io import StringIO as _SIO

    _err = _SIO()
    with _ctx.redirect_stdout(_SIO()), _ctx.redirect_stderr(_err):
        _rc = ccc.main(common + ["--baseline", first, "--compare", first])
    check(
        "--baseline with --compare is refused as ambiguous, by that guard",
        _rc == 2 and "answer different questions" in _err.getvalue(),
    )
    # A self-baseline is the negative control: same tree both sides, so any
    # non-zero delta would mean the reader is not reading what local_reader does.
    subprocess.run(["git", "add", "-A"], cwd=base, check=True)
    subprocess.run(["git", "commit", "-qm", "grown"], cwd=base, check=True)
    check(
        "a self-baseline reports zero growth under a zero limit",
        ccc.main(common + ["--baseline", "HEAD", "--max-growth", "0"]) == 0,
    )
    # The exit-code half is asserted above; per fail-fast.md, the message has
    # to name the rev too, or a typo'd ref and a missing root file read alike.
    _err = _SIO()
    with _ctx.redirect_stdout(_SIO()), _ctx.redirect_stderr(_err):
        _rc = ccc.main(common + ["--baseline", "no-such-rev-xyz"])
    check(
        "the unresolvable-rev error names the rev it could not read",
        _rc == 2 and "no-such-rev-xyz" in _err.getvalue(),
    )

check(
    "render_delta labels its rows from its arguments, not a hard-coded pair",
    "at REV" in ccc.render_delta(10, 20, 4, "T", "at REV", "working tree")
    and "working tree" in ccc.render_delta(10, 20, 4, "T", "at REV", "working tree"),
)


def _byte_cols(text):
    """Offsets where a row's byte column ends (the ' B' after each number)."""
    return {line.index(" B") for line in text.splitlines() if " B" in line}


_grow = ccc.render_delta(1000, 2000, 4, "T", "before", "after")
_shrink = ccc.render_delta(2000, 1000, 4, "T", "before", "after")
check(
    "a positive and a negative delta end their byte column at the same offset",
    # One offset within each rendering, and the same offset across the two:
    # a manual sign prefix spends a column the '-' of a negative number takes
    # from the field itself, so the two cases came out a character apart.
    _byte_cols(_grow) == _byte_cols(_shrink) and len(_byte_cols(_grow)) == 1,
)
_save = ccc.render_delta(2001, 1000, 4, "T", "before", "after")
check(
    "a shrink's token column reports the bytes saved, not one more",
    # -1001 B at 4 B/tok is 250 tokens saved; `//` floors toward negative
    # infinity and reported 251, so a trim over-claimed its own saving.
    "-250 tok" in _save and "-251" not in _save,
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
