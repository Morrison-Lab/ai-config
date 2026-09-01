#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2528)."""
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
check("normalize_label uppercase with underscores", normalize_label("MY_LABEL") == "my_label")
check(
    "normalize_label collapses whitespace",
    normalize_label("  MY   \t\n  LABEL  ") == "my label",
)
check("normalize_label empty string", normalize_label("") == "")
check("normalize_label unicode casefold", normalize_label("CAFÉ") == "café")

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

# 4. Full reference links with uppercase and mixed case labels
full_ref_valid = """
Here is a [full reference link][MY-REF].

[my-ref]: ./target.md "Target Title"
"""
check(
    "full reference link with uppercase label matches lowercase definition",
    run_check_file(full_ref_valid, files={"target.md": "ok"}) == [],
)

full_ref_uppercase_def = """
Here is a [full reference link][my_ref].

[MY_REF]: ./target.md "Target Title"
"""
check(
    "full reference link with lowercase label matches uppercase definition",
    run_check_file(full_ref_uppercase_def, files={"target.md": "ok"}) == [],
)

full_ref_both_uppercase = """
Here is a [full reference link][MY_REF].

[MY_REF]: ./TARGET.md "Target Title"
"""
check(
    "full reference link with uppercase label and definition resolving to TARGET.md",
    run_check_file(full_ref_both_uppercase, files={"TARGET.md": "ok"}) == [],
)

full_ref_missing = """
Here is a [broken reference link][MISSING-REF].

[missing-ref]: ./nonexistent.md
"""
broken_full = run_check_file(full_ref_missing)
check("full reference link with uppercase label to missing file is reported broken", len(broken_full) == 1)
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

# 6. Collapsed reference links with uppercase labels
collapsed_valid = """
See [TARGET.MD][].

[target.md]: ./target.md
"""
check(
    "collapsed reference link [LABEL][] matches case-insensitively",
    run_check_file(collapsed_valid, files={"target.md": "ok"}) == [],
)

collapsed_missing = """
See [MISSING.MD][].

[missing.md]: ./missing.md
"""
check(
    "collapsed reference link [LABEL][] is reported broken when target missing",
    len(run_check_file(collapsed_missing)) == 1,
)

# 7. Shortcut reference links with uppercase labels
shortcut_valid = """
See [MY-SHORTCUT] for details.

[my-shortcut]: ./target.md
"""
check(
    "shortcut reference link [UPPERCASE] matches lowercase definition",
    run_check_file(shortcut_valid, files={"target.md": "ok"}) == [],
)

shortcut_uppercase_def = """
See [my-shortcut] for details.

[MY-SHORTCUT]: ./target.md
"""
check(
    "shortcut reference link [lowercase] matches uppercase definition",
    run_check_file(shortcut_uppercase_def, files={"target.md": "ok"}) == [],
)

shortcut_missing = """
See [MY-SHORTCUT] for details.

[my-shortcut]: ./missing.md
"""
check(
    "shortcut reference link [UPPERCASE] is reported broken when target missing",
    len(run_check_file(shortcut_missing)) == 1,
)

# 8. Non-link bracketed prose produces NO false positives
prose_no_defs = """
This is a [NOTE] about matrix[i][j] and regex [A-Za-z0-9] with [TODO] item [1].
Also a [text][UNDEFINED_LABEL] with no matching definition.
"""
check(
    "bracketed prose and undefined references produce zero false positives",
    run_check_file(prose_no_defs) == [],
)

# 9. Code regions (fences and inline spans) are stripped
code_regions = """
```markdown
[fake inline](missing.md)
[fake ref][MISSING-REF]
[MISSING-REF]: missing.md
```

Here is inline code: `[fake link](missing2.md)` and ``[fake ref][MISSING3]``.
"""
check(
    "code blocks and inline code spans do not trigger broken links",
    run_check_file(code_regions) == [],
)

# 10. Unreferenced reference definitions are validated
unreferenced_def_valid = """
Prose without explicit link syntax.

[DOC-REF]: ./target.md
"""
check(
    "unreferenced reference definition with uppercase label to existing file passes",
    run_check_file(unreferenced_def_valid, files={"target.md": "ok"}) == [],
)

unreferenced_def_missing = """
Prose without explicit link syntax.

[DOC-REF]: ./missing.md
"""
check(
    "unreferenced reference definition with uppercase label to missing file is reported broken",
    len(run_check_file(unreferenced_def_missing)) == 1,
)

# 11. First definition takes precedence (CommonMark spec)
first_def_precedence = """
[Link][MY-LABEL]

[my-label]: ./target.md
[MY-LABEL]: ./missing.md
"""
check(
    "first reference definition takes precedence when duplicated with different case",
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
[MY-REF]:
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
