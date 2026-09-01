#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2522)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-links.py"
spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot load {SCRIPT}")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

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


# 1. Autolink URI extraction in markdown tables with adjacent text
table_doc = """| Column A | Column B |
| --- | --- |
| Click <https://github.com> here | Visit <http://example.com/docs> now |
| Text before<https://api.github.com/v1>text after | Contact <support@example.org> |
|<https://bare.example.com>| <user@domain.tld> |
| Parenthetical (<https://morrisonlab.org>) | Trailing punctuation <https://test.com>! |
"""

table_links = cl.extract_links(table_doc)
check("extracts https autolink with adjacent text", "https://github.com" in table_links)
check("extracts http autolink with path", "http://example.com/docs" in table_links)
check("extracts autolink without space boundaries", "https://api.github.com/v1" in table_links)
check("extracts email autolink in table cell", "support@example.org" in table_links)
check("extracts tight table autolink", "https://bare.example.com" in table_links)
check("extracts second email autolink", "user@domain.tld" in table_links)
check("extracts autolink in parentheses", "https://morrisonlab.org" in table_links)
check("extracts autolink before exclamation", "https://test.com" in table_links)

# 2. External classification
check("https:// is external", cl.is_external("https://github.com"))
check("http:// is external", cl.is_external("http://example.com"))
check("mailto: is external", cl.is_external("mailto:user@domain.tld"))
check("email address is external", cl.is_external("user@domain.tld"))
check("tel: is external", cl.is_external("tel:+1234567890"))
check("anchor # is external", cl.is_external("#heading"))
check("relative path is not external", not cl.is_external("relative/path/to/file.md"))
check("parent relative path is not external", not cl.is_external("../shared/workflow/rule.md"))

# 3. Standard markdown link extraction
md_links_doc = """
[Standard Link](shared/workflow/rule.md)
[Angle Bracket Link](<shared/workflow/other.md>)
[With Title](shared/workflow/title.md "Optional Title")
[External Link](https://github.com/Morrison-Lab/ai-config)
"""
md_links = cl.extract_links(md_links_doc)
check("extracts standard relative link", "shared/workflow/rule.md" in md_links)
check("extracts angle bracket relative link", "shared/workflow/other.md" in md_links)
check("extracts link stripping title", "shared/workflow/title.md" in md_links)
check("extracts external markdown link", "https://github.com/Morrison-Lab/ai-config" in md_links)

# 4. Code spans and fenced blocks ignore autolinks
code_doc = """
Here is an autolink: <https://github.com>.
Here is inline code: `<https://ignored.com>` and `<ignored@example.com>`.

```markdown
| Table in code | <https://code-table.com> |
```
"""
code_links = cl.extract_links(code_doc)
check("extracts prose autolink", "https://github.com" in code_links)
check("ignores inline code autolink", "https://ignored.com" not in code_links)
check("ignores inline code email autolink", "ignored@example.com" not in code_links)
check("ignores fenced code autolink", "https://code-table.com" not in code_links)

# 5. Angle-bracket placeholders and HTML tags are not autolinks
placeholder_doc = """
Check <owner>/<repo> or <placeholder> for info.
Also <div> and <br> tags.
"""
placeholder_links = cl.extract_links(placeholder_doc)
check("ignores angle bracket placeholders", len(placeholder_links) == 0)

# 6. End-to-end check_file test in temp directory
with tempfile.TemporaryDirectory() as tmpdir:
    tmppath = Path(tmpdir)
    target_file = tmppath / "existing.md"
    target_file.write_text("# Target\n", encoding="utf-8")

    test_file = tmppath / "test.md"
    test_file.write_text(
        """# Sample

| Feature | Link |
| --- | --- |
| Existing | [Relative](existing.md) |
| Web | Click <https://github.com> here |
| Contact | Email <support@domain.org> |
| Tight | |<https://example.com/api>| |
""",
        encoding="utf-8",
    )

    # Save and reset state
    saved_broken = list(cl.broken)
    saved_checked = cl.checked
    cl.broken = []
    cl.checked = 0

    cl.check_file(test_file)

    check("check_file found 1 valid relative link", cl.checked == 1)
    check("check_file reported no broken links for autolinks in table", len(cl.broken) == 0)

    # Now add a broken link
    broken_file = tmppath / "broken.md"
    broken_file.write_text(
        """# Broken Sample
| Feature | Link |
| --- | --- |
| Missing | [Missing](does_not_exist.md) |
| Web | <https://github.com> |
""",
        encoding="utf-8",
    )
    cl.check_file(broken_file)
    check("check_file detected broken relative link", len(cl.broken) == 1)

    # Restore state
    cl.broken = saved_broken
    cl.checked = saved_checked

print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
