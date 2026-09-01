#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2547).

Verifies that:
1. parse_link_target properly extracts paths and drops title attributes across
   double quotes, single quotes, parentheses, and angle brackets.
2. Link reference definitions ([label]: target "title") are recognized and checked.
3. Footnotes ([^label]: text) and placeholders are ignored.
4. Inline links and reference definitions with relative targets validate correctly.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
check_links = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = check_links
spec.loader.exec_module(check_links)

parse_link_target = check_links.parse_link_target
is_external = check_links.is_external
check_file = check_links.check_file

passed = 0
failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name}")


def main() -> int:
    print("Testing check-links.py...")

    # 1. parse_link_target unit tests
    check("parse plain target", parse_link_target("foo/bar.md") == "foo/bar.md")
    check(
        "parse target with double-quoted title",
        parse_link_target('foo/bar.md "Optional Title"') == "foo/bar.md",
    )
    check(
        "parse target with single-quoted title",
        parse_link_target("foo/bar.md 'Optional Title'") == "foo/bar.md",
    )
    check(
        "parse target with parenthesized title",
        parse_link_target("foo/bar.md (Optional Title)") == "foo/bar.md",
    )
    check(
        "parse angle-bracket target",
        parse_link_target("<foo/bar.md>") == "foo/bar.md",
    )
    check(
        "parse angle-bracket target with double-quoted title",
        parse_link_target('<foo/bar.md> "Optional Title"') == "foo/bar.md",
    )
    check(
        "parse angle-bracket target with single-quoted title",
        parse_link_target("<foo/bar.md> 'Optional Title'") == "foo/bar.md",
    )
    check(
        "parse angle-bracket target with parenthesized title",
        parse_link_target("<foo/bar.md> (Optional Title)") == "foo/bar.md",
    )
    check(
        "parse angle-bracket placeholder preserved",
        parse_link_target("<owner>/<repo>") == "<owner>/<repo>",
    )
    check(
        "parse target with anchor and title",
        parse_link_target('foo/bar.md#heading "Heading Title"') == "foo/bar.md#heading",
    )
    check("parse empty string", parse_link_target("") == "")
    check("parse whitespace string", parse_link_target("   ") == "")

    # 2. is_external unit tests
    check("http is external", is_external("http://example.com"))
    check("https is external", is_external("https://example.com"))
    check("mailto is external", is_external("mailto:dev@example.com"))
    check("tel is external", is_external("tel:+1234567890"))
    check("in-page anchor is external", is_external("#section"))
    check("relative path is not external", not is_external("docs/guide.md"))

    # 3. check_file with reference definitions and titles
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        target_file = tmp / "target.md"
        target_file.write_text("# Target\n", encoding="utf-8")

        # Test markdown containing various reference definitions
        md_content = """# Reference Links Test

[ref1]: target.md
[ref2]: target.md "Double Quote Title"
[ref3]: target.md 'Single Quote Title'
[ref4]: target.md (Parenthesized Title)
[ref5]: <target.md>
[ref6]: <target.md> "Angle Bracket With Double Quotes"
[ref7]: <target.md> 'Angle Bracket With Single Quotes'
[ref8]: <target.md> (Angle Bracket With Parens)
   [ref9]: target.md "Indented 3 Spaces"
[ext1]: https://example.com "External Link"
[placeholder]: <owner>/<repo>
[^footnote]: This is footnote text, not a broken link.

Inline link check: [inline](target.md "Inline Title").
"""
        test_md = tmp / "test.md"
        test_md.write_text(md_content, encoding="utf-8")

        # Save previous global state and run check_file
        check_links.broken = []
        check_links.checked = 0
        check_file(test_md)

        check(
            "valid reference definitions and titles found no broken links",
            len(check_links.broken) == 0,
        )
        check(
            "checked count reflects all valid relative reference definitions and inline link",
            check_links.checked == 10,
        )

    # 4. Broken reference definition is detected
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        test_md = tmp / "broken_ref.md"
        test_md.write_text(
            '[missing]: nonexistent_file.md "Missing File"\n',
            encoding="utf-8",
        )
        check_links.broken = []
        check_links.checked = 0
        check_file(test_md)

        check(
            "broken reference definition is detected",
            len(check_links.broken) == 1,
        )
        check(
            "broken entry includes missing file target",
            any("nonexistent_file.md" in b for b in check_links.broken),
        )

    # 5. CLI end-to-end execution
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    check("check-links.py passes on repo tree", proc.returncode == 0)
    check("check-links.py reports success checkmark", "✓ no broken relative links" in proc.stdout)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
