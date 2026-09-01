#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2535 / ai-config#2842)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

normalize_label = mod.normalize_label
is_external = mod.is_external
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


def run_check_file(content: str, *, files: dict[str, str] | None = None) -> list[str]:
    """Helper to run check_file on markdown in an isolated temp directory."""
    mod.broken.clear()
    mod.checked = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        doc = root / "test.md"
        doc.write_text(content, encoding="utf-8")
        if files:
            for relpath, text in files.items():
                p = root / relpath
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
        check_file(doc, root=root)
        return list(mod.broken)


# 1. Label normalization
check("normalize_label lowercase", normalize_label("MY-LABEL") == "my-label")
check(
    "normalize_label collapses whitespace",
    normalize_label("  my   \t\n  label  ") == "my label",
)
check("normalize_label empty string", normalize_label("") == "")

# 2. External links detection
check("is_external http", is_external("http://example.com"))
check("is_external https", is_external("https://example.com/foo.md"))
check("is_external mailto", is_external("mailto:user@example.com"))
check("is_external tel", is_external("tel:+1234567890"))
check("is_external anchor", is_external("#section-heading"))
check("is_external custom scheme", is_external("custom://resource"))
check("is_external relative path is False", not is_external("./foo/bar.md"))

# 3. Inline links
check(
    "inline link to existing file passes",
    run_check_file("[click here](./target.md)", files={"target.md": "ok"}) == [],
)
check(
    "inline link to missing file is reported broken",
    len(run_check_file("[click here](./missing.md)")) == 1,
)
check(
    "inline link with anchor and query string resolves path part",
    run_check_file("[anchor](./target.md#heading?query=1)", files={"target.md": "ok"})
    == [],
)
check(
    "inline link with angle brackets resolves path",
    run_check_file("[bracket](<./target.md>)", files={"target.md": "ok"}) == [],
)
check(
    "inline link with title resolves path",
    run_check_file('[titled](./target.md "My Title")', files={"target.md": "ok"})
    == [],
)

# 4. Full reference links
full_ref_valid = """
Here is a [full reference link][my-ref].

[my-ref]: ./target.md "Target Title"
"""
check(
    "full reference link to existing file passes",
    run_check_file(full_ref_valid, files={"target.md": "ok"}) == [],
)

full_ref_missing = """
Here is a [broken reference link][missing-ref].

[missing-ref]: ./nonexistent.md
"""
broken_full = run_check_file(full_ref_missing)
check("full reference link to missing file is reported broken", len(broken_full) == 1)
check(
    "broken report contains target path",
    len(broken_full) == 1 and "./nonexistent.md" in broken_full[0],
)

# 5. Case-insensitive and whitespace-normalized full reference links
full_ref_case = """
See [this document][MY TARGET].

[my   target]: ./target.md
"""
check(
    "full reference link matches case-insensitively with normalized whitespace",
    run_check_file(full_ref_case, files={"target.md": "ok"}) == [],
)

# 6. Collapsed reference links
collapsed_valid = """
See [target.md][].

[target.md]: ./target.md
"""
check(
    "collapsed reference link [label][] passes when target exists",
    run_check_file(collapsed_valid, files={"target.md": "ok"}) == [],
)

collapsed_missing = """
See [missing.md][].

[missing.md]: ./missing.md
"""
check(
    "collapsed reference link [label][] is reported broken when target missing",
    len(run_check_file(collapsed_missing)) == 1,
)

# 7. Shortcut reference links
shortcut_valid = """
See [my-shortcut] for details.

[my-shortcut]: ./target.md
"""
check(
    "shortcut reference link [label] passes when target exists",
    run_check_file(shortcut_valid, files={"target.md": "ok"}) == [],
)

shortcut_missing = """
See [my-shortcut] for details.

[my-shortcut]: ./missing.md
"""
check(
    "shortcut reference link [label] is reported broken when target missing",
    len(run_check_file(shortcut_missing)) == 1,
)

# 8. Non-link bracketed prose produces NO false positives
prose_no_defs = """
This is a [NOTE] about matrix[i][j] and regex [A-Za-z0-9] with [TODO] item [1].
Also a [text][undefined_label] with no matching definition.
"""
check(
    "bracketed prose and undefined references produce zero false positives",
    run_check_file(prose_no_defs) == [],
)

# 9. Code regions (fences and inline spans) are stripped
code_regions = """
```markdown
[fake inline](missing.md)
[fake ref][missing-ref]
[missing-ref]: missing.md
```

Here is inline code: `[fake link](missing2.md)` and ``[fake ref][missing3]``.
"""
check(
    "code blocks and inline code spans do not trigger broken links",
    run_check_file(code_regions) == [],
)

# 10. Unreferenced reference definitions are validated
unreferenced_def_valid = """
Prose without explicit link syntax.

[doc-ref]: ./target.md
"""
check(
    "unreferenced reference definition to existing file passes",
    run_check_file(unreferenced_def_valid, files={"target.md": "ok"}) == [],
)

unreferenced_def_missing = """
Prose without explicit link syntax.

[doc-ref]: ./missing.md
"""
check(
    "unreferenced reference definition to missing file is reported broken",
    len(run_check_file(unreferenced_def_missing)) == 1,
)

# 11. First definition takes precedence (CommonMark spec)
first_def_precedence = """
[Link][my-label]

[my-label]: ./target.md
[my-label]: ./missing.md
"""
check(
    "first reference definition takes precedence when duplicated",
    run_check_file(first_def_precedence, files={"target.md": "ok"}) == [],
)

# 12. Placeholder and pure in-page anchors are skipped
placeholders = """
[repo link](<owner>/<repo>)
[generic link](url)
[section link](#heading-anchor)
"""
check(
    "placeholders and pure in-page anchors are skipped",
    run_check_file(placeholders) == [],
)

# 13. Multiline reference definition
multiline_def = """
[my-ref]:
  ./target.md
"""
check(
    "multiline reference definition resolves target path",
    run_check_file(
        "[click][my-ref]\n" + multiline_def, files={"target.md": "ok"}
    )
    == [],
)

print(f"\n{passed} passed, {failed} failed")
if failed:
    sys.exit(1)
