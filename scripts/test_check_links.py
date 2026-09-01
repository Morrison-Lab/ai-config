#!/usr/bin/env python3
"""Regression tests for check-links.py."""
import importlib.util
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "cl", Path(__file__).parent / "check-links.py"
)
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

passes = 0
failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


# --- 1. is_external tests --------------------------------------------------

check("is_external: http URL", cl.is_external("http://example.com"))
check("is_external: https URL", cl.is_external("https://example.com/page"))
check("is_external: mailto URI", cl.is_external("mailto:support@example.com"))
check("is_external: tel URI", cl.is_external("tel:+1234567890"))
check("is_external: anchor link", cl.is_external("#section-anchor"))
check("is_external: custom scheme URI", cl.is_external("ftp://files.example.com"))
check("is_external: bare email autolink", cl.is_external("user@example.com"))
check("is_external: relative file path is not external", not cl.is_external("docs/guide.md"))
check("is_external: parent relative path is not external", not cl.is_external("../shared/faq.md"))
check("is_external: current dir relative path is not external", not cl.is_external("./readme.md"))


# --- 2. extract_targets on definition lists and autolinks -------------------

deflist_sample = """
# Vocabulary

Pandoc Style Term
: Definition containing <https://pandoc.org/MANUAL.html> and <mailto:dev@pandoc.org>.

Email Contact
: Reach out at <contact@example.org> for inquiries.

Relative Ref
: Read more in [the manual](docs/manual.md) and <references/spec.md>.

Broken Def Link
: See [missing](docs/missing.md) or <references/missing.md>.
"""

targets = list(cl.extract_targets(deflist_sample))
check(
    "extract_targets: ignores external autolinks in definition lists",
    "https://pandoc.org/MANUAL.html" not in targets
    and "mailto:dev@pandoc.org" not in targets
    and "contact@example.org" not in targets,
)
check(
    "extract_targets: extracts relative links in definition lists",
    "docs/manual.md" in targets
    and "references/spec.md" in targets
    and "docs/missing.md" in targets
    and "references/missing.md" in targets,
)


# --- 3. extract_targets on code fences, inline spans, HTML, placeholders ---

complex_sample = """
# Header

Normal link: [guide](docs/guide.md).
Autolink: <https://github.com/Morrison-Lab/ai-config>.
Angle-bracketed link: [wrapped](<docs/wrapped.md>).
Title link: [titled](docs/titled.md "Optional Title").
Anchor in link: [heading](docs/section.md#overview).
Query in link: [search](docs/search.md?q=test).

HTML tags should be ignored:
<details>
<summary>Click to expand</summary>
<div>content</div>
<br>
<img src="pic.png">
</details>

Angle-bracket placeholders:
`<owner>/<repo>`
Use `<file>` or `<branch>` or `<N>`.
And in text: <owner>/<repo> or <placeholder>.

```markdown
Fenced code block:
[fenced](docs/nonexistent-fenced.md)
<https://fenced.example.com>
<docs/nonexistent-autolink-fenced.md>
```

Inline code: `[inline](docs/nonexistent-inline.md)` and `<docs/nonexistent-inline.md>`.
"""

complex_targets = list(cl.extract_targets(complex_sample))
check("extract_targets: extracts standard relative link", "docs/guide.md" in complex_targets)
check("extract_targets: extracts angle-bracketed target", "docs/wrapped.md" in complex_targets)
check("extract_targets: extracts titled target with title stripped", "docs/titled.md" in complex_targets)
check("extract_targets: extracts target with anchor", "docs/section.md#overview" in complex_targets)
check("extract_targets: extracts target with query", "docs/search.md?q=test" in complex_targets)
check(
    "extract_targets: ignores fences and inline code",
    "docs/nonexistent-fenced.md" not in complex_targets
    and "docs/nonexistent-autolink-fenced.md" not in complex_targets
    and "docs/nonexistent-inline.md" not in complex_targets,
)
check(
    "extract_targets: ignores HTML tags and placeholders",
    not any(t in complex_targets for t in ["details", "summary", "div", "br", "owner", "repo", "file", "branch", "N", "placeholder"]),
)


# --- 4. check_file negative and positive controls in tempdir -----------------

with tempfile.TemporaryDirectory() as tmpdir:
    root = Path(tmpdir)
    docs = root / "docs"
    docs.mkdir()
    manual = docs / "manual.md"
    manual.write_text("# Manual\n", encoding="utf-8")

    # Clean file: all relative targets exist, all autolinks in definition lists are external
    clean_file = root / "clean.md"
    clean_file.write_text(
        "# Clean Document\n\n"
        "Term\n"
        ": Definition with autolink <https://example.com> and <mailto:user@example.com>.\n\n"
        "Reference\n"
        ": See [Manual](docs/manual.md) and <docs/manual.md>.\n",
        encoding="utf-8",
    )

    # Save original globals
    orig_broken = list(cl.broken)
    orig_checked = cl.checked
    cl.broken = []
    cl.checked = 0

    cl.check_file(clean_file)
    check("check_file: clean file with deflist autolinks produces 0 broken links", len(cl.broken) == 0)
    check("check_file: checked counter increments for valid relative links", cl.checked == 2)

    # Broken file: positive controls for missing relative link and missing deflist relative link
    broken_file = root / "broken.md"
    broken_file.write_text(
        "# Broken Document\n\n"
        "Term\n"
        ": Valid autolink <https://valid.com> but broken relative autolink <docs/missing-autolink.md>.\n\n"
        "Other\n"
        ": Broken markdown link [missing](docs/missing-link.md).\n",
        encoding="utf-8",
    )

    cl.broken = []
    cl.checked = 0
    cl.check_file(broken_file)
    check("check_file: positive control flags missing relative targets in deflist", len(cl.broken) == 2)
    check(
        "check_file: broken list contains expected paths",
        any("docs/missing-autolink.md" in b for b in cl.broken)
        and any("docs/missing-link.md" in b for b in cl.broken),
    )

    # Restore globals
    cl.broken = orig_broken
    cl.checked = orig_checked


# --- 5. Summary -------------------------------------------------------------

print(f"\nResults: {passes} passed, {failures} failed")
if failures > 0:
    sys.exit(1)
