#!/usr/bin/env python3
"""Self-test for scripts/split-qmd.py.

The splitter is only safe to use if the split changes no content, so the
cases pinned here are: expanding the includes gives back every line of the
original, a rerun on the spine writes nothing, and a rerun refuses to
overwrite a subfile that holds other content.

Run with ``python3 scripts/test_split_qmd.py``. Needs no pytest.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "split_qmd", Path(__file__).resolve().parent / "split-qmd.py"
)
split_qmd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(split_qmd)

FAILURES: list[str] = []

CHAPTER = """---
title: Fixture
---

# First section

Some prose before the exercise.

::: {#exr-first}
#### A question
What is it?
:::

{{< slidebreak >}}

::: {#sol-first}
An answer.

::: {.callout-note}
A nested callout.
:::
:::

More prose after it.

```{python}
x = 1
# ::: not a div inside code
```

# Second section

::: {#def-thing}
A definition.
:::

::: center
A bare-class div.
:::

::: {#refs}
:::
"""


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def expand(spine: Path) -> str:
    out = []
    for line in spine.read_text().split("\n"):
        m = re.match(r"\{\{< include (_subfiles/\S+) >\}\}$", line)
        out.append((spine.parent / m.group(1)).read_text().rstrip("\n") if m else line)
    return "\n".join(out)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        chapter = Path(tmp) / "fixture.qmd"
        chapter.write_text(CHAPTER)
        files = split_qmd.split(chapter)
        check("writes subfiles", len(files) >= 4, str(sorted(files)))
        check("names divs by id", {"_exr-first.qmd", "_sol-first.qmd", "_def-thing.qmd"} <= set(files))
        check("names a bare-class div by its class", any(f.endswith("-center.qmd") for f in files), str(sorted(files)))
        check("round-trips every line, blank lines included", expand(chapter) == CHAPTER)
        spine = chapter.read_text()
        check("keeps headings in the spine", "# First section" in spine and "# Second section" in spine)
        check("keeps {#refs} in the spine", "::: {#refs}" in spine)

        again = split_qmd.split(chapter)
        check("rerun on the spine writes nothing", again == {}, str(sorted(again)))
        check("rerun leaves the spine unchanged", chapter.read_text() == spine)

        clash = Path(tmp) / "clash.qmd"
        clash.write_text(CHAPTER)
        sub = Path(tmp) / "_subfiles" / "clash"
        sub.mkdir(parents=True)
        (sub / "_exr-first.qmd").write_text("other content\n")
        try:
            split_qmd.split(clash)
            refused = False
        except SystemExit:
            refused = True
        check("refuses to overwrite a different subfile", refused)
        check("leaves the chapter untouched on refusal", clash.read_text() == CHAPTER)

        for label, tail in [("div", "::: {#exr-open}\nNo close.\n"),
                            ("code fence", "```{python}\nx = 1\n"),
                            ("HTML comment", "<!-- never closed\n")]:
            broken = Path(tmp) / f"broken-{label.replace(' ', '-')}.qmd"
            text = CHAPTER + tail
            broken.write_text(text)
            try:
                split_qmd.split(broken)
                message = ""
            except SystemExit as err:
                message = str(err.code)
            check(f"names an unclosed {label}", "unclosed" in message, message)
            check(f"writes nothing for an unclosed {label}",
                  broken.read_text() == text
                  and not (Path(tmp) / "_subfiles" / broken.stem).exists())
    print(f"{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
