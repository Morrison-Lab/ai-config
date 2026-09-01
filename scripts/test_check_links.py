#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2514).

Verifies that:
1. Inline markdown links ([text](target.md)) resolve correctly and report missing targets.
2. Single-line reference link definitions ([label]: target.md) resolve correctly.
3. Reference link definitions with indented destinations on the next line
   ([label]:\n   <target.md> "title") resolve correctly.
4. Variations with angle brackets, titles, anchors, leading indentation, and tabs are supported.
5. Code blocks (fenced) and inline code spans are ignored.
6. External URLs, in-page anchors, and placeholder brackets are skipped.
7. The check-links.py CLI fails (exit 1) on broken links and passes (exit 0) when all resolve.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-links.py"

# Import check_links module dynamically
spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
check_links = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = check_links
spec.loader.exec_module(check_links)

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


def run_check_links_cli(*args: str, cwd: Path = REPO) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def reset_state() -> None:
    check_links.broken.clear()
    check_links.checked = 0


def main() -> int:
    print("Testing check-links.py...")

    # 1. Inline links
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "target.md").write_text("# Target", encoding="utf-8")
        doc = td / "doc.md"
        doc.write_text(
            "Here is an [inline link](target.md) and [with title](target.md \"Title\").\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check("inline links resolve", len(check_links.broken) == 0 and check_links.checked == 2)

    # 2. Broken inline link
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        doc = td / "doc.md"
        doc.write_text("Broken [link](nonexistent.md).\n", encoding="utf-8")
        reset_state()
        check_links.check_file(doc, root=td)
        check("broken inline link detected", len(check_links.broken) == 1)

    # 3. Single-line reference link definitions
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "target.md").write_text("# Target", encoding="utf-8")
        doc = td / "doc.md"
        doc.write_text(
            "[ref1]: target.md\n"
            "[ref2]: <target.md>\n"
            "[ref3]: target.md \"Title\"\n"
            "[ref4]: <target.md> 'Title'\n"
            "[ref5]: target.md (Title)\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "single-line reference definitions resolve",
            len(check_links.broken) == 0 and check_links.checked == 5,
        )

    # 4. Indented destination on next line (Issue #2514)
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "target.md").write_text("# Target", encoding="utf-8")
        (td / "other.md").write_text("# Other", encoding="utf-8")
        doc = td / "doc.md"
        doc.write_text(
            "[ref1]:\n"
            "   <target.md> \"title\"\n"
            "[ref2]:\n"
            "   target.md\n"
            "[ref3]:\n"
            "  <other.md>\n"
            "[ref4]:\n"
            "    <target.md>\n"
            "[ref5]:\n"
            "\t<other.md> \"tab indented\"\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "indented destination on next line resolves",
            len(check_links.broken) == 0 and check_links.checked == 5,
        )

    # 5. Indented destination on next line with broken target
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        doc = td / "doc.md"
        doc.write_text(
            "[broken_ref]:\n"
            "   <missing_target.md> \"title\"\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "broken indented destination detected",
            len(check_links.broken) == 1 and "missing_target.md" in check_links.broken[0],
        )

    # 6. Definition itself indented up to 3 spaces
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "target.md").write_text("# Target", encoding="utf-8")
        doc = td / "doc.md"
        doc.write_text(
            "   [ref_indented]:\n"
            "      <target.md>\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "definition indented up to 3 spaces resolves",
            len(check_links.broken) == 0 and check_links.checked == 1,
        )

    # 7. Anchor preservation and resolution
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "target.md").write_text("# Target", encoding="utf-8")
        doc = td / "doc.md"
        doc.write_text(
            "[ref_anchor]:\n"
            "   <target.md#section-heading> \"title\"\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "destination with anchor resolves target file",
            len(check_links.broken) == 0 and check_links.checked == 1,
        )

    # 8. External targets, anchors, and placeholders skipped
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        doc = td / "doc.md"
        doc.write_text(
            "[ext1]: https://example.com\n"
            "[ext2]: <https://example.com/docs>\n"
            "[ext3]:\n"
            "   <http://example.com>\n"
            "[ext4]:\n"
            "   mailto:user@example.com\n"
            "[anchor]: #local-anchor\n"
            "[placeholder]: <owner>/<repo>\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "external targets, anchors, and placeholders skipped",
            len(check_links.broken) == 0 and check_links.checked == 0,
        )

    # 9. Fenced code and inline backticks ignored
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        doc = td / "doc.md"
        doc.write_text(
            "```markdown\n"
            "[fake_ref]:\n"
            "   <nonexistent_in_code.md>\n"
            "```\n"
            "`[fake_inline]: <nonexistent.md>`\n",
            encoding="utf-8",
        )
        reset_state()
        check_links.check_file(doc, root=td)
        check(
            "fenced code blocks and backticks ignored",
            len(check_links.broken) == 0 and check_links.checked == 0,
        )

    # 10. CLI execution exit code verification
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "shared").mkdir()
        (td / "shared" / "target.md").write_text("# Target", encoding="utf-8")
        (td / "shared" / "doc.md").write_text(
            "[ref]:\n   <target.md>\n",
            encoding="utf-8",
        )
        rc, stdout, stderr = run_check_links_cli("--root", str(td))
        check("CLI passes on valid relative links", rc == 0 and "✓ no broken relative links" in stdout)

    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "shared").mkdir()
        (td / "shared" / "doc.md").write_text(
            "[ref]:\n   <nonexistent_target.md>\n",
            encoding="utf-8",
        )
        rc, stdout, stderr = run_check_links_cli("--root", str(td))
        check("CLI fails on broken relative links", rc == 1 and "1 broken link(s)" in stdout)

    # 11. Baseline repo check runs clean
    rc, stdout, stderr = run_check_links_cli()
    check("CLI runs clean on repo baseline", rc == 0 and "✓ no broken relative links" in stdout)

    print(f"\nSummary: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
