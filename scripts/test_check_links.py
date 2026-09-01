#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2578).

Verifies that:
1. External link schemes and in-page anchors are recognized and skipped.
2. Extensionless markdown targets and directory index/README files resolve.
3. Anchor fragments (#section) on extensionless targets are handled correctly.
4. Broken links (including broken extensionless targets with anchors) are caught.
5. Bare-word placeholders and code-fenced examples are skipped.
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
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

is_external = mod.is_external
resolve_target = mod.resolve_target
check_file = mod.check_file

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
    print("Testing check-links.py...")

    # 1. is_external tests
    check("https link is external", is_external("https://example.com"))
    check("http link is external", is_external("http://example.com"))
    check("mailto link is external", is_external("mailto:user@example.com"))
    check("tel link is external", is_external("tel:+1234567890"))
    check("pure anchor is external/skipped", is_external("#section-header"))
    check("custom scheme is external", is_external("ftp://files.example.com"))
    check("relative md file is not external", not is_external("foo.md"))
    check("relative path with anchor is not external", not is_external("doc#section"))
    check("relative subpath is not external", not is_external("../guide/setup.md"))

    # 2. resolve_target unit tests with temporary file structure
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "direct.md").write_text("# Direct", encoding="utf-8")
        (td / "image.png").write_bytes(b"PNG")
        (td / "extensionless.md").write_text("# Extensionless", encoding="utf-8")

        sub_dir = td / "dir_with_index"
        sub_dir.mkdir()
        (sub_dir / "index.md").write_text("# Index", encoding="utf-8")

        readme_dir = td / "dir_with_readme"
        readme_dir.mkdir()
        (readme_dir / "README.md").write_text("# README", encoding="utf-8")

        nested = td / "nested"
        nested.mkdir()
        (nested / "item.md").write_text("# Item", encoding="utf-8")

        # Direct file resolution
        res = resolve_target(td, "direct.md")
        check("resolve direct .md file", res == (td / "direct.md").resolve())

        res_img = resolve_target(td, "image.png")
        check("resolve direct non-md file", res_img == (td / "image.png").resolve())

        # Direct with anchor
        res_anchor = resolve_target(td, "direct.md#heading")
        check("resolve direct .md with anchor", res_anchor == (td / "direct.md").resolve())

        # Extensionless target resolving to .md
        res_ext = resolve_target(td, "extensionless")
        check("resolve extensionless target", res_ext == (td / "extensionless.md").resolve())

        # Extensionless target with anchor fragment
        res_ext_anchor = resolve_target(td, "extensionless#heading-name")
        check(
            "resolve extensionless target with anchor fragment",
            res_ext_anchor == (td / "extensionless.md").resolve(),
        )

        # Extensionless target with query and anchor
        res_query_anchor = resolve_target(td, "extensionless?raw=1#heading-name")
        check(
            "resolve extensionless target with query and anchor",
            res_query_anchor == (td / "extensionless.md").resolve(),
        )

        # Directory resolving to index.md
        res_index = resolve_target(td, "dir_with_index")
        check("resolve dir to dir or index.md", res_index is not None and res_index.exists())

        res_index_anchor = resolve_target(td, "dir_with_index#heading")
        check(
            "resolve dir with anchor to index.md or dir",
            res_index_anchor is not None and res_index_anchor.exists(),
        )

        # Directory resolving to README.md
        res_readme = resolve_target(td, "dir_with_readme")
        check("resolve dir to README.md or dir", res_readme is not None and res_readme.exists())

        res_readme_anchor = resolve_target(td, "dir_with_readme#section")
        check(
            "resolve dir with anchor to README.md or dir",
            res_readme_anchor is not None and res_readme_anchor.exists(),
        )

        # Nested extensionless target with anchor
        res_nested_anchor = resolve_target(td, "nested/item#details")
        check(
            "resolve nested extensionless target with anchor",
            res_nested_anchor == (nested / "item.md").resolve(),
        )

        # Pure anchor returns None from resolve_target (handled upstream)
        check("pure anchor returns None", resolve_target(td, "#heading") is None)
        check("empty target returns None", resolve_target(td, "") is None)

        # Missing targets return None
        check("missing file returns None", resolve_target(td, "nonexistent.md") is None)
        check(
            "missing extensionless with anchor returns None",
            resolve_target(td, "nonexistent#section") is None,
        )

    # 3. check_file module-level integration tests
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "target.md").write_text("# Target", encoding="utf-8")
        (td / "ext_target.md").write_text("# Ext Target", encoding="utf-8")

        test_doc = td / "test_doc.md"
        test_doc.write_text(
            """# Test Document
Here is a [direct link](target.md#section).
Here is an [extensionless anchor link](ext_target#section).
Here is a [pure anchor](#local-section).
Here is an [external link](https://example.com).
Here is an [angle bracket placeholder](<owner>/<repo>).
Here is an [example placeholder](url).

```markdown
[ignored link in fence](missing_fence_target.md#section)
```

And inline code `[ignored link in code](missing_inline.md#section)` should be ignored.
""",
            encoding="utf-8",
        )

        mod.broken.clear()
        mod.checked = 0
        check_file(test_doc)
        check("valid file produces no broken links", len(mod.broken) == 0)
        check("checked count recorded expected links", mod.checked == 2)

        # Document with broken links
        broken_doc = td / "broken_doc.md"
        broken_doc.write_text(
            """# Broken Doc
[broken direct](missing_file.md#sec)
[broken extensionless](missing_ext#sec)
[broken subpath](missing_dir/sub#sec)
""",
            encoding="utf-8",
        )

        mod.broken.clear()
        mod.checked = 0
        check_file(broken_doc)
        check("broken links detected", len(mod.broken) == 3)
        check("broken targets recorded", any("missing_ext#sec" in b for b in mod.broken))

    # 4. CLI end-to-end execution on current repository
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    check("check-links.py runs cleanly on repo", res.returncode == 0)
    check("check-links output reports success", "no broken relative links" in res.stdout)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
