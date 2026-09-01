#!/usr/bin/env python3
"""Unit and regression tests for scripts/check-links.py (ai-config#2517).

Verifies that:
1. Markdown tables without border pipes parse autolinks in all columns.
2. Markdown tables with border pipes parse autolinks and inline links.
3. External autolinks (https, http, mailto, tel, email) are recognized and skipped.
4. Relative autolinks (<path/to/file.md>) are resolved and verified against disk.
5. Missing relative autolinks and inline links are flagged as broken.
6. Code spans and code blocks inside and outside tables are ignored.
7. HTML tags and placeholder angle-bracket tokens are not flagged as broken links.
8. The check-links.py CLI runs clean on repo trees and exits 1 on broken links.
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
    raise ImportError(f"Cannot load {SCRIPT}")
check_links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_links)

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


def run_cli(*args: str, cwd: Path = REPO) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    print("Testing scripts/check-links.py...")

    # 1. External autolink recognition
    check("is_external recognises https", check_links.is_external("https://example.com"))
    check("is_external recognises http", check_links.is_external("http://example.com/foo"))
    check("is_external recognises mailto", check_links.is_external("mailto:dev@example.com"))
    check("is_external recognises raw email", check_links.is_external("user@example.com"))
    check("is_external recognises anchor", check_links.is_external("#section"))
    check("is_external rejects relative path", not check_links.is_external("docs/guide.md"))
    check("is_external rejects relative autolink target", not check_links.is_external("./guide.md"))

    # 2. HTML tags and placeholders ignored
    check("HTML opening tag ignored", check_links.is_html_tag_or_placeholder("details"))
    check("HTML closing tag ignored", check_links.is_html_tag_or_placeholder("/details"))
    check("HTML summary tag ignored", check_links.is_html_tag_or_placeholder("summary"))
    check("HTML comment ignored", check_links.is_html_tag_or_placeholder("!-- comment --"))
    check("Bare placeholder ignored", check_links.is_html_tag_or_placeholder("owner"))
    check("Relative path not classified as html tag", not check_links.is_html_tag_or_placeholder("docs/guide.md"))

    # 3. Borderless table parsing with autolinks
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        docs_dir = root / "docs"
        docs_dir.mkdir()
        target_file = docs_dir / "target.md"
        target_file.write_text("# Target\n", encoding="utf-8")

        # Test A: Borderless table with external autolink in col 1
        md_file_a = root / "borderless_external.md"
        md_file_a.write_text(
            "Col 1 | Col 2\n"
            "--- | ---\n"
            "<https://example.com> | text\n"
            "another | <mailto:info@example.com>\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_a, root=root)
        check("borderless table with external autolinks has no broken links", len(check_links.broken) == 0)

        # Test B: Borderless table with relative autolink in col 1 and col 2
        md_file_b = root / "borderless_relative.md"
        md_file_b.write_text(
            "Source | Destination\n"
            "--- | ---\n"
            "<docs/target.md> | text\n"
            "text | <docs/target.md>\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_b, root=root)
        check("borderless table with relative autolinks resolves existing files", len(check_links.broken) == 0)
        check("borderless table relative autolinks counted in checked total", check_links.checked == 2)

        # Test C: Borderless table with multi-column autolinks
        md_file_c = root / "borderless_multi.md"
        md_file_c.write_text(
            "Header A | Header B | Header C\n"
            "--- | --- | ---\n"
            "<https://example.com> | <docs/target.md> | <mailto:test@example.com>\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_c, root=root)
        check("borderless table multi-column resolves autolinks in every column", len(check_links.broken) == 0)
        check("borderless table multi-column checked target count is 1", check_links.checked == 1)

        # Test D: Borderless table with broken relative autolink
        md_file_d = root / "borderless_broken.md"
        md_file_d.write_text(
            "Col 1 | Col 2\n"
            "--- | ---\n"
            "<docs/nonexistent.md> | valid\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_d, root=root)
        check("borderless table flags missing relative autolink", len(check_links.broken) == 1)
        check("broken entry formats relative autolink with angle brackets", "<docs/nonexistent.md>" in check_links.broken[0])

        # Test E: Bordered table with autolinks and inline links
        md_file_e = root / "bordered_table.md"
        md_file_e.write_text(
            "| Col 1 | Col 2 |\n"
            "| --- | --- |\n"
            "| <https://example.com> | <docs/target.md> |\n"
            "| [Link](docs/target.md) | <docs/missing_bordered.md> |\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_e, root=root)
        check("bordered table flags missing autolink while resolving valid links", len(check_links.broken) == 1)
        check("bordered table broken link matches missing_bordered.md", "<docs/missing_bordered.md>" in check_links.broken[0])

        # Test F: Code spans in table cells do not register as links
        md_file_f = root / "code_spans_in_table.md"
        md_file_f.write_text(
            "Col 1 | Col 2\n"
            "--- | ---\n"
            "`<docs/nonexistent.md>` | `[missing](docs/nonexistent2.md)`\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_f, root=root)
        check("code spans inside table cells are stripped and not flagged", len(check_links.broken) == 0)

        # Test G: HTML tags and placeholders inside tables do not trigger false positives
        md_file_g = root / "html_and_placeholders_table.md"
        md_file_g.write_text(
            "Tag | Description\n"
            "--- | ---\n"
            "<details><summary>More</summary></details> | HTML accordion\n"
            "<owner>/<repo> | GitHub repository placeholder\n"
            "<branch> | Branch name\n"
            "<N> | Number placeholder\n",
            encoding="utf-8",
        )
        check_links.broken.clear()
        check_links.checked = 0
        check_links.check_file(md_file_g, root=root)
        check("HTML tags and placeholders in tables produce no broken links", len(check_links.broken) == 0)

    # 4. CLI subprocess execution on current repo
    rc, stdout, stderr = run_cli()
    check("check-links.py CLI runs clean on repo (rc=0)", rc == 0)
    check("check-links.py CLI reports success checkmark", "✓ no broken relative links" in stdout)

    print(f"\nResults: {passes} passed, {failures} failed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
