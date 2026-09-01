#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2526, ai-config#2538).

Verifies that:
1. External link forms (http(s), mailto, tel, anchors, email autolinks) are recognized.
2. Relative filesystem links resolve accurately against real files.
3. Code blocks and inline code spans are stripped before link extraction.
4. Footnote definitions and references are validated in-file.
5. Autolinks (<https://...>, <mailto:...>) inside footnote definitions
   and prose are recognized as external links and not treated as local filesystem paths.
6. Relative autolinks (<target.md>) inside footnote definitions are validated.
7. HTML tags and angle-bracket placeholders are ignored.
8. CLI invocation executes cleanly over repository files.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-links.py"

sys.path.insert(0, str(REPO / "scripts"))
import importlib.util

spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {SCRIPT}")
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
    check("is_external: mailto with query", cl.is_external("mailto:agent@example.com?subject=Test"))
    check("is_external: email autolink", cl.is_external("user@example.com"))
    check("is_external: tel", cl.is_external("tel:+1234567890"))
    check("is_external: in-page anchor", cl.is_external("#heading-anchor"))
    check("is_external: generic scheme", cl.is_external("custom-scheme://host/path"))
    check("is_external: relative file is not external", not cl.is_external("docs/guide.md"))
    check("is_external: parent relative file is not external", not cl.is_external("../shared/rule.md"))

    # 2. Filesystem inline link validation in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        target_file = tmp_path / "target.md"
        target_file.write_text("# Target\n", encoding="utf-8")

        # 2a. Valid relative link
        valid_md = tmp_path / "valid.md"
        valid_md.write_text("[Target](target.md)\n", encoding="utf-8")
        checked_count, broken_list = run_check_file(valid_md, root=tmp_path)
        check("valid relative link increments checked", checked_count == 1)
        check("valid relative link has no broken links", len(broken_list) == 0)

        # 2b. Missing relative link target
        missing_md = tmp_path / "missing.md"
        missing_md.write_text("[Missing](nonexistent.md)\n", encoding="utf-8")
        checked_count, broken_list = run_check_file(missing_md, root=tmp_path)
        check("missing relative link increments checked", checked_count == 1)
        check("missing relative link reported in broken", len(broken_list) == 1 and "nonexistent.md" in broken_list[0])

        # 2c. Link with anchor and query parameters
        anchor_md = tmp_path / "anchor.md"
        anchor_md.write_text("[Target with anchor](target.md#section-one?ref=123)\n", encoding="utf-8")
        checked_count, broken_list = run_check_file(anchor_md, root=tmp_path)
        check("link with anchor/query resolves to existing target", checked_count == 1 and len(broken_list) == 0)

        # 2d. Angle-bracket wrapped target and title
        title_md = tmp_path / "title.md"
        title_md.write_text('[Wrapped Target](<target.md> "Target Title")\n', encoding="utf-8")
        checked_count, broken_list = run_check_file(title_md, root=tmp_path)
        check("angle-bracket and titled target resolves to existing target", checked_count == 1 and len(broken_list) == 0)

        # 2e. Angle-bracket wrapped external target in markdown link
        ext_angle_md = tmp_path / "ext_angle.md"
        ext_angle_md.write_text('[External Target](<https://example.com/docs>)\n', encoding="utf-8")
        checked_count, broken_list = run_check_file(ext_angle_md, root=tmp_path)
        check("angle-bracket external markdown link is not checked as local file", checked_count == 0 and len(broken_list) == 0)

        # 2f. Links inside code blocks and inline backticks are stripped
        code_md = tmp_path / "code.md"
        code_md.write_text(
            "```markdown\n[Fake Missing](missing-code.md)\n<https://fake-in-code.com>\n```\n"
            "Here is `[Inline Fake](missing-inline.md)` code and `<fake-inline.md>`.\n"
            "[Real Target](target.md)\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(code_md, root=tmp_path)
        check("code block and code span links are stripped", checked_count == 1 and len(broken_list) == 0)

    # 3. Footnote reference, definition, and autolink tests (ai-config#2526, ai-config#2538)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        doc_other = tmp_path / "other.md"
        doc_other.write_text("# Other doc\n", encoding="utf-8")

        # 3a. Footnote definitions with autolinks (https, mailto, email)
        fn_autolinks = tmp_path / "fn_autolinks.md"
        fn_autolinks.write_text(
            "Here is a claim[^1] with a contact note[^contact] and standalone URL[^url].\n\n"
            "[^1]: See research at <https://example.com/paper.pdf> for details.\n"
            "[^contact]: Send questions to <mailto:maintainer@example.com> or <dev@example.org>.\n"
            "[^url]: <https://example.com/standalone>\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(fn_autolinks, root=tmp_path)
        check("footnote autolinks are recognized as external (not flagged as missing local files)", len(broken_list) == 0)
        check("footnote references increment checked count", checked_count == 3)

        # 3b. Footnote definitions with valid relative autolinks and inline links
        fn_relative = tmp_path / "fn_relative.md"
        fn_relative.write_text(
            "See note[^note1] and note[^note2].\n\n"
            "[^note1]: Refer to <other.md> for details.\n"
            "[^note2]: Refer to [Other Doc](other.md) as well.\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(fn_relative, root=tmp_path)
        check("valid relative autolink and inline link inside footnote resolve cleanly", len(broken_list) == 0)
        check("footnote refs and relative links counted in checked", checked_count == 4)

        # 3c. Footnote definitions with broken relative autolink and inline link
        fn_broken = tmp_path / "fn_broken.md"
        fn_broken.write_text(
            "See note[^bad1] and note[^bad2].\n\n"
            "[^bad1]: Broken autolink <nonexistent-auto.md>.\n"
            "[^bad2]: Broken inline [Missing](nonexistent-inline.md).\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(fn_broken, root=tmp_path)
        check(
            "broken relative autolink and inline link in footnotes are flagged",
            len(broken_list) == 2
            and any("nonexistent-auto.md" in b for b in broken_list)
            and any("nonexistent-inline.md" in b for b in broken_list),
        )

        # 3d. Dangling footnote reference (missing definition)
        fn_dangling = tmp_path / "fn_dangling.md"
        fn_dangling.write_text(
            "This reference[^missing-def] has no definition in the file.\n\n"
            "[^other]: Unrelated footnote.\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(fn_dangling, root=tmp_path)
        check("dangling footnote reported as broken", len(broken_list) == 1 and "[^missing-def]" in broken_list[0])

    # 4. General autolinks and HTML tag filtering in prose
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        guide_file = tmp_path / "guide.md"
        guide_file.write_text("# Guide\n", encoding="utf-8")

        prose_md = tmp_path / "prose.md"
        prose_md.write_text(
            "Here is <https://example.com>, <mailto:user@example.com>, and <guide.md>.\n"
            "<details><summary>Click here</summary>\n"
            "Inside details: <guide.md>\n"
            "</details>\n"
            "Angle-bracket placeholder: <owner>/<repo> and <placeholder>.\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(prose_md, root=tmp_path)
        check("prose autolinks resolve and HTML tags / placeholders ignored", checked_count == 2 and len(broken_list) == 0)

        prose_broken_md = tmp_path / "prose_broken.md"
        prose_broken_md.write_text(
            "Broken relative autolink: <missing-guide.md>.\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(prose_broken_md, root=tmp_path)
        check("broken relative autolink in prose flagged", len(broken_list) == 1 and "missing-guide.md" in broken_list[0])

    # 5. Reference link definitions
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ref_target = tmp_path / "ref_target.md"
        ref_target.write_text("# Target\n", encoding="utf-8")

        ref_md = tmp_path / "ref.md"
        ref_md.write_text(
            "See [Target Ref][target-ref] and [External Ref][ext-ref].\n\n"
            "[target-ref]: ref_target.md\n"
            "[ext-ref]: https://example.com\n"
            "[ext-angle]: <https://example.com>\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(ref_md, root=tmp_path)
        check("reference link definition to existing file succeeds", checked_count == 1 and len(broken_list) == 0)

        ref_broken_md = tmp_path / "ref_broken.md"
        ref_broken_md.write_text(
            "See [Broken][bad-ref].\n\n"
            "[bad-ref]: missing-ref.md\n",
            encoding="utf-8",
        )
        checked_count, broken_list = run_check_file(ref_broken_md, root=tmp_path)
        check("reference link definition to missing file is flagged", len(broken_list) == 1 and "missing-ref.md" in broken_list[0])

    # 6. CLI invocation over repository
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
