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
   PYTHONWARNINGS=ignore.
5. An empty search space fails rather than reporting a vacuous clean --- the
   negative control the issue asks for.
6. A file that does not compile is reported rather than swallowed.

Every fixture below writes its backslash through a valid escape in THIS file,
so the suite stays clean under the very check it exercises.
"""
import os
import subprocess
import sys
import tempfile
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

    # 5. Negative control: examining nothing is a failure, not a clean tree.
    with tempfile.TemporaryDirectory() as tmp:
        code, out, _ = run_script(str(tmp))
        check("an empty search space fails", code == 1)
        check("the empty search space is named", "Examined 0 " in out)
        check("the vacuous verdict is refused", "search space was empty" in out)

    # 6. A file that does not compile is reported, never swallowed. The first
    #    attempt at this scan swallowed every compile failure and reported a
    #    clean tree over 238 files it had never actually examined.
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
