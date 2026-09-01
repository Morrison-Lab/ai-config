#!/usr/bin/env python3
"""Regression tests for scripts/check-links.py.

Verifies:
  1. Autolinks inside markdown tables without spaces (e.g. `|<https://github.com>|`
     and `|<user@domain.tld>|`) are parsed as external links and not treated as
     broken relative paths.
  2. URI autolinks with schemes (`https:`, `http:`, `mailto:`, `ftp:`, `tel:`)
     and email autolinks are classified as external.
  3. Non-autolink angle bracket constructs (HTML tags, angle-bracket placeholders
     such as `<owner>/<repo>`) are ignored.
  4. Links inside fenced code blocks and inline code spans are ignored.
  5. Valid relative links resolve and missing relative targets are flagged as broken.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
check_links = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = check_links
spec.loader.exec_module(check_links)

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def run_tests() -> None:
    # 1. Test is_external
    check("is_external: https URL", check_links.is_external("https://github.com"))
    check("is_external: http URL", check_links.is_external("http://example.com/path"))
    check("is_external: mailto prefix", check_links.is_external("mailto:dev@example.com"))
    check("is_external: tel prefix", check_links.is_external("tel:+1234567890"))
    check("is_external: anchor fragment", check_links.is_external("#heading-title"))
    check("is_external: ftp scheme", check_links.is_external("ftp://files.example.org"))
    check("is_external: doi URI scheme", check_links.is_external("doi:10.1000/182"))
    check("is_external: urn URI scheme", check_links.is_external("urn:isbn:0451450523"))
    check("is_external: email address", check_links.is_external("user@domain.tld"))
    check("is_external: tagged email", check_links.is_external("alice.bob+tag@sub.domain.co"))
    check("is_external: relative file is not external", not check_links.is_external("docs/guide.md"))
    check("is_external: relative file with slash and at", not check_links.is_external("@shared/workflow/foo.md"))
    check("is_external: bare relative file", not check_links.is_external("foo.md"))

    # 2. Test autolink regex matching
    autolinks = check_links.AUTOLINK.findall(
        "|<https://github.com>|<user@domain.tld>|<mailto:dev@example.com>|"
    )
    check(
        "AUTOLINK matches unspaced table cells",
        autolinks == ["https://github.com", "user@domain.tld", "mailto:dev@example.com"],
        f"got {autolinks}",
    )

    placeholders = check_links.AUTOLINK.findall("<div> <owner>/<repo> <!-- comment --> a < b")
    check(
        "AUTOLINK ignores HTML tags and placeholders",
        placeholders == [],
        f"got {placeholders}",
    )

    # 3. Test check_file on synthetic files in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        check_links.ROOT = tmp_path
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "target.md").write_text("# Target\n", encoding="utf-8")

        # Clean document with table unspaced autolinks and relative links
        clean_doc = tmp_path / "docs" / "clean.md"
        clean_doc.write_text(
            "# Table Test\n\n"
            "| Column 1 | Column 2 | Contact |\n"
            "|---|---|---|\n"
            "| [Target](target.md) |<https://github.com>|<user@domain.tld>|\n"
            "| [Target 2](<target.md>) | <http://example.com> | <mailto:alice@example.com> |\n"
            "| Double pipes ||<https://example.com>||<bob@domain.org>|\n"
            "\n"
            "Angle placeholder: `<owner>/<repo>` should be ignored.\n"
            "Code block with broken link:\n"
            "```markdown\n"
            "[Broken](missing.md)\n"
            "|<https://fake.broken.domain>|\n"
            "```\n"
            "Inline code: `[Broken](missing_inline.md)` and `|<https://fake.domain>|`\n",
            encoding="utf-8",
        )

        check_links.broken = []
        check_links.checked = 0
        check_links.check_file(clean_doc)
        check(
            "check_file on unspaced table autolinks has no broken links",
            len(check_links.broken) == 0,
            f"broken={check_links.broken}",
        )
        check(
            "check_file counted relative links",
            check_links.checked == 2,
            f"checked={check_links.checked}",
        )

        # Document with a genuine broken relative link
        broken_doc = tmp_path / "docs" / "broken.md"
        broken_doc.write_text(
            "# Broken Test\n\n"
            "| Cell | Link |\n"
            "|---|---|\n"
            "| Unspaced autolink |<https://example.com>|\n"
            "| Real broken relative |[Missing](does_not_exist.md)|\n",
            encoding="utf-8",
        )

        check_links.broken = []
        check_links.checked = 0
        check_links.check_file(broken_doc)
        check(
            "check_file flags broken relative link while ignoring table autolink",
            len(check_links.broken) == 1 and "does_not_exist.md" in check_links.broken[0],
            f"broken={check_links.broken}",
        )


if __name__ == "__main__":
    run_tests()
    print(f"\n{passes} passed, {failures} failed")
    if failures > 0:
        sys.exit(1)
