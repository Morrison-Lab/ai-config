#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2524).

Verifies that:
1. Markdown inline links with angle-bracketed destinations and inline titles
   (e.g. `[label](<path/to/file.md> "Title")`, `'Title'`, `(Title)`) are correctly
   extracted and verified against relative targets without corrupting the path.
2. Angle-bracketed destinations without titles (`[label](<path/to/file.md>)`) resolve.
3. Angle-bracketed destinations with spaces in filename (`<path/to/my file.md>`) resolve.
4. Bare destinations with and without titles (`path/to/file.md "Title"`) resolve.
5. External links, in-page anchors, and angle-bracket placeholders (`<owner>/<repo>`)
   are skipped and not treated as broken relative links.
6. Fenced code blocks and inline backtick code spans are ignored.
7. Missing relative targets are detected and cause non-zero exit codes.
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
check_links = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = check_links
spec.loader.exec_module(check_links)

extract_target = check_links.extract_target

passes = 0
failures = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name} {extra}")


def run_script(*args, cwd: Path = REPO) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_extract_target() -> None:
    # Angle bracket destinations with various title styles
    check(
        "angle bracket with double-quoted title",
        extract_target('<path/to/file.md> "Optional Title"') == "path/to/file.md",
    )
    check(
        "angle bracket with single-quoted title",
        extract_target("<path/to/file.md> 'Optional Title'") == "path/to/file.md",
    )
    check(
        "angle bracket with parenthesized title",
        extract_target("<path/to/file.md> (Optional Title)") == "path/to/file.md",
    )
    check(
        "angle bracket without title",
        extract_target("<path/to/file.md>") == "path/to/file.md",
    )
    check(
        "angle bracket with internal whitespace",
        extract_target('<\t path/to/file.md \t> \t "Title"') == "path/to/file.md",
    )
    check(
        "angle bracket with space in filename",
        extract_target('<path/to/my doc.md> "Title"') == "path/to/my doc.md",
    )
    check(
        "angle bracket with anchor and title",
        extract_target('<path/to/file.md#section-name> "Title"')
        == "path/to/file.md#section-name",
    )
    check(
        "angle bracket with query parameter and title",
        extract_target('<path/to/file.md?v=1&b=2> "Title"')
        == "path/to/file.md?v=1&b=2",
    )
    check(
        "angle bracket with multiline title",
        extract_target('<path/to/file.md>\n"Multiline\nTitle"') == "path/to/file.md",
    )
    check(
        "angle bracket external link with title",
        extract_target('<https://example.com/page> "Title"')
        == "https://example.com/page",
    )
    check(
        "angle bracket in-page anchor with title",
        extract_target('<#section-anchor> "Title"') == "#section-anchor",
    )

    # Bare destinations with and without titles
    check(
        "bare destination with double-quoted title",
        extract_target('path/to/file.md "Optional Title"') == "path/to/file.md",
    )
    check(
        "bare destination with single-quoted title",
        extract_target("path/to/file.md 'Optional Title'") == "path/to/file.md",
    )
    check(
        "bare destination with parenthesized title",
        extract_target("path/to/file.md (Optional Title)") == "path/to/file.md",
    )
    check(
        "bare destination without title",
        extract_target("path/to/file.md") == "path/to/file.md",
    )
    check(
        "bare destination with whitespace and tabs",
        extract_target('path/to/file.md\t\t"Title"') == "path/to/file.md",
    )
    check(
        "bare destination with anchor and title",
        extract_target('path/to/file.md#heading "Title"') == "path/to/file.md#heading",
    )

    # Placeholders and empty values
    check(
        "angle placeholder <owner>/<repo> preserved for downstream filter",
        extract_target("<owner>/<repo>") == "<owner>/<repo>",
    )
    check(
        "angle placeholder <owner>/<repo>/path preserved for downstream filter",
        extract_target("<owner>/<repo>/file.md") == "<owner>/<repo>/file.md",
    )
    check("empty target returns empty", extract_target("") == "")
    check("whitespace-only target returns empty", extract_target("   \t\n") == "")


def test_file_checking_and_resolution() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        docs = root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        target_file = docs / "target.md"
        target_file.write_text("# Target doc\n", encoding="utf-8")

        space_file = docs / "with space.md"
        space_file.write_text("# Target doc with space\n", encoding="utf-8")

        # Test valid links in various syntaxes
        valid_md = root / "valid.md"
        valid_md.write_text(
            "# Valid Links\n\n"
            "- [link 1](<docs/target.md> \"Double Quote Title\")\n"
            "- [link 2](<docs/target.md> 'Single Quote Title')\n"
            "- [link 3](<docs/target.md> (Paren Title))\n"
            "- [link 4](<docs/target.md>)\n"
            "- [link 5](<docs/target.md#anchor> \"Title with Anchor\")\n"
            "- [link 6](<docs/with space.md> \"Title with Spaces\")\n"
            "- [link 7](docs/target.md \"Bare Title\")\n"
            "- [link 8](docs/target.md)\n"
            "- [ext](<https://example.com> \"External\")\n"
            "- [anchor](<#local-heading> \"Local Anchor\")\n"
            "- [placeholder](<owner>/<repo>/file.md)\n"
            "- [bare placeholder](url)\n"
            "\n```markdown\n"
            "[fenced broken](<docs/missing_fenced.md> \"Title\")\n"
            "```\n\n"
            "Here is inline `[inline broken](<docs/missing_inline.md> \"Title\")`.\n",
            encoding="utf-8",
        )

        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(valid_md, root=root)

        check("valid file has 0 broken links", len(check_links.broken) == 0)
        # 8 valid relative links checked (links 1..8)
        check(
            "valid file checks exactly 8 relative links",
            check_links.checked == 8,
            f"got {check_links.checked}",
        )

        # Test missing / broken links
        broken_md = root / "broken.md"
        broken_md.write_text(
            "# Broken Links\n\n"
            "- [broken 1](<docs/nonexistent.md> \"Double Quote Title\")\n"
            "- [broken 2](<docs/nonexistent2.md> 'Single Quote Title')\n"
            "- [broken 3](docs/nonexistent3.md \"Bare Title\")\n",
            encoding="utf-8",
        )

        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(broken_md, root=root)

        check("broken file detects 3 broken links", len(check_links.broken) == 3)
        check(
            "broken file records formatted missing target paths",
            any("docs/nonexistent.md" in b for b in check_links.broken)
            and any("docs/nonexistent2.md" in b for b in check_links.broken)
            and any("docs/nonexistent3.md" in b for b in check_links.broken),
        )


def test_cli_execution() -> None:
    # 1. Live repository should pass cleanly
    rc, stdout, stderr = run_script()
    check(
        "live check-links.py runs cleanly (exit 0)",
        rc == 0 and "✓ no broken relative links" in stdout,
        f"rc={rc}, out={stdout}, err={stderr}",
    )

    # 2. Subprocess in a temporary directory with broken link should fail with exit 1
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        (tmp_root / "skills").mkdir(parents=True, exist_ok=True)
        (tmp_root / "skills" / "test.md").write_text(
            "- [broken](<missing.md> \"Title\")\n", encoding="utf-8"
        )

        # Run script with tmp_root by testing via Python invocation
        code = (
            f"import sys; from pathlib import Path; "
            f"sys.path.insert(0, '{REPO}/scripts'); "
            f"import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('cl', '{SCRIPT}'); "
            f"cl = importlib.util.module_from_spec(spec); "
            f"spec.loader.exec_module(cl); "
            f"cl.ROOT = Path('{tmp_root}'); "
            f"cl.main()"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        check(
            "broken link causes CLI to exit 1",
            proc.returncode == 1 and "1 broken link(s)" in proc.stdout,
            f"rc={proc.returncode}, out={proc.stdout}, err={proc.stderr}",
        )


def main() -> int:
    print("Testing check-links.py...")
    test_extract_target()
    test_file_checking_and_resolution()
    test_cli_execution()

    print(f"\nResults: {passes} passed, {failures} failed")
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
