#!/usr/bin/env python3
"""Regression tests for check-memory-file-size.py."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "cmfs", Path(__file__).parent / "check-memory-file-size.py"
)
cmfs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmfs)

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


def make_repo(tmpdir: Path) -> Path:
    scripts_dir = tmpdir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "check-memory-file-size.py").write_text(
        (Path(__file__).parent / "check-memory-file-size.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    memories = tmpdir / "memories"
    memories.mkdir()
    (memories / "session").mkdir()

    # 60 lines: 3 sections of 20.
    small = "# Small\n\n" + "".join(
        f"## Section {i}\n" + "a bullet\n" * 19 for i in range(3)
    )
    # 122 lines: the "Huge" section is the clear outlier, so it should head
    # the report's per-file section list.
    big = "# Big\n\n" + "## Tiny\n" + "x\n" * 19 + "## Huge\n" + "y\n" * 99
    # 95 lines: inside the warning band for `--max-lines 100`, whose
    # default warn threshold is round(100 * 0.92) == 92. Under the cap, so it
    # must never appear as a breach.
    near = "# Near\n" + "z\n" * 94
    # 92 and 91 lines: the two files straddling that same warn threshold, so
    # the band's lower edge is pinned. Without them an off-by-one there --
    # `warn_lines < len(lines)` instead of `<=` -- silently drops the file
    # sitting exactly at the threshold and no assertion notices.
    edge = "# Edge\n" + "z\n" * 91
    under = "# Under\n" + "z\n" * 90
    (memories / "small.md").write_text(small, encoding="utf-8")
    (memories / "near.md").write_text(near, encoding="utf-8")
    (memories / "edge.md").write_text(edge, encoding="utf-8")
    (memories / "under.md").write_text(under, encoding="utf-8")
    (memories / "big.md").write_text(big, encoding="utf-8")
    (memories / "MEMORY.md").write_text("# index\n" + "row\n" * 200, encoding="utf-8")
    (memories / "session" / "notes.md").write_text("# s\n" + "n\n" * 200, "utf-8")

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmpdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmpdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmpdir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmpdir, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmpdir, check=True)
    return tmpdir


def run_check(repo: Path, *args: str):
    result = subprocess.run(
        [sys.executable, "scripts/check-memory-file-size.py", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout, result.returncode


with tempfile.TemporaryDirectory() as tmp:
    repo = make_repo(Path(tmp))

    out, code = run_check(repo, "--max-lines", "100")
    check("flags the file over the threshold", "memories/big.md: 122 lines" in out)
    check("leaves the file under the threshold alone", "small.md" not in out)
    check("advisory mode exits 0 despite a finding", code == 0)
    check("names the largest section as a split candidate", "## Huge" in out)
    check(
        "orders sections largest first",
        out.index("## Huge") < out.index("## Tiny"),
    )

    out, code = run_check(repo, "--max-lines", "100", "--strict")
    check("--strict exits non-zero on a finding", code == 1)

    out, code = run_check(repo, "--max-lines", "500")
    check("clean corpus reports no findings", "No memory file exceeds" in out)
    check("clean corpus exits 0", code == 0)

    # The warning band (ai-config#3102). Reporting only the breach is what
    # made the check arrive too late to act on, so the band has to print in
    # the clean case too -- that is the case the old output could not
    # distinguish from an empty corpus.
    out, code = run_check(repo, "--max-lines", "100")
    check(
        "warns on a file approaching the cap",
        "memories/near.md: 95 lines" in out,
    )
    check("reports the remaining headroom", "(5 lines of headroom)" in out)
    # The breach format is "<path>: <n> lines" with nothing after it, so the
    # absence of that line is what proves the warned file was not also
    # reported as over the cap.
    check(
        "the approaching file is not reported as a breach",
        "near.md: 95 lines\n" not in out,
    )
    check(
        "warns on a file at exactly the warn threshold",
        "memories/edge.md: 92 lines (8 lines of headroom)" in out,
    )
    check(
        "leaves the file one line below the warn threshold alone",
        "under.md" not in out,
    )

    out, code = run_check(repo, "--max-lines", "122")
    check(
        "warns even when nothing breached",
        "No memory file exceeds" in out
        and "memories/big.md: 122 lines" in out,
    )
    check("a warning alone still exits 0", code == 0)

    # A file AT the cap warns rather than breaching: the failure fires
    # strictly above --max-lines, and that file is exactly the one that
    # cannot take another line.
    check(
        "a file at exactly the cap warns with 0 headroom",
        "memories/big.md: 122 lines (0 lines of headroom)" in out,
    )

    _, code = run_check(repo, "--max-lines", "122", "--strict")
    check("a warning alone exits 0 under --strict", code == 0)

    out, _ = run_check(repo, "--max-lines", "500", "--warn-fraction", "0.99")
    check(
        "--warn-fraction moves the band",
        "No memory file is within 5 lines of the cap." in out,
    )

    # An over-cap file is past the cap, not near it, so the empty-band line
    # would read as contradicting the breach printed directly above it.
    out, _ = run_check(repo, "--max-lines", "100", "--warn-fraction", "0.99")
    check(
        "no empty-band line alongside a breach",
        "memories/big.md: 122 lines" in out and "is within" not in out,
    )

    _, code = run_check(repo, "--max-lines", "100", "--warn-fraction", "1")
    check("rejects a --warn-fraction of 1", code == 2)
    _, code = run_check(repo, "--max-lines", "100", "--warn-fraction", "0")
    check("rejects a --warn-fraction of 0", code == 2)

    # MEMORY.md (the index) and session/ notes are both over any threshold
    # used above, so their absence from the findings proves the exclusions
    # apply. Match the "<path>: <n> lines" finding format specifically --
    # the report's closing advice mentions memories/MEMORY.md by name, so a
    # bare substring test would false-fail.
    out, _ = run_check(repo, "--max-lines", "100")
    check("excludes the MEMORY.md index", "MEMORY.md: " not in out)
    check("excludes session/ notes", "session/notes.md: " not in out)

    # Prove the session/ exclusion is load-bearing rather than dead code:
    # a DEFAULT git pathspec wildcard matches `/`, so `git ls-files --
    # "memories/*.md"` does return nested paths and the prefix filter is what
    # removes them. (It is the explicit `:(glob)` magic that stops `*` from
    # matching `/` -- not the default.) Asserting both halves means a future
    # reader does not have to take either claim on trust.
    listed = subprocess.run(
        ["git", "ls-files", "--", "memories/*.md"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.split()
    check(
        "default pathspec DOES return nested session/ paths",
        "memories/session/notes.md" in listed,
    )
    globbed = subprocess.run(
        ["git", "ls-files", "--", ":(glob)memories/*.md"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.split()
    check(
        ":(glob) magic is what stops * from matching /",
        "memories/session/notes.md" not in globbed,
    )

check(
    "warn threshold applies the fraction of the cap",
    cmfs.warn_line_threshold(1250, 0.92) == 1150,
)
# The default's product is exactly 1150.0, so the assertion above holds under
# truncation, flooring and ceiling alike and says nothing about the rounding.
# These two inputs are where those disagree: 1250 * 0.9207 is 1150.875, which
# truncates to 1150 and rounds to 1151; 100 * 0.925 is exactly 92.5, which
# ceils to 93 and rounds to 92 under Python's round-half-to-even. Together
# they pin `round` against each neighbouring rule a later edit might reach for.
check(
    "warn threshold rounds a non-integral product up, not down",
    cmfs.warn_line_threshold(1250, 0.9207) == 1151,
)
check(
    "warn threshold rounds a .5 product half-to-even",
    cmfs.warn_line_threshold(100, 0.925) == 92,
)

# The real corpus must stay under the shipped default, or the check ships red.
findings = cmfs.oversized_files(
    cmfs.measured_files("memories"), cmfs.DEFAULT_MAX_LINES
)
check(
    f"this repo's own memories/ is under the {cmfs.DEFAULT_MAX_LINES}-line default",
    not findings,
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
