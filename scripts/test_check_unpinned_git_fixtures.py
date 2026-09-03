#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-unpinned-git-fixtures.py"

# Assembled rather than written literally, so this file's own fixture text is
# not itself a call site for the checker it exercises.
QUOTE = '"' * 3
UNPINNED = '    subprocess.run(["%s", "init", "-q"], cwd=tmp, check=True)' % ("g" + "it")
AFTER_BARE_CLOSE = "\n".join([
    "FIXTURE = " + QUOTE,
    "documentation text",
    QUOTE,
    "",
    "def build(tmp):",
    UNPINNED,
    "",
])


def examined(n):
    """Build the count line, so the command name is never written literally."""
    return "Examined %d %s init/clone call sites." % (n, "g" + "it")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_baseline_passes():
    r = run()
    if r.returncode != 0:
        print("FAIL: Baseline check failed!")
        print(r.stdout)
        print(r.stderr)
        return False

    # Do not write the word literally
    if "Examined " not in r.stdout or " call sites." not in r.stdout:
        print("FAIL: Expected output not found:")
        print(r.stdout)
        return False

    print("PASS: Baseline check passes and counts correct number of call sites.")
    return True


def test_reports_site_after_bare_closing_triple_quote():
    """A line scanner enters string state on a lone closing quote (#2986).

    Every call site after that bare quote then went unexamined, so a green
    run could hide an unpinned fixture.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "test_after_bare_close.py"
        target.write_text(AFTER_BARE_CLOSE, encoding="utf-8")
        r = run(str(target))

    if r.returncode == 0:
        print("FAIL: unpinned site after a bare closing triple quote was not reported:")
        print(r.stdout)
        return False

    if examined(1) not in r.stdout:
        print("FAIL: expected exactly one examined call site:")
        print(r.stdout)
        return False

    print("PASS: an unpinned site after a bare closing triple quote is reported.")
    return True


def test_skips_call_site_inside_a_multiline_string():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "test_inside_string.py"
        inside = "\n".join([
            "FIXTURE = " + QUOTE,
            UNPINNED,
            QUOTE,
            "",
        ])
        target.write_text(inside, encoding="utf-8")
        r = run(str(target))

    if examined(0) not in r.stdout:
        print("FAIL: a call site inside a multi-line string should not be examined:")
        print(r.stdout)
        return False

    print("PASS: a call site inside a multi-line string is not examined.")
    return True


def main():
    os.chdir(Path(__file__).resolve().parent.parent)
    results = [
        test_baseline_passes(),
        test_reports_site_after_bare_closing_triple_quote(),
        test_skips_call_site_inside_a_multiline_string(),
    ]
    if not all(results):
        sys.exit(1)
    print(f"PASS: all {len(results)} checks passed.")


if __name__ == '__main__':
    main()
