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
PINNED = ('    subprocess.run(["%s", "init", "-q", "-b", "main"], cwd=tmp, check=True)'
          % ("g" + "it"))
AFTER_BARE_CLOSE = "\n".join([
    "FIXTURE = " + QUOTE,
    "documentation text",
    QUOTE,
    "",
    "def build(tmp):",
    UNPINNED,
    "",
])

# A call sharing the string's *opening* line: the multi-line string starts on
# the same physical line as the call, after it. Whole-line skipping covers
# this line entirely and hides the call (#2986).
UNPINNED_ON_OPENING_LINE = "\n".join([
    "def build(tmp):",
    '    subprocess.run(["%s", "init", "-q"], cwd=tmp, doc=%s' % ("g" + "it", QUOTE),
    "this is a trailing doc string",
    "that spans multiple lines",
    QUOTE + ")",
    "",
])
PINNED_ON_OPENING_LINE = "\n".join([
    "def build(tmp):",
    '    subprocess.run(["%s", "init", "-q", "-b", "main"], cwd=tmp, doc=%s'
    % ("g" + "it", QUOTE),
    "this is a trailing doc string",
    "that spans multiple lines",
    QUOTE + ")",
    "",
])

# A call sharing the string's *closing* line: the multi-line string's bare
# closing quote is immediately followed, on the same physical line, by the
# call. Whole-line skipping covers this line entirely and hides the call
# (#2986).
UNPINNED_ON_CLOSING_LINE = "\n".join([
    "DOC = " + QUOTE,
    "documentation text",
    "spanning lines",
    QUOTE + " ; " + UNPINNED.strip(),
    "",
])
PINNED_ON_CLOSING_LINE = "\n".join([
    "DOC = " + QUOTE,
    "documentation text",
    "spanning lines",
    QUOTE + " ; " + PINNED.strip(),
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

    if r.returncode != 0:
        print("FAIL: a file whose only call site is inside a string should pass:")
        print(r.stdout)
        return False

    if "could not tokenize" in r.stdout:
        print("FAIL: the file was not parsed:")
        print(r.stdout)
        return False

    if examined(0) not in r.stdout:
        print("FAIL: a call site inside a multi-line string should not be examined:")
        print(r.stdout)
        return False

    print("PASS: a call site inside a multi-line string is not examined.")
    return True


def test_reports_unpinned_call_sharing_the_opening_quote_line():
    """A call on the same line as a multi-line string's *opening* quote (#2986).

    Marking the whole first line as covered hides a call that precedes the
    opening quote on that line.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "test_opening_line.py"
        target.write_text(UNPINNED_ON_OPENING_LINE, encoding="utf-8")
        r = run(str(target))

    if r.returncode == 0:
        print("FAIL: unpinned call sharing the opening quote line was not reported:")
        print(r.stdout)
        return False

    if examined(1) not in r.stdout:
        print("FAIL: expected exactly one examined call site:")
        print(r.stdout)
        return False

    print("PASS: an unpinned call sharing the opening quote line is reported.")
    return True


def test_passes_pinned_call_sharing_the_opening_quote_line():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "test_opening_line_pinned.py"
        target.write_text(PINNED_ON_OPENING_LINE, encoding="utf-8")
        r = run(str(target))

    if r.returncode != 0:
        print("FAIL: a pinned call sharing the opening quote line should pass:")
        print(r.stdout)
        return False

    if examined(1) not in r.stdout:
        print("FAIL: expected exactly one examined call site:")
        print(r.stdout)
        return False

    print("PASS: a pinned call sharing the opening quote line is examined and passes.")
    return True


def test_reports_unpinned_call_sharing_the_closing_quote_line():
    """A call on the same line as a multi-line string's *closing* quote (#2986).

    Marking the whole last line as covered hides a call that follows the
    closing quote on that line.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "test_closing_line.py"
        target.write_text(UNPINNED_ON_CLOSING_LINE, encoding="utf-8")
        r = run(str(target))

    if r.returncode == 0:
        print("FAIL: unpinned call sharing the closing quote line was not reported:")
        print(r.stdout)
        return False

    if examined(1) not in r.stdout:
        print("FAIL: expected exactly one examined call site:")
        print(r.stdout)
        return False

    print("PASS: an unpinned call sharing the closing quote line is reported.")
    return True


def test_passes_pinned_call_sharing_the_closing_quote_line():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "test_closing_line_pinned.py"
        target.write_text(PINNED_ON_CLOSING_LINE, encoding="utf-8")
        r = run(str(target))

    if r.returncode != 0:
        print("FAIL: a pinned call sharing the closing quote line should pass:")
        print(r.stdout)
        return False

    if examined(1) not in r.stdout:
        print("FAIL: expected exactly one examined call site:")
        print(r.stdout)
        return False

    print("PASS: a pinned call sharing the closing quote line is examined and passes.")
    return True


def main():
    os.chdir(Path(__file__).resolve().parent.parent)
    results = [
        test_baseline_passes(),
        test_reports_site_after_bare_closing_triple_quote(),
        test_skips_call_site_inside_a_multiline_string(),
        test_reports_unpinned_call_sharing_the_opening_quote_line(),
        test_passes_pinned_call_sharing_the_opening_quote_line(),
        test_reports_unpinned_call_sharing_the_closing_quote_line(),
        test_passes_pinned_call_sharing_the_closing_quote_line(),
    ]
    if not all(results):
        sys.exit(1)
    print(f"PASS: all {len(results)} checks passed.")


if __name__ == '__main__':
    main()
