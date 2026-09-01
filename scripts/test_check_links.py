#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2538).

Verifies that:
1. Relative markdown links point to existing files.
2. External links (http, https, mailto, tel, in-page #anchors) are skipped.
3. Code blocks (fences) and inline code spans are stripped before checking.
4. Footnote references ([^1], [^label]) and definitions ([^1]:) are recognized.
5. In-file footnote anchors are validated without resolving against the filesystem.
6. Missing footnote definitions are reported as broken links.
7. Relative links inside footnote definitions are checked against the filesystem.
8. Reference-style link definitions ([ref]: target) are checked against the filesystem.
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
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot load spec from {SCRIPT}")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

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


def run_check_file(md: Path, root: Path | None = None) -> tuple[int, list[str]]:
    """Run check_file with isolated counters."""
    orig_checked = cl.checked
    orig_broken = list(cl.broken)
    cl.checked = 0
    cl.broken = []
    try:
        cl.check_file(md, root=root if root is not None else md.parent)
        return cl.checked, list(cl.broken)
    finally:
        cl.checked = orig_checked
        cl.broken = orig_broken


def main() -> int:
    print("Testing check-links.py...")

    # 1. is_external tests
    check("is_external: https URL", cl.is_external("https://example.com/foo"))
    check("is_external: http URL", cl.is_external("http://example.com/foo"))
    check("is_external: mailto", cl.is_external("mailto:agent@example.com"))
    check("is_external: tel", cl.is_external("tel:+1234567890"))
    check("is_external: in-page anchor", cl.is_external("#heading-anchor"))
    check("is_external: generic scheme", cl.is_external("custom-scheme://host/path"))
    check("is_external: relative file is not external", not cl.is_external("docs/guide.md"))
    check("is_external: parent relative file is not external", not cl.is_external("../shared/rule.md"))

    # 2. Filesystem link validation in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        target_file = tmp_path / "target.md"
        target_file.write_text("# Target\n", encoding="utf-8")

        # 2a. Valid relative link
        valid_md = tmp_path / "valid.md"
        valid_md.write_text("[Target](target.md)\n", encoding="utf-8")
        checked, broken = run_check_file(valid_md, root=tmp_path)
        check("valid relative link increments checked", checked == 1)
        check("valid relative link has no broken links", len(broken) == 0)

        # 2b. Missing relative link target
        missing_md = tmp_path / "missing.md"
        missing_md.write_text("[Missing](nonexistent.md)\n", encoding="utf-8")
        checked, broken = run_check_file(missing_md, root=tmp_path)
        check("missing relative link increments checked", checked == 1)
        check("missing relative link reported in broken", len(broken) == 1 and "nonexistent.md" in broken[0])

        # 2c. Link with anchor and query parameters
        anchor_md = tmp_path / "anchor.md"
        anchor_md.write_text("[Target with anchor](target.md#section-one?ref=123)\n", encoding="utf-8")
        checked, broken = run_check_file(anchor_md, root=tmp_path)
        check("link with anchor/query resolves to existing target", checked == 1 and len(broken) == 0)

        # 2d. Angle-bracket wrapped target and title
        title_md = tmp_path / "title.md"
        title_md.write_text('[Wrapped Target](<target.md> "Target Title")\n', encoding="utf-8")
        checked, broken = run_check_file(title_md, root=tmp_path)
        check("angle-bracket and titled target resolves to existing target", checked == 1 and len(broken) == 0)

        # 2e. Links inside code blocks and inline backticks are stripped
        code_md = tmp_path / "code.md"
        code_md.write_text(
            "```markdown\n[Fake Missing](missing-code.md)\n```\n"
            "Here is `[Inline Fake](missing-inline.md)` code.\n"
            "[Real Target](target.md)\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(code_md, root=tmp_path)
        check("code block links are stripped", checked == 1 and len(broken) == 0)

    # 3. Footnote reference and definition tests (ai-config#2538)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        doc_other = tmp_path / "other.md"
        doc_other.write_text("# Other doc\n", encoding="utf-8")

        # 3a. Valid footnote reference and definition
        fn_valid = tmp_path / "fn_valid.md"
        fn_valid.write_text(
            "Here is a claim[^1] supported by research[^bench-2026].\n\n"
            "[^1]: This is the first footnote text.\n"
            "   [^bench-2026]: Indented footnote definition.\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(fn_valid, root=tmp_path)
        check("valid footnotes increment checked count", checked == 2)
        check("valid footnotes have no broken links (not resolved on disk)", len(broken) == 0)

        # 3b. Multiple references to the same footnote definition
        fn_multi = tmp_path / "fn_multi.md"
        fn_multi.write_text(
            "First ref[^1] and second ref[^1] to the same definition.\n\n"
            "[^1]: Shared footnote definition.\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(fn_multi, root=tmp_path)
        check("multiple footnote references both succeed", checked == 2 and len(broken) == 0)

        # 3c. Dangling footnote reference (missing definition)
        fn_dangling = tmp_path / "fn_dangling.md"
        fn_dangling.write_text(
            "This reference[^missing-def] has no definition in the file.\n\n"
            "[^other]: Unrelated footnote.\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(fn_dangling, root=tmp_path)
        check("dangling footnote reported as broken", len(broken) == 1 and "[^missing-def]" in broken[0])

        # 3d. Footnote reference inside code is ignored
        fn_code = tmp_path / "fn_code.md"
        fn_code.write_text(
            "```\n[^not-a-footnote]\n```\n"
            "Inline `[^also-code]` example.\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(fn_code, root=tmp_path)
        check("footnote in code is not treated as active reference", checked == 0 and len(broken) == 0)

        # 3e. Footnote definition containing relative link
        fn_link_valid = tmp_path / "fn_link_valid.md"
        fn_link_valid.write_text(
            "See note[^note].\n\n"
            "[^note]: For more info see [the other document](other.md).\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(fn_link_valid, root=tmp_path)
        check("relative link inside footnote definition is checked", checked == 2 and len(broken) == 0)

        # 3f. Footnote definition containing broken relative link
        fn_link_broken = tmp_path / "fn_link_broken.md"
        fn_link_broken.write_text(
            "See note[^note].\n\n"
            "[^note]: For more info see [missing doc](nonexistent.md).\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(fn_link_broken, root=tmp_path)
        check("broken relative link inside footnote definition is flagged", len(broken) == 1 and "nonexistent.md" in broken[0])

    # 4. Reference link definition tests
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ref_target = tmp_path / "guide.md"
        ref_target.write_text("# Guide\n", encoding="utf-8")

        ref_md = tmp_path / "ref.md"
        ref_md.write_text(
            "See the [User Guide][guide-ref].\n\n"
            "[guide-ref]: guide.md\n"
            "[external-ref]: https://example.com\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(ref_md, root=tmp_path)
        check("reference link definition to existing file succeeds", checked == 1 and len(broken) == 0)

        ref_broken_md = tmp_path / "ref_broken.md"
        ref_broken_md.write_text(
            "See [Broken][bad-ref].\n\n"
            "[bad-ref]: missing-guide.md\n",
            encoding="utf-8",
        )
        checked, broken = run_check_file(ref_broken_md, root=tmp_path)
        check("reference link definition to missing file is flagged", len(broken) == 1 and "missing-guide.md" in broken[0])

    # 5. CLI invocation over repository
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    check("CLI check-links.py runs cleanly on repo (exit 0)", res.returncode == 0)
    check("CLI output indicates no broken relative links", "✓ no broken relative links" in res.stdout)

    print(f"\nResults: {passes} passed, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
