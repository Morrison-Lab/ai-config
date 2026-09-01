#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2520)."""
from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path to import check-links module
sys.path.insert(0, str(Path(__file__).resolve().parent))

check_links = importlib.import_module("check-links")

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


# 1. Regex test for reference link definitions with subsequent line titles
cases = [
    # Double-quoted title on subsequent line
    ('[label]: path/to/target.md\n  "Title string"', "path/to/target.md"),
    # Single-quoted title on subsequent line
    ("[label]: path/to/target.md\n  'Title string'", "path/to/target.md"),
    # Parenthesized title on subsequent line
    ("[label]: path/to/target.md\n  (Title string)", "path/to/target.md"),
    # Angle bracket destination with subsequent line title
    ('[label]: <path/to/target.md>\n  "Title string"', "path/to/target.md"),
    # Destination on subsequent line, title on line after
    ('[label]:\n  path/to/target.md\n  "Title string"', "path/to/target.md"),
    # Destination on same line with title
    ('[label]: path/to/target.md "Title string"', "path/to/target.md"),
    # Destination without title
    ("[label]: path/to/target.md", "path/to/target.md"),
    # Up to 3 spaces indentation
    ('   [label]: path/to/target.md\n     "Title string"', "path/to/target.md"),
    # Escaped brackets in label
    ('[label\\]with\\]bracket]: path/to/target.md\n  "Title string"', "path/to/target.md"),
    # Escaped quotes in title
    ('[label]: path/to/target.md\n  "Title with \\"quotes\\""', "path/to/target.md"),
]

for snippet, expected_dest in cases:
    m = check_links.REF_DEF.search(snippet)
    check(f"REF_DEF matches snippet: {snippet.splitlines()[0]}", m is not None)
    if m:
        dest = m.group(2) or m.group(3)
        check(f"REF_DEF extracted dest {expected_dest}", dest == expected_dest)

# 2. Negative cases that should not be matched as reference link definitions
negatives = [
    # Footnote definition
    "[^1]: This is footnote text",
    # 4 spaces indent is a markdown code block
    '    [label]: path/to/target.md\n    "Title string"',
]
for snippet in negatives:
    m = check_links.REF_DEF.search(snippet)
    check(f"REF_DEF ignores negative case: {snippet.splitlines()[0]}", m is None)

# 3. End-to-end check_file tests with temporary files
with tempfile.TemporaryDirectory() as tmpdir:
    tmppath = Path(tmpdir)
    target_existing = tmppath / "target_existing.md"
    target_existing.write_text("# Target", encoding="utf-8")

    sub_dir = tmppath / "subdir"
    sub_dir.mkdir()
    sub_target = sub_dir / "nested.md"
    sub_target.write_text("# Nested", encoding="utf-8")

    test_md = tmppath / "test.md"
    test_content = """# Test Document

Here is an inline link: [Existing](target_existing.md "Optional Title").
Here is a link in code fence (should be ignored):
```markdown
[Broken In Fence](nonexistent_in_fence.md)
[Broken Ref In Fence]: nonexistent_ref_fence.md
  "Fence Title"
```

Here is inline code (should be ignored): `[Broken Inline](nonexistent_inline.md)`.

Here is a reference link with title on subsequent line:
[sub_link]: subdir/nested.md
  "Nested Markdown Title"

Here is a broken reference link with title on subsequent line:
[broken_sub]: missing/file.md
  "Missing File Title"

Here is a broken inline link: [Missing](missing/inline.md).

[^footnote]: Footnote text pointing nowhere.
"""
    test_md.write_text(test_content, encoding="utf-8")

    # Reset globals before check_file
    check_links.broken = []
    check_links.checked = 0

    check_links.check_file(test_md)

    check("checked count reflects valid relative targets", check_links.checked == 4)
    check("broken list has exactly 2 entries", len(check_links.broken) == 2)
    check(
        "broken list contains broken reference link with subsequent title",
        any("missing/file.md" in b for b in check_links.broken),
    )
    check(
        "broken list contains broken inline link",
        any("missing/inline.md" in b for b in check_links.broken),
    )
    check(
        "code fences and inline spans were ignored",
        not any("nonexistent" in b for b in check_links.broken),
    )

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
