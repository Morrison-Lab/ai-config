#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2515).

Validates that check-links.py correctly recognizes autolinks (<https://...>,
<mailto:...>) inside nested markdown blockquotes (> > <https://...>),
while properly verifying relative links and ignoring code spans/blocks.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_links", Path(__file__).parent / "check-links.py"
)
check_links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_links)

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


def main() -> None:
    global passes, failures

    # --- 1. is_external tests ---
    check("is_external: https URL", check_links.is_external("https://example.com"))
    check("is_external: http URL", check_links.is_external("http://example.com/path"))
    check("is_external: mailto link", check_links.is_external("mailto:user@example.com"))
    check("is_external: tel link", check_links.is_external("tel:+1234567890"))
    check("is_external: ftp link", check_links.is_external("ftp://ftp.example.com"))
    check("is_external: anchor link", check_links.is_external("#heading-anchor"))
    check("is_external: raw email autolink", check_links.is_external("user@example.com"))
    check("is_external: relative file path is not external", not check_links.is_external("docs/guide.md"))
    check("is_external: parent relative path is not external", not check_links.is_external("../README.md"))
    check("is_external: dot-slash relative path is not external", not check_links.is_external("./style.md"))

    # --- 2. extract_targets tests ---
    # Standard inline link
    doc_inline = "Check out [the guide](docs/guide.md) for details."
    check(
        "extract_targets: standard inline link",
        check_links.extract_targets(doc_inline) == ["docs/guide.md"],
    )

    # Inline link with title
    doc_title = 'See [API](docs/api.md "API Documentation") here.'
    check(
        "extract_targets: inline link with title",
        check_links.extract_targets(doc_title) == ["docs/api.md"],
    )

    # Inline link with angle brackets in destination
    doc_angled = "See [Angled](<https://example.com/docs>)."
    check(
        "extract_targets: inline link with angle brackets in destination",
        check_links.extract_targets(doc_angled) == ["https://example.com/docs"],
    )

    # Standalone autolinks
    doc_autolink = "Visit <https://example.com> or email <mailto:info@example.com>."
    targets = check_links.extract_targets(doc_autolink)
    check(
        "extract_targets: standalone autolinks",
        "https://example.com" in targets and "mailto:info@example.com" in targets,
    )

    # Autolinks in nested blockquotes
    doc_nested_blockquotes = """
# Nested Blockquote Fixtures

> Level 1 quote with <https://example.com/level1>
> > Level 2 nested blockquote with <https://example.com/level2>
> > Level 2 mailto autolink <mailto:support@example.org>
> > Level 2 relative link [architecture](docs/arch.md)
>> Level 2 unspaced blockquote with <https://example.com/level2-unspaced>
> > > Level 3 nested blockquote with <https://developer.mozilla.org/en-US/docs/Web>
> > > Level 3 raw email autolink <developer@example.org>
>>> Level 3 unspaced blockquote with <https://example.com/level3-unspaced>
> > > > Level 4 deep nested blockquote with <https://python.org>
> > > > Level 4 relative link [changelog](CHANGELOG.md)
>  >   > Level 3 mixed spacing with <https://example.com/mixed-spacing>
>>><https://example.com/adjacent-to-marker>
> > - Nested blockquote list item with <https://example.com/bq-list>
> > 1. Nested blockquote numbered item with <https://example.com/bq-num>
> > Protocol autolinks: <ftp://ftp.example.com/file> and <tel:+18005550199>
"""
    nested_targets = check_links.extract_targets(doc_nested_blockquotes)
    expected_nested = [
        "https://example.com/level1",
        "https://example.com/level2",
        "mailto:support@example.org",
        "docs/arch.md",
        "https://example.com/level2-unspaced",
        "https://developer.mozilla.org/en-US/docs/Web",
        "developer@example.org",
        "https://example.com/level3-unspaced",
        "https://python.org",
        "CHANGELOG.md",
        "https://example.com/mixed-spacing",
        "https://example.com/adjacent-to-marker",
        "https://example.com/bq-list",
        "https://example.com/bq-num",
        "ftp://ftp.example.com/file",
        "tel:+18005550199",
    ]
    for expected in expected_nested:
        check(
            f"extract_targets: nested blockquote contains '{expected}'",
            expected in nested_targets,
        )

    # Autolinks inside code blocks are ignored
    doc_fenced = """
Here is prose before code.

```markdown
> > Blockquote in code block <https://code-example.com>
> > `[inside-code](broken/path.md)`
```

~~~
> > Tilde fence <mailto:ignored@code.com>
~~~

Prose after code with <https://real-link.com>.
"""
    fenced_targets = check_links.extract_targets(doc_fenced)
    check("extract_targets: fenced code block autolink ignored", "https://code-example.com" not in fenced_targets)
    check("extract_targets: fenced code block relative link ignored", "broken/path.md" not in fenced_targets)
    check("extract_targets: tilde code block autolink ignored", "mailto:ignored@code.com" not in fenced_targets)
    check("extract_targets: prose after code block extracted", "https://real-link.com" in fenced_targets)

    # Autolinks inside inline code spans are ignored
    doc_inline_code = "Use `> > <https://inline-code-example.com>` inside configuration."
    check(
        "extract_targets: inline code span autolink ignored",
        "https://inline-code-example.com" not in check_links.extract_targets(doc_inline_code),
    )

    # Angle-bracket placeholders are not autolinks
    doc_placeholders = "> > Run `gh repo clone <owner>/<repo>` or check `<branch-name>`."
    placeholder_targets = check_links.extract_targets(doc_placeholders)
    check(
        "extract_targets: angle-bracket placeholders are not autolinks",
        len(placeholder_targets) == 0,
    )

    # --- 3. check_file end-to-end tests with real files ---
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        check_links.ROOT = tmppath

        # Create target files
        docs_dir = tmppath / "docs"
        docs_dir.mkdir()
        (docs_dir / "arch.md").write_text("# Arch\n", encoding="utf-8")
        (tmppath / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

        # Create valid markdown file containing nested blockquotes with autolinks and valid relative links
        test_file = tmppath / "README.md"
        test_file.write_text(doc_nested_blockquotes, encoding="utf-8")

        broken = check_links.check_file(test_file)
        check("check_file: nested blockquotes with autolinks report 0 broken links", len(broken) == 0)

        # Create file with broken relative link in a nested blockquote
        broken_doc = """
> Level 1
> > Nested blockquote with <https://example.com>
> > Nested blockquote with broken link [missing](docs/missing.md)
"""
        broken_file = tmppath / "broken.md"
        broken_file.write_text(broken_doc, encoding="utf-8")
        broken_results = check_links.check_file(broken_file)
        check("check_file: detects broken relative link in nested blockquote", len(broken_results) == 1)
        check("check_file: broken result contains relative path", "broken.md -> docs/missing.md" in broken_results[0])

    print(f"\nResults: {passes} passed, {failures} failed.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
