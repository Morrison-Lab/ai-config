#!/usr/bin/env python3
"""Tests for scripts/check-python-escapes.py (ai-config#3114).

Verifies that:
1. The live tree passes, and the summary reports a non-empty denominator.
2. A non-raw literal carrying an unrecognized backslash sequence is flagged,
   in a docstring as well as in ordinary code --- the docstring case is the
   corpus's actual exposure, since these modules quote regex source in prose.
3. A raw literal and a doubled backslash are not flagged.
4. Detection does not depend on the warning CATEGORY or on the ambient
   warnings filter. Python 3.11 raises DeprecationWarning, silent by default,
   while 3.12 and later raise SyntaxWarning; a category-keyed scan would pass
   vacuously on one of them, and a filter-dependent scan would pass under
   PYTHONWARNINGS=ignore. The category half is checked by calling the
   predicate directly, since one interpreter can only ever raise one of the
   two categories.
5. An empty search space fails rather than reporting a vacuous clean --- the
   negative control the issue asks for.
6. A file that does not compile is reported rather than swallowed.

Every fixture below writes its backslash through a valid escape in THIS file,
so the suite stays clean under the very check it exercises.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-python-escapes.py"

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


def run_script(*args: str, env: dict | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    print("Testing check-python-escapes.py...")

    # 1. The live tree is clean, and the denominator is reported and non-zero.
    code, out, err = run_script()
    check("the tracked tree passes", code == 0)
    check("the summary reports what was examined", "Examined " in out)
    examined = 0
    for token in out.replace(";", " ").split():
        if token.isdigit():
            examined = int(token)
            break
    check("the denominator is non-zero", examined > 0)
    check("nothing is written to stderr on a clean run", err == "")

    # The denominator has to be RIGHT, not merely non-zero. A pathspec that
    # regressed to a subdirectory would still report a non-empty search space
    # while the gate scanned a fraction of the corpus --- the undercount the
    # empty-search-space guard cannot see. Derive the expected count
    # independently rather than asserting a literal that goes stale.
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", "*.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    expected = len([name for name in listed.stdout.split(chr(0)) if name])
    check("the denominator matches the tracked .py count", examined == expected)

    # And the default path needs a positive detection test, not only a clean
    # one: every other must-flag fixture below is reached through an explicit
    # path argument, which returns before the tracked-tree enumeration runs.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "scripts").mkdir()
        copied = repo / "scripts" / SCRIPT.name
        copied.write_bytes(SCRIPT.read_bytes())
        write(repo, "offender.py", 'PATTERN = "^a\\s+b$"\n')
        for cmd in (
            ["git", "init", "-q"],
            ["git", "add", "-A"],
        ):
            subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
        proc = subprocess.run(
            [sys.executable, str(copied)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        check("the tracked-tree path flags an offender", proc.returncode == 1)
        check(
            "the tracked-tree path names the offender",
            "offender.py" in proc.stdout,
        )
        check(
            "the tracked-tree path counts every tracked file",
            "Examined 2 " in proc.stdout,
        )

    # 2. A non-raw literal with an unrecognized backslash sequence is flagged.
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        write(d, "bad_code.py", 'PATTERN = "^a\\s+b$"\n')
        code, out, _ = run_script(str(d / "bad_code.py"))
        check("a bad code literal fails", code == 1)
        check("the finding names the file", "bad_code.py" in out)
        check("the finding names the line", ":1:" in out)
        check("one file is counted as flagged", "1 carried" in out)

        # The docstring case: the module explains a pattern and thereby
        # contains it. This is the shape that reached main in this corpus.
        write(
            d,
            "bad_doc.py",
            '"""Match the anchor (?:export\\s+)? before the name."""\n',
        )
        code, out, _ = run_script(str(d / "bad_doc.py"))
        check("a bad docstring fails", code == 1)
        check("the docstring finding names the file", "bad_doc.py" in out)

        # 3. Raw literals and doubled backslashes are correct and stay clean.
        write(d, "good_raw.py", 'PATTERN = r"^a\\s+b$"\n')
        write(d, "good_doubled.py", 'PATTERN = "^a\\\\s+b$"\n')
        write(d, "good_doc.py", 'r"""Match the (?:export\\s+)? anchor."""\n')
        code, out, _ = run_script(
            str(d / "good_raw.py"),
            str(d / "good_doubled.py"),
            str(d / "good_doc.py"),
        )
        check("raw and doubled forms pass", code == 0)
        check("all three clean files were examined", "Examined 3 " in out)

        # A directory argument recurses.
        code, out, _ = run_script(str(d))
        check("a directory argument recurses", "Examined 5 " in out)
        check("the mixed directory fails", code == 1)
        check("both offenders are counted", "2 carried" in out)

    # 4. Neither the warning category nor the ambient filter decides the
    #    verdict. On 3.11 the fixture raises DeprecationWarning, which the
    #    default filter hides entirely; PYTHONWARNINGS=ignore hides it on
    #    every interpreter. The scan must flag it in both cases.
    with tempfile.TemporaryDirectory() as tmp:
        target = write(Path(tmp), "silent.py", 'PATTERN = "\\d+"\n')
        muted = dict(os.environ, PYTHONWARNINGS="ignore")
        code, out, _ = run_script(str(target), env=muted)
        check("a muted warnings filter does not hide the finding", code == 1)
        check("the muted run still names the escape", "invalid escape" in out)

    # The filter half of that claim is testable on any interpreter; the
    # CATEGORY half is not, because one interpreter only ever raises one of
    # the two. So exercise the predicate directly against both categories
    # instead. Without this, a regression from the message test to
    # `issubclass(entry.category, SyntaxWarning)` would pass every assertion
    # in this file on the 3.12 CI runner while going blind on a 3.11
    # maintainer machine --- the exact split the check exists to close.
    spec = importlib.util.spec_from_file_location("check_python_escapes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for category in (DeprecationWarning, SyntaxWarning, UserWarning):
        entry = warnings.WarningMessage(
            category("invalid escape sequence " + chr(39) + "\\s" + chr(39)),
            category,
            "fixture.py",
            1,
        )
        check(
            f"the predicate accepts a {category.__name__} carrying the message",
            module.is_invalid_escape(entry),
        )
    unrelated = warnings.WarningMessage(
        SyntaxWarning("assertion is always true"), SyntaxWarning, "fixture.py", 1
    )
    check(
        "the predicate rejects an unrelated SyntaxWarning",
        not module.is_invalid_escape(unrelated),
    )

    # 5. Negative control: examining nothing is a failure, not a clean tree.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, _ = run_script(str(tmp))
        check("an empty search space fails", code == 1)
        check("the empty search space is named", "Examined 0 " in out)
        check("the vacuous verdict is refused", "search space was empty" in out)

    # 6. A file that does not compile is reported, never swallowed. The first
    #    attempt at this scan swallowed every compile failure and reported a
    #    clean tree it had never actually examined, with no denominator to
    #    show for it.
    with tempfile.TemporaryDirectory() as tmp:
        target = write(Path(tmp), "broken.py", "def f(:\n")
        code, out, _ = run_script(str(target))
        check("an uncompilable file fails", code == 1)
        check("the uncompilable file is named", "does not compile" in out)
        check("the uncompilable file is not counted as an escape", "0 carried" in out)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
