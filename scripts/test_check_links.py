#!/usr/bin/env python3
"""Regression tests for check-links.py.

Tests that check-links.py correctly resolves relative links, skips external links,
and recognizes autolinks in markdown and HTML <summary> tags.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

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


def test_is_external() -> None:
    check("is_external https", cl.is_external("https://example.com"))
    check("is_external http", cl.is_external("http://example.com/foo"))
    check("is_external mailto", cl.is_external("mailto:user@example.com"))
    check("is_external tel", cl.is_external("tel:+1234567890"))
    check("is_external anchor", cl.is_external("#section-heading"))
    check("is_external custom scheme", cl.is_external("ftp://files.example.com"))
    check("is_external email address", cl.is_external("user@example.com"))
    check("is_external relative file", not cl.is_external("docs/guide.md"))
    check("is_external parent relative file", not cl.is_external("../shared/doc.md"))
    check("is_external bare filename", not cl.is_external("README.md"))


def test_extract_links() -> None:
    # Standard inline markdown link
    text = "Read the [guide](docs/guide.md) for info."
    check("extract standard inline link", cl.extract_links(text) == ["docs/guide.md"])

    # Link with angle brackets
    text = "See [link](<https://example.com/path>)."
    check(
        "extract angle bracketed inline link",
        "https://example.com/path" in cl.extract_links(text),
    )

    # Link with title
    text = 'See [guide](docs/guide.md "Documentation Title").'
    check("extract inline link with title", cl.extract_links(text) == ["docs/guide.md"])

    # Autolinks in plain markdown
    text = "Visit <https://example.com> or email <mailto:support@example.com>."
    links = cl.extract_links(text)
    check(
        "extract plain autolinks",
        links == ["https://example.com", "mailto:support@example.com"],
    )

    # Autolinks in HTML summary tags
    text = "<summary>See <https://example.com/api></summary>"
    check(
        "extract autolink in summary tag",
        cl.extract_links(text) == ["https://example.com/api"],
    )

    text = "<details><summary>Contact <mailto:team@example.com></summary>Body</details>"
    check(
        "extract mailto autolink in summary tag",
        cl.extract_links(text) == ["mailto:team@example.com"],
    )

    # Non-autolink HTML tags and placeholder angle brackets
    text = "<summary>No autolink here</summary> and <owner>/<repo> placeholders"
    check("no false positives for plain HTML and placeholders", cl.extract_links(text) == [])


def test_check_file_integration() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        original_root = cl.ROOT
        original_broken = list(cl.broken)
        original_checked = cl.checked
        try:
            cl.ROOT = root
            cl.broken.clear()
            cl.checked = 0

            # Setup directory structure
            docs_dir = root / "docs"
            docs_dir.mkdir()
            target_file = docs_dir / "target.md"
            target_file.write_text("# Target\n", encoding="utf-8")

            test_md = root / "test.md"
            content = """# Test Document

Here is a valid relative link: [target](docs/target.md).
Here is an external link: [Google](https://google.com).
Here is an autolink in markdown: <https://example.com>.
Here is a summary tag with an autolink:
<details>
<summary>See <https://example.com/help></summary>
Details text.
</details>
Here is a summary tag with mailto autolink:
<summary>Contact <mailto:dev@example.com></summary>

```markdown
[ignored inside fence](docs/nonexistent.md)
<https://example.com/fence>
```

Inline code: `[ignored inside code](docs/nonexistent.md)` and `<https://example.com/code>`.
"""
            test_md.write_text(content, encoding="utf-8")

            cl.check_file(test_md)

            check("integration check no broken links", len(cl.broken) == 0)
            check("integration check valid relative links counted", cl.checked == 1)

            # Test broken link detection
            broken_md = root / "broken.md"
            broken_md.write_text("[missing](docs/missing.md)", encoding="utf-8")
            cl.check_file(broken_md)
            check("integration check detect broken link", len(cl.broken) == 1)
            check(
                "integration check broken link format",
                "broken.md -> docs/missing.md" in cl.broken[0],
            )
        finally:
            cl.ROOT = original_root
            cl.broken = original_broken
            cl.checked = original_checked


def main() -> None:
    test_is_external()
    test_extract_links()
    test_check_file_integration()
    print(f"\n{passes} passed, {failures} failed.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
