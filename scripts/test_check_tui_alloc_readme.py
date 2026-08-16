#!/usr/bin/env python3
"""Tests for check-tui-alloc-readme.py.

Mutation-tested per `shared/workflow/algorithmatize-checks.md`: each
drift mutation is asserted to have actually applied (the mutant differs
from the original and carries the injected value) before its verdict is
scored, and each failure's message must name the drifted field, so a
failure is attributable rather than merely non-zero.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts/check-tui-alloc-readme.py"
SCRIPT = ROOT / "dotfiles/shiva/bin/tui-alloc"
README = ROOT / "dotfiles/shiva/config/tui-alloc/README.md"

failures = []


def run(script: Path, readme: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), "--script", str(script),
         "--readme", str(readme)],
        capture_output=True, text=True)


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "ok" if cond else "FAIL"
    print(f"{status:4} {name}" + (f" -- {detail}" if not cond else ""))
    if not cond:
        failures.append(name)


def main() -> None:
    script_text = SCRIPT.read_text(encoding="utf-8")
    readme_text = README.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1. The live corpus is the known-clean control: main is green,
        # so the real files must agree (a failing run here means either
        # real drift or a broken check -- both worth failing the suite).
        r = run(SCRIPT, README)
        check("live corpus passes", r.returncode == 0,
              f"rc={r.returncode} out={r.stdout!r} err={r.stderr!r}")
        check("live run reports its denominator",
              "Compared 4 defaults" in r.stdout, r.stdout)

        # 2. Known-positive controls: mutate each script default and
        # require exit 1 with the field named. Field -> (old, new).
        mutations = {
            "cpus": ("${ALLOC_CPUS:-8}", "${ALLOC_CPUS:-16}"),
            "mem": ("${ALLOC_MEM:-32G}", "${ALLOC_MEM:-64G}"),
            "time": ("${ALLOC_TIME:-48:00:00}", "${ALLOC_TIME:-72:00:00}"),
            "exclude": ("--exclude=c1", "--exclude=c2"),
        }
        for field, (old, new) in mutations.items():
            mutant = script_text.replace(old, new)
            check(f"mutation applied: {field}",
                  mutant != script_text and new in mutant,
                  f"pattern {old!r} not found in script")
            mpath = tmp / f"tui-alloc-{field}"
            mpath.write_text(mutant, encoding="utf-8")
            r = run(mpath, README)
            check(f"drift caught: {field}",
                  r.returncode == 1 and field in r.stdout,
                  f"rc={r.returncode} out={r.stdout!r}")

        # 3. Parse failures exit 2, never 0 -- a reshaped file must not
        # read as agreement (fail-fast: the vacuous pass is the defect).
        gutted_script = script_text.replace("${ALLOC_TIME:-48:00:00}",
                                            "$ALLOC_TIME")
        check("gut mutation applied", gutted_script != script_text)
        gpath = tmp / "tui-alloc-gutted"
        gpath.write_text(gutted_script, encoding="utf-8")
        r = run(gpath, README)
        check("script parse failure exits 2",
              r.returncode == 2 and "parse failure" in r.stderr,
              f"rc={r.returncode} err={r.stderr!r}")

        gutted_readme = readme_text.replace("defaults:", "typical values:")
        check("readme gut mutation applied", gutted_readme != readme_text)
        rpath = tmp / "README-gutted.md"
        rpath.write_text(gutted_readme, encoding="utf-8")
        r = run(SCRIPT, rpath)
        check("readme parse failure exits 2",
              r.returncode == 2 and "parse failure" in r.stderr,
              f"rc={r.returncode} err={r.stderr!r}")

        # 4. Time compaction: a non-whole-hour default must not compact,
        # so a README stating the compact form for it is drift.
        odd_time = script_text.replace("${ALLOC_TIME:-48:00:00}",
                                       "${ALLOC_TIME:-36:30:00}")
        check("odd-time mutation applied", "36:30:00" in odd_time)
        opath = tmp / "tui-alloc-oddtime"
        opath.write_text(odd_time, encoding="utf-8")
        r = run(opath, README)
        check("non-whole-hour time compared raw, caught as drift",
              r.returncode == 1 and "36:30:00" in r.stdout,
              f"rc={r.returncode} out={r.stdout!r}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # 5. A comment-only change must not move the verdict: the header
        # comment's usage example quotes an --exclude value, and an
        # unanchored pattern matched it instead of the real flag (caught
        # by check 1 before first merge -- this pins the fix).
        comment_only = script_text.replace("--exclude=c1,c2",
                                           "--exclude=c9,c8")
        check("comment-only mutation applied",
              comment_only != script_text and "c9,c8" in comment_only)
        cpath = tmp / "tui-alloc-comment"
        cpath.write_text(comment_only, encoding="utf-8")
        r = run(cpath, README)
        check("comment example is not read as the flag",
              r.returncode == 0, f"rc={r.returncode} out={r.stdout!r}")

    n = 14
    print(f"{n - len(failures)}/{n} checks passed")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
