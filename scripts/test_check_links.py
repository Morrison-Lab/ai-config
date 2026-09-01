#!/usr/bin/env python3
"""Regression tests for scripts/check-links.py (ai-config#2532)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_links", Path(__file__).resolve().parent / "check-links.py"
)
if spec is None or spec.loader is None:
    raise ImportError("Could not load scripts/check-links.py")
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


# 1. extract_target helper
check(
    "extract_target: plain destination",
    cl.extract_target("docs/guide.md") == "docs/guide.md",
)
check(
    "extract_target: destination with title",
    cl.extract_target('docs/guide.md "Guide Title"') == "docs/guide.md",
)
check(
    "extract_target: angle-bracket destination",
    cl.extract_target("<docs/guide.md>") == "docs/guide.md",
)
check(
    "extract_target: angle-bracket destination with title",
    cl.extract_target('<docs/guide.md> "Guide Title"') == "docs/guide.md",
)
check(
    "extract_target: angle-bracket destination with spaces",
    cl.extract_target("<docs/my guide.md>") == "docs/my guide.md",
)
check(
    "extract_target: complex mailto with angle brackets",
    cl.extract_target("<mailto:user@domain.tld?subject=Hello%20World&body=Text>")
    == "mailto:user@domain.tld?subject=Hello%20World&body=Text",
)

# 2. is_external recognition
check(
    "is_external: mailto with query parameters",
    cl.is_external("mailto:user@domain.tld?subject=Hello%20World&body=Text"),
)
check(
    "is_external: mailto with complex parameters and multiple recipients",
    cl.is_external("mailto:a@b.com,c@d.com?cc=e@f.com&subject=Test&body=Msg"),
)
check(
    "is_external: angle-bracketed mailto",
    cl.is_external("<mailto:user@domain.tld?subject=Hello%20World&body=Text>"),
)
check(
    "is_external: email autolink",
    cl.is_external("user@domain.tld"),
)
check(
    "is_external: angle-bracketed email autolink",
    cl.is_external("<user@domain.tld>"),
)
check(
    "is_external: email autolink with query",
    cl.is_external("user@domain.tld?subject=Hello"),
)
check(
    "is_external: https URL",
    cl.is_external("https://example.com/path?query=1"),
)
check(
    "is_external: http URL",
    cl.is_external("http://example.com"),
)
check(
    "is_external: tel URL",
    cl.is_external("tel:+1234567890"),
)
check(
    "is_external: in-page anchor",
    cl.is_external("#section-header"),
)
check(
    "is_external: custom protocol with ://",
    cl.is_external("custom-proto://resource/1"),
)
check(
    "is_external: relative file path is not external",
    not cl.is_external("docs/guide.md"),
)
check(
    "is_external: relative path with query/anchor is not external",
    not cl.is_external("docs/guide.md?v=1#sec"),
)

# 3. AUTOLINK regex discrimination
check(
    "AUTOLINK matches mailto autolink with complex query params",
    bool(
        cl.AUTOLINK.search(
            "Contact us at <mailto:user@domain.tld?subject=Hello%20World&body=Text> for info."
        )
    ),
)
check(
    "AUTOLINK matches email autolink",
    bool(cl.AUTOLINK.search("Reach out to <user@domain.tld> directly.")),
)
check(
    "AUTOLINK matches https autolink",
    bool(cl.AUTOLINK.search("See <https://example.com/docs>.")),
)
check(
    "AUTOLINK does not match HTML tags",
    not bool(cl.AUTOLINK.search("<summary>Details</summary><br><div>")),
)
check(
    "AUTOLINK does not match placeholder angle brackets",
    not bool(cl.AUTOLINK.search("Specify <owner>/<repo> as arguments.")),
)

# 4. End-to-end check_file tests with temporary files
with tempfile.TemporaryDirectory() as tmpdir:
    tmp_root = Path(tmpdir)
    doc_dir = tmp_root / "docs"
    doc_dir.mkdir(parents=True)

    target_file = doc_dir / "target.md"
    target_file.write_text("# Target\n", encoding="utf-8")

    test_md = doc_dir / "test.md"
    test_md.write_text(
        """# Sample Document
Here is an autolink: <mailto:user@domain.tld?subject=Hello%20World&body=Text>
Here is an email autolink: <dev@example.org>
Here is a bracketed mailto: [Contact](<mailto:user@domain.tld?subject=Hello%20World&body=Text>)
Here is a valid relative link: [Target](target.md)
Here is an in-page anchor: [Section](#section)
Here is an external link: [GitHub](https://github.com/Morrison-Lab/ai-config)
```markdown
[Ignored In Fence](missing.md)
```
`[Ignored In Code](missing2.md)`
""",
        encoding="utf-8",
    )

    cl.broken = []
    cl.checked = 0
    cl.check_file(test_md)

    check(
        "end-to-end: valid relative link and mailto autolinks produce 0 broken links",
        len(cl.broken) == 0,
    )
    check(
        "end-to-end: exactly 1 relative link checked",
        cl.checked == 1,
    )

    # Document with broken relative link
    bad_md = doc_dir / "bad.md"
    bad_md.write_text(
        """# Bad Links
[Broken](nonexistent.md)
<mailto:user@domain.tld?subject=Hello%20World&body=Text>
""",
        encoding="utf-8",
    )

    cl.broken = []
    cl.checked = 0
    cl.check_file(bad_md)

    check(
        "end-to-end: broken relative link detected",
        len(cl.broken) == 1 and "nonexistent.md" in cl.broken[0],
    )

print(f"\nTotal: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
