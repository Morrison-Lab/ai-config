#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2511)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path to import check-links module
SCRIPT_PATH = Path(__file__).resolve().parent / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

clean_target = mod.clean_target
find_targets = mod.find_targets
check_file = mod.check_file

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


# 1. Target cleaning tests
check("clean_target basic relative", clean_target("relative/path.md") == "relative/path.md")
check("clean_target dot-slash", clean_target("./relative/path.md") == "./relative/path.md")
check("clean_target parent-dir", clean_target("../relative/path.md") == "../relative/path.md")
check("clean_target angle brackets", clean_target("<relative/path.md>") == "relative/path.md")
check("clean_target anchor strip", clean_target("path.md#heading") == "path.md")
check("clean_target query strip", clean_target("path.md?version=1") == "path.md")
check("clean_target anchor and query", clean_target("path.md#heading?v=1") == "path.md")
check("clean_target pure anchor ignored", clean_target("#pure-anchor") is None)
check("clean_target https ignored", clean_target("https://example.com/doc.md") is None)
check("clean_target http ignored", clean_target("http://example.com/doc.md") is None)
check("clean_target mailto ignored", clean_target("mailto:user@example.com") is None)
check("clean_target tel ignored", clean_target("tel:+1234567890") is None)
check("clean_target protocol ignored", clean_target("git://github.com/repo") is None)
check("clean_target angle bracket placeholder ignored", clean_target("<owner>/<repo>") is None)
check("clean_target bare word placeholder ignored", clean_target("bareword") is None)

# 2. Inline links tests
inline_doc = 'See [doc](path/to/doc.md) and [other](<path/to/other.md> "title").'
check("find_targets inline links", find_targets(inline_doc) == ["path/to/doc.md", "path/to/other.md"])

# 3. Reference link definitions with multiline titles and trailing spaces
cases = [
    # Multiline double-quoted title with trailing spaces on intermediate lines
    (
        '[label1]: path/one.md\n  "Title line 1   \n   Title line 2   \n   Title line 3"',
        ["path/one.md"],
    ),
    # Multiline double-quoted title with trailing spaces before closing quote
    (
        '[label2]: path/two.md\n  "Title line 1\n   Title line 2   "',
        ["path/two.md"],
    ),
    # Multiline double-quoted title with trailing spaces after closing quote
    (
        '[label3]: path/three.md\n  "Title line 1\n   Title line 2"   ',
        ["path/three.md"],
    ),
    # Multiline double-quoted title with closing quote on separate line with trailing spaces
    (
        '[label4]: path/four.md\n  "Title line 1\n   Title line 2\n  "   ',
        ["path/four.md"],
    ),
    # Destination with trailing spaces on its line, multiline title on next line
    (
        '[label5]: path/five.md   \n  "Title line 1   \n   Title line 2"   ',
        ["path/five.md"],
    ),
    # Angle-bracket destination with trailing spaces, multiline title with trailing spaces
    (
        '[label6]: <path/six.md>   \n  "Title line 1   \n   Title line 2"   ',
        ["path/six.md"],
    ),
    # Multiline single-quoted title with trailing spaces
    (
        "[label7]: path/seven.md   \n  'Title line 1   \n   Title line 2   '   ",
        ["path/seven.md"],
    ),
    # Multiline parenthesized title with trailing spaces
    (
        "[label8]: path/eight.md   \n  (Title line 1   \n   Title line 2   )   ",
        ["path/eight.md"],
    ),
    # Parenthesized title with escaped and nested parens
    (
        "[label9]: path/nine.md\n  (Title with \\) escaped and (nested) parens   )   ",
        ["path/nine.md"],
    ),
    # Destination on subsequent line after label, multiline title on line after
    (
        '[label10]:\n  path/ten.md\n  "Multiline   \n   title"   ',
        ["path/ten.md"],
    ),
    # Destination on same line without title
    (
        "[label11]: path/eleven.md   ",
        ["path/eleven.md"],
    ),
    # Up to 3 spaces indentation on definition line
    (
        '   [label12]: path/twelve.md\n     "Indented multiline   \n      title"   ',
        ["path/twelve.md"],
    ),
    # Escaped brackets in label
    (
        '[label\\]with\\]bracket]: path/thirteen.md\n  "Title string"   ',
        ["path/thirteen.md"],
    ),
]

for snippet, expected in cases:
    extracted = find_targets(snippet)
    check(f"find_targets matches: {snippet.splitlines()[0]}", extracted == expected)

# 4. CommonMark blank line rule: title cannot span across blank line
blank_line_doc = """[ref]: path/to/doc.md
  "Title line 1

   Title line 2"
"""
check("blank line breaks title parsing", find_targets(blank_line_doc) == ["path/to/doc.md"])

# 5. Code fences and inline spans are ignored
code_doc = """Here is `[inline](code/inline.md)` and `` `[multi](code/multi.md)` ``.
```markdown
[fence-inline](code/fence.md)
[fence-ref]: code/fence-ref.md
  "Fence title   
   line 2"   
```
Real links:
[real-inline](real/inline.md)
[real-ref]: real/ref.md
  "Real title   
   line 2"   
"""
check(
    "code fences and spans are ignored",
    find_targets(code_doc) == ["real/inline.md", "real/ref.md"],
)

# 6. Negative cases that should not match as reference definitions
negative_cases = [
    # Footnote definition
    "[^1]: This is a footnote text pointing nowhere",
    # 4 spaces indentation is an indented code block
    '    [ref]: path/to/doc.md\n    "Title string"',
]
for neg in negative_cases:
    check(f"negative case ignored: {neg.splitlines()[0]}", find_targets(neg) == [])

# 7. End-to-end check_file tests with temporary files
with tempfile.TemporaryDirectory() as tmpdir:
    td = Path(tmpdir)
    (td / "existing_inline.md").write_text("# Existing Inline", encoding="utf-8")
    (td / "existing_ref.md").write_text("# Existing Ref", encoding="utf-8")

    sub = td / "subdir"
    sub.mkdir()
    (sub / "nested.md").write_text("# Nested", encoding="utf-8")

    source_md = td / "source.md"
    source_content = """# Test Source Document

Inline valid: [Inline](existing_inline.md)
Inline broken: [Broken Inline](missing/inline.md)

Reference definition with multiline title and trailing spaces:
[ref_ok]: existing_ref.md   
  "Valid multiline title   
   line 2   "   

Reference definition with nested path and trailing spaces:
[ref_nested]: subdir/nested.md
  'Nested single quote   
   title'   

Broken reference definition with multiline title and trailing spaces:
[ref_broken]: missing/ref_file.md   
  (Broken parenthesized   
   title   )   

Code block that should be ignored:
```markdown
[ignored_ref]: nonexistent/code.md
  "Ignored Title   
   line 2"   
```

Inline span that should be ignored: `[ignored_inline]: nonexistent/inline.md`

Footnote that should be ignored:
[^note1]: footnote content
"""
    source_md.write_text(source_content, encoding="utf-8")

    mod.broken.clear()
    mod.checked = 0
    check_file(source_md)

    check("checked count is 5", mod.checked == 5)
    check("broken list has exactly 2 entries", len(mod.broken) == 2)
    check(
        "broken list contains missing/inline.md",
        any("missing/inline.md" in b for b in mod.broken),
    )
    check(
        "broken list contains missing/ref_file.md",
        any("missing/ref_file.md" in b for b in mod.broken),
    )
    check(
        "code fences and spans are excluded from broken list",
        not any("nonexistent" in b for b in mod.broken),
    )

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
