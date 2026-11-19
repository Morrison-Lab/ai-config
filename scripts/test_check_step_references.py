#!/usr/bin/env python3
"""Tests for scripts/check-step-references.py (ai-config#1865).

The negative controls come first: a reference to a step the target does not
define, and a backwards range, each of which the checker MUST report. A zero
result is otherwise indistinguishable from a detector that never ran.
The rest pin the forms the corpus actually uses, and the cases that must stay
quiet.
"""
import contextlib
import importlib.util
import io
import re
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_step_references", Path(__file__).parent / "check-step-references.py"
)
csr = importlib.util.module_from_spec(spec)
sys.modules["check_step_references"] = csr
spec.loader.exec_module(csr)

TARGET = """\
# target

## Procedure

### 1. First

### 2. Second

### 3.5. Halfway

### 4b. Sub-step

## Step 6 -- Extend

## step 12 -- Lower-case prefix

### 10 Heading with no punctuation

### 11.9. Ninth part

### 11.10. Tenth part

```bash
### 9. Not a step: inside a fence
```

7. **A numbered item.**
"""

FRAGMENT = """\
# fragment

1. **Only step.**
"""


DECIMAL = """\
# decimal

### 1.25. Only a decimal step
"""

ANCHOR = "Anchor: `target` step 1.\n"


def make_repo(tmp: Path, citing: str) -> Path:
    (tmp / "skills" / "target").mkdir(parents=True)
    (tmp / "skills" / "target" / "SKILL.md").write_text(TARGET, encoding="utf-8")
    (tmp / "skills" / "citing").mkdir(parents=True)
    path = tmp / "skills" / "citing" / "SKILL.md"
    path.write_text(citing, encoding="utf-8")
    (tmp / "shared").mkdir()
    (tmp / "shared" / "fragment.md").write_text(FRAGMENT, encoding="utf-8")
    (tmp / "shared" / "decimal.md").write_text(DECIMAL, encoding="utf-8")
    return path


def run(citing: str) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_repo(tmp, citing)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = csr.main(["--root", str(tmp)])
        return code, out.getvalue(), err.getvalue()


CASES = [
    # (name, citing text, expected exit code, substring the output must hold)
    ("missing step is reported", "Run `target` step 5.\n", 1, "defines no step 5"),
    ("backwards range is reported", "Run `target` steps 3 through 1.\n", 1, "not ascending"),
    ("fenced heading is not a step", "Run `target` step 9.\n", 1, "defines no step 9"),
    ("missing sub-step is reported", "Run `target` step 4c.\n", 1, "defines no step 4c"),
    ("link form, missing step", "Run [`f`](../../shared/fragment.md) step 2.\n", 1, "no step 2"),
    ("of form, missing step", "See step 8 of [`target`](../target/SKILL.md).\n", 1, "no step 8"),
    ("reference across a line break", "Run `target`\nstep 5.\n", 1, "defines no step 5"),
    ("heading step", "Run `target` step 1.\n", 0, ""),
    ("possessive and own", "Run `target`'s own step 2.\n", 0, ""),
    ("decimal step", "Run `target` step 3.5 first.\n", 0, ""),
    ("lettered sub-step", "Run `target` step 4b.\n", 0, ""),
    ("group of sub-steps", "Run `target` step 4.\n", 0, ""),
    ("Step N heading form", "Run `target` step 6.\n", 0, ""),
    ("numbered list item", "Run `target` step 7.\n", 0, ""),
    ("range and list", "Run `target` steps 1 through 2, 3.5 and 7.\n", 0, ""),
    ("link form", "Run [`f`](../../shared/fragment.md) step 1.\n", 0, ""),
    ("of form", "See step 2 of [`target`](../target/SKILL.md).\n", 0, ""),
    ("unknown skill is reported", "Run `nonexistent` step 99.\n", 1, "no skill named nonexistent"),
    ("missing Markdown link is reported as missing", "Run [`x`](../../shared/gone.md) step 1.\n", 1, "names no file"),
    ("a skill name containing step is not an example", "Run `step-runner` step 1.\n", 1, "no skill named step-runner"),
    ("local non-Markdown link is reported", "Run [`x`](../../shared/x.txt) step 1.\n", 1, "not a Markdown file"),
    ("decimal step is not its parent", "Run [`d`](../../shared/decimal.md) step 1.\n", 1, "no step 1"),
    ("corpus with no resolved reference fails", "Then do step 99.\n", 1, "found no references"),
    ("capital Step after the name", "Run `target` Step 1.\n", 0, ""),
    ("capital Step after the name, missing", "Run `target` Step 5.\n", 1, "defines no step 5"),
    ("range interior is checked", "Run `target` steps 4 through 7.\n", 1, "no step 5, inside range 4 to 7"),
    ("range interior met by a decimal step", "Run `target` steps 1 through 4.\n", 0, ""),
    ("backticked of form", "See step 2 of `target`.\n", 0, ""),
    ("backticked of form, missing", "See step 8 of `target`.\n", 1, "defines no step 8"),
    ("lower-case Step prefix", "Run `target` step 12.\n", 0, ""),
    ("same-document anchor link", "### 1. Only\n\nSee [`here`](#only) step 1.\n", 0, ""),
    ("same-document anchor, missing step", "### 1. Only\n\nSee [`here`](#only) step 2.\n", 1, "no step 2"),
    ("heading with a space after the id", "Run `target` step 10.\n", 0, ""),
    ("componentwise range order", "Run `target` steps 11.9 through 11.10.\n", 0, ""),
    ("example code span is skipped", ANCHOR + "Write ``Run `target` step 99`` like this.\n", 0, ""),
    ("bare same-document reference is out of scope", ANCHOR + "Then do step 99.\n", 0, ""),
    ("reference inside a fence is skipped", ANCHOR + "```\n`target` step 99\n```\n", 0, ""),
    ("external link is skipped", ANCHOR + "See [`x`](https://example.com/x.md) step 99.\n", 0, ""),
]


def main() -> int:
    failures = 0
    for name, citing, want_code, want_text in CASES:
        code, out, err = run(citing)
        ok = code == want_code and want_text in out + err
        if ok and want_code == 0:
            # A pass must have resolved something, or it proves nothing.
            ok = re.search(r" in [1-9]\d* reference", err) is not None
        if not ok:
            failures += 1
            print(f"FAIL {name}: exit {code} (want {want_code}), output {out!r}")
    print(f"{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
