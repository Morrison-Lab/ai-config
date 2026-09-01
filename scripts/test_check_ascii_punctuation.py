#!/usr/bin/env python3
"""Tests for scripts/check-ascii-punctuation.py (ai-config#2550).

Verifies that:
1. The 7 banned punctuation glyphs (em-dash, en-dash, curly quotes, multiplication sign)
   fail the gate in source files (.py, .R, .qmd, etc.).
2. Legitimate non-banned Unicode (e.g. accents, emojis, status symbols) does not fail.
3. The check is working-tree aware in diff mode (detecting uncommitted edits,
   staged changes, branch commits, and untracked files).
4. The search space is reported accurately (file and line/added line counts).
5. Running in diff mode against an empty diff refuses to report false success (exits 2).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-ascii-punctuation.py"

passes = 0
failures = 0


def check(name: str, cond: bool) -> None:
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


def run_script(*args, cwd: Path = REPO) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    print("Testing check-ascii-punctuation.py...")

    # Banned glyphs assembled via chr() to keep this test file ASCII-clean.
    EM_DASH = chr(0x2014)
    EN_DASH = chr(0x2013)
    LEFT_DOUBLE_QUOTE = chr(0x201C)
    RIGHT_DOUBLE_QUOTE = chr(0x201D)
    LEFT_SINGLE_QUOTE = chr(0x2018)
    RIGHT_SINGLE_QUOTE = chr(0x2019)
    MULT_SIGN = chr(0x00D7)

    # 1. Whole-tree scan over clean files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "clean.py").write_text("# Clean python file\ndef foo():\n    return 42\n", encoding="utf-8")
        code, out, err = run_script(str(tmp / "clean.py"))
        check("clean python file passes with exit 0", code == 0)
        check("...and reports 1 file, 3 lines", "Checked 1 file(s), 3 line(s)" in out)

    # 2. Each banned glyph fails with exit 1
    banned_samples = [
        (EM_DASH, "EM DASH (U+2014)"),
        (EN_DASH, "EN DASH (U+2013)"),
        (LEFT_DOUBLE_QUOTE, "LEFT DOUBLE QUOTATION MARK (U+201C)"),
        (RIGHT_DOUBLE_QUOTE, "RIGHT DOUBLE QUOTATION MARK (U+201D)"),
        (LEFT_SINGLE_QUOTE, "LEFT SINGLE QUOTATION MARK (U+2018)"),
        (RIGHT_SINGLE_QUOTE, "RIGHT SINGLE QUOTATION MARK (U+2019)"),
        (MULT_SIGN, "MULTIPLICATION SIGN (U+00D7)"),
    ]
    for glyph, name in banned_samples:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            f = tmp / "bad.py"
            f.write_text(f"# comment with {glyph}\nx = 1\n", encoding="utf-8")
            code, out, err = run_script(str(f))
            check(f"file containing {name} fails with exit 1", code == 1)
            check(f"...and stderr names {name}", name in err)
            check("...and stderr reports file and line", "bad.py:1:" in err)

    # 3. Non-banned Unicode characters do NOT trigger the gate
    non_banned_samples = [
        ("résumé", "accented latin text"),
        (chr(0x2713), "checkmark status symbol"),
        (chr(0x2192), "right arrow symbol"),
        (chr(0x1F6D1), "octagonal stop sign emoji"),
        (chr(0x2022), "bullet symbol"),
    ]
    for char, label in non_banned_samples:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            f = tmp / "unicode.py"
            f.write_text(f"# valid unicode: {char}\nx = '{char}'\n", encoding="utf-8")
            code, out, err = run_script(str(f))
            check(f"non-banned unicode ({label}) passes cleanly", code == 0)

    # 4. JSON output format
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        f = tmp / "test.py"
        f.write_text(f"line_1 = 'ok'\nline_2 = 'bad {EM_DASH}'\n", encoding="utf-8")
        code, out, err = run_script(str(f), "--json")
        check("--json exits 1 on violation", code == 1)
        data = json.loads(out)
        check("--json status is 'violations'", data["status"] == "violations")
        check("--json files_examined is 1", data["files_examined"] == 1)
        check("--json lines_examined is 2", data["lines_examined"] == 2)
        check("--json violations_count is 1", data["violations_count"] == 1)
        check("--json violation details match line 2", data["violations"][0]["line"] == 2)

    # 5. Diff mode and working-tree awareness
    with tempfile.TemporaryDirectory() as git_tmp:
        repo = Path(git_tmp)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

        # Base commit
        (repo / "base.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        subprocess.run(["git", "add", "base.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)

        # 5a. Empty diff against base reports empty search space and exits 2
        code, out, err = run_script("--diff", "--base", "main", cwd=repo)
        check("empty diff against base exits 2", code == 2)
        check("...and reports 0 files and 0 added lines examined", "0 files and 0 added lines examined" in err)

        # 5b. Uncommitted working-tree edit with em-dash fails exit 1
        (repo / "base.py").write_text(f"x = 1\ny = 2\nz = 'uncommitted {EM_DASH}'\n", encoding="utf-8")
        code, out, err = run_script("--diff", "--base", "main", cwd=repo)
        check("uncommitted working-tree addition with em-dash fails exit 1", code == 1)
        check("...and reports violation in base.py", "base.py:3:" in err)

        # 5c. Clean uncommitted edit passes exit 0
        (repo / "base.py").write_text("x = 1\ny = 2\nz = 'clean uncommitted'\n", encoding="utf-8")
        code, out, err = run_script("--diff", "--base", "main", cwd=repo)
        check("clean uncommitted working-tree addition passes exit 0", code == 0)
        check("...and reports 1 file and 1 added line examined", "Checked 1 file(s), 1 added line(s)" in out)

        # 5d. Staged change with em-dash fails exit 1
        subprocess.run(["git", "add", "base.py"], cwd=repo, check=True)
        (repo / "base.py").write_text(f"x = 1\ny = 2\nz = 'staged {EM_DASH}'\n", encoding="utf-8")
        subprocess.run(["git", "add", "base.py"], cwd=repo, check=True)
        code, out, err = run_script("--diff", "--base", "main", cwd=repo)
        check("staged addition with em-dash fails exit 1", code == 1)

        # 5e. Committed change with em-dash fails exit 1
        subprocess.run(["git", "commit", "-q", "-m", "commit with em-dash"], cwd=repo, check=True)
        code, out, err = run_script("--diff", "--base", "HEAD~1", cwd=repo)
        check("committed change on branch with em-dash fails exit 1", code == 1)

        # 5f. Untracked file with em-dash is detected in diff mode
        (repo / "untracked.py").write_text(f"new_code = '{EM_DASH}'\n", encoding="utf-8")
        code, out, err = run_script("--diff", "--base", "HEAD", cwd=repo)
        check("untracked file with em-dash is detected in diff mode", code == 1)
        check("...and names untracked.py", "untracked.py:1:" in err)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
