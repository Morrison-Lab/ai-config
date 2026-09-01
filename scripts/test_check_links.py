#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2516).

Validates that check-links.py correctly:
1. Recognizes autolinks (<https://...>, <mailto:...>, <user@domain.tld>)
   in prose and 4-space indented markdown lists and nested sublists.
2. Strips true indented code blocks (4+ space indent preceded by blank line)
   so fake/example links inside them are not flagged as broken relative paths.
3. Preserves and validates relative links across nested list items.
4. Ignores fenced code blocks, inline code spans, HTML tags, and angle-bracket placeholders.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO / "scripts" / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
check_links = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = check_links
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


def main() -> int:
    global passes, failures
    print("Testing check-links.py...")

    # 1. is_external tests
    check("is_external: https URL", check_links.is_external("https://example.com"))
    check("is_external: http URL", check_links.is_external("http://example.com/path"))
    check("is_external: mailto link", check_links.is_external("mailto:user@example.com"))
    check("is_external: tel link", check_links.is_external("tel:+1234567890"))
    check("is_external: ftp link", check_links.is_external("ftp://ftp.example.com"))
    check("is_external: anchor link", check_links.is_external("#heading-anchor"))
    check("is_external: email address", check_links.is_external("user@domain.tld"))
    check("is_external: email with subdomains", check_links.is_external("user@sub.domain.co.uk"))
    check("is_external: custom URI scheme vscode://", check_links.is_external("vscode://file/path"))
    check("is_external: relative file path is not external", not check_links.is_external("docs/guide.md"))
    check("is_external: parent relative path is not external", not check_links.is_external("../README.md"))
    check("is_external: dot-slash relative path is not external", not check_links.is_external("./style.md"))

    # 2. extract_targets tests
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

    # Standalone autolinks in prose
    doc_autolink = "Visit <https://example.com> or email <mailto:info@example.com> or <dev@morrison.lab>."
    targets_autolink = check_links.extract_targets(doc_autolink)
    check(
        "extract_targets: standalone autolinks in prose",
        "https://example.com" in targets_autolink
        and "mailto:info@example.com" in targets_autolink
        and "dev@morrison.lab" in targets_autolink,
    )

    # 4-space indented lists with autolinks and relative links
    doc_4space_lists = """
- Root item 1
    - 4-space sublist item with autolink <https://github.com/Morrison-Lab/ai-config>
    - 4-space sublist item with mailto autolink <mailto:support@example.org>
    - 4-space sublist item with email autolink <developer@example.org>
    - 4-space sublist item with relative link [architecture](docs/arch.md)
    * 4-space star sublist with autolink <https://developer.mozilla.org/en-US/docs/Web>
    + 4-space plus sublist with autolink <https://python.org>
    1. 4-space numbered sublist with autolink <https://pypi.org>
    2. 4-space numbered sublist with relative link [changelog](CHANGELOG.md)
    - [ ] 4-space task list unchecked with <https://example.com/task1>
    - [x] 4-space task list checked with <https://example.com/task2>
"""
    targets_4space = check_links.extract_targets(doc_4space_lists)
    expected_4space = [
        "https://github.com/Morrison-Lab/ai-config",
        "mailto:support@example.org",
        "developer@example.org",
        "docs/arch.md",
        "https://developer.mozilla.org/en-US/docs/Web",
        "https://python.org",
        "https://pypi.org",
        "CHANGELOG.md",
        "https://example.com/task1",
        "https://example.com/task2",
    ]
    for exp in expected_4space:
        check(f"extract_targets: 4-space list item contains '{exp}'", exp in targets_4space)

    # Standalone 4-space indented list at start of file
    doc_standalone_4space = """    - <https://standalone.example.com>
    - [standalone](docs/standalone.md)
"""
    targets_standalone = check_links.extract_targets(doc_standalone_4space)
    check(
        "extract_targets: standalone 4-space list recognized",
        "https://standalone.example.com" in targets_standalone and "docs/standalone.md" in targets_standalone,
    )

    # True indented code blocks: link-like syntax inside code blocks is stripped
    doc_indented_code = """
Here is prose before code.

    def example():
        # [fake_link](nonexistent/relative/path.md)
        # <https://code-example.com>
        # <nonexistent/file.md>
        return True

    # another indented code chunk after blank
    run_command("[command](missing_command.md)")

Here is prose after code with real link [readme](README.md).
"""
    targets_indented_code = check_links.extract_targets(doc_indented_code)
    check(
        "extract_targets: fake link in indented code block is stripped",
        "nonexistent/relative/path.md" not in targets_indented_code,
    )
    check(
        "extract_targets: autolink in indented code block is stripped",
        "https://code-example.com" not in targets_indented_code,
    )
    check(
        "extract_targets: second chunk in indented code block is stripped",
        "missing_command.md" not in targets_indented_code,
    )
    check(
        "extract_targets: real link after indented code block is preserved",
        "README.md" in targets_indented_code,
    )

    # Fenced code blocks and inline code spans are ignored
    doc_fenced = """
```markdown
- [fenced_link](missing_in_fence.md)
- <https://fenced-code.com>
```

~~~
- <mailto:tilde@example.com>
~~~

Inline code: `[inline_link](missing_in_span.md)` and `<https://inline.com>`
"""
    targets_fenced = check_links.extract_targets(doc_fenced)
    check("extract_targets: fenced code block link ignored", "missing_in_fence.md" not in targets_fenced)
    check("extract_targets: fenced autolink ignored", "https://fenced-code.com" not in targets_fenced)
    check("extract_targets: tilde fenced autolink ignored", "mailto:tilde@example.com" not in targets_fenced)
    check("extract_targets: inline code span link ignored", "missing_in_span.md" not in targets_fenced)

    # Placeholders and HTML tags are ignored
    doc_placeholders = "Run `<owner>/<repo>` or `<branch>` in `<div class='test'>`."
    targets_placeholders = check_links.extract_targets(doc_placeholders)
    check("extract_targets: placeholders and HTML tags produce no link targets", len(targets_placeholders) == 0)

    # 3. check_file end-to-end tests with real files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create target files
        docs_dir = tmppath / "docs"
        docs_dir.mkdir()
        (docs_dir / "arch.md").write_text("# Arch\n", encoding="utf-8")
        (tmppath / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

        # Valid file with 4-space lists and autolinks
        valid_file = tmppath / "valid.md"
        valid_file.write_text(doc_4space_lists, encoding="utf-8")
        broken_valid = check_links.check_file(valid_file, root=tmppath)
        check("check_file: valid 4-space lists with autolinks report 0 broken links", len(broken_valid) == 0)

        # File with true indented code block containing missing links (should not fail)
        code_file = tmppath / "code.md"
        code_file.write_text(doc_indented_code, encoding="utf-8")
        (tmppath / "README.md").write_text("# Readme\n", encoding="utf-8")
        broken_code = check_links.check_file(code_file, root=tmppath)
        check("check_file: indented code block missing links are stripped and report 0 broken", len(broken_code) == 0)

        # File with broken link inside a 4-space indented list
        broken_doc = """
- Root
    - 4-space sublist item with autolink <https://example.com>
    - 4-space sublist item with broken link [missing](docs/missing.md)
"""
        broken_file = tmppath / "broken.md"
        broken_file.write_text(broken_doc, encoding="utf-8")
        broken_results = check_links.check_file(broken_file, root=tmppath)
        check("check_file: detects broken relative link in 4-space sublist", len(broken_results) == 1)
        check("check_file: broken result names missing relative path", "broken.md -> docs/missing.md" in broken_results[0])

    # 4. CLI execution against repo
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    check("CLI: check-links.py runs clean against repo with exit 0", proc.returncode == 0)
    check("CLI: check-links.py outputs success checkmark", "✓ no broken relative links" in proc.stdout)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
