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

```bash
### 9. Not a step: inside a fence
```

7. **A numbered item.**
"""

FRAGMENT = """\
# fragment

1. **Only step.**
"""


def make_repo(tmp: Path, citing: str) -> Path:
    (tmp / "skills" / "target").mkdir(parents=True)
    (tmp / "skills" / "target" / "SKILL.md").write_text(TARGET, encoding="utf-8")
    (tmp / "skills" / "citing").mkdir(parents=True)
    path = tmp / "skills" / "citing" / "SKILL.md"
    path.write_text(citing, encoding="utf-8")
    (tmp / "shared").mkdir()
    (tmp / "shared" / "fragment.md").write_text(FRAGMENT, encoding="utf-8")
    return path


def run(citing: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_repo(tmp, citing)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = csr.main(["--root", str(tmp)])
        return code, out.getvalue()


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
    ("unknown skill is skipped", "Run `nonexistent` step 99.\n", 0, ""),
    ("bare same-document reference is out of scope", "Then do step 99.\n", 0, ""),
    ("reference inside a fence is skipped", "```\n`target` step 99\n```\n", 0, ""),
    ("external link is skipped", "See [`x`](https://example.com/x.md) step 99.\n", 0, ""),
]


def main() -> int:
    failures = 0
    for name, citing, want_code, want_text in CASES:
        code, out = run(citing)
        ok = code == want_code and want_text in out
        if not ok:
            failures += 1
            print(f"FAIL {name}: exit {code} (want {want_code}), output {out!r}")
    print(f"{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
