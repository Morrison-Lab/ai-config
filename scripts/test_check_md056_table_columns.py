#!/usr/bin/env python3
"""Tests for scripts/check-md056-table-columns.py (ai-config#3764).

Verifies that:
1. Clean GFM tables (with or without outer pipes, with alignment colons, empty cells) pass.
2. Unescaped pipes inside inline code spans (PR #3737 failure) are detected and reported.
3. Escaped pipes inside inline code spans (PR #3737 fix) pass cleanly.
4. Column count mismatches (too many cells, too few cells) are flagged as MD056 errors.
5. Tables inside fenced code blocks are ignored.
6. Non-table constructs (thematic breaks, setext headings, prose with pipes) are not falsely parsed as tables.
7. Backslash parity before pipes is handled correctly (\\| is unescaped; \\| is escaped).
8. CLI flags (--json, specific file paths, --root) work as expected.
9. Live repository scan passes cleanly with zero violations.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-md056-table-columns.py"

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


def run_script(*args: str, cwd: Path = REPO) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("Testing check-md056-table-columns.py...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Clean table with outer pipes
        f_clean = tmp_path / "clean_table.md"
        f_clean.write_text(
            "# Clean Table\n\n"
            "| Header 1 | Header 2 | Header 3 |\n"
            "| :--- | :---: | ---: |\n"
            "| Cell 1 | Cell 2 | Cell 3 |\n"
            "| Alpha | Beta | Gamma |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_clean))
        check("clean table passes", rc == 0 and "OK: all table column counts match" in out)

        # 2. Clean table without outer pipes
        f_no_outer = tmp_path / "no_outer_pipes.md"
        f_no_outer.write_text(
            "# No Outer Pipes\n\n"
            "Header 1 | Header 2\n"
            "--- | :---\n"
            "Val 1 | Val 2\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_no_outer))
        check("clean table without outer pipes passes", rc == 0 and "OK:" in out)

        # 3. Clean table with valid empty cells
        f_empty_cells = tmp_path / "empty_cells.md"
        f_empty_cells.write_text(
            "| Col A | Col B | Col C |\n"
            "|---|---|---|\n"
            "| | Mid | |\n"
            "| Left | | Right |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_empty_cells))
        check("table with empty cells passes", rc == 0 and "OK:" in out)

        # 4. PR #3737 exact reproduction: unescaped pipes in code spans
        # Lines in README.md:473 had alternations inside backticks like `gh issue|pr comment`
        f_repro_3737 = tmp_path / "repro_3737.md"
        f_repro_3737.write_text(
            "| Hook | Event | Summary |\n"
            "|---|---|---|\n"
            "| `warn.py` | `PreToolUse` | (`gh issue|pr comment`, `gh api`) plus `gh issue|pr create|edit` and `glab issue|mr note` |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_repro_3737))
        check(
            "PR #3737 unescaped pipe in code span fails MD056",
            rc == 1
            and "error MD056/table-column-count" in out
            and "Expected: 3; Actual: 7" in out
            and "unescaped '|' inside code span" in out,
        )

        # 5. PR #3737 fix: escaped pipes in code spans
        f_repro_fixed = tmp_path / "repro_fixed.md"
        f_repro_fixed.write_text(
            "| Hook | Event | Summary |\n"
            "|---|---|---|\n"
            r"| `warn.py` | `PreToolUse` | (`gh issue\|pr comment`, `gh api`) plus `gh issue\|pr create\|edit` and `glab issue\|mr note` |"
            "\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_repro_fixed))
        check("PR #3737 escaped pipes pass cleanly", rc == 0 and "OK:" in out)

        # 6. Mismatched body row: too many cells
        f_too_many = tmp_path / "too_many.md"
        f_too_many.write_text(
            "| Col 1 | Col 2 |\n"
            "|---|---|\n"
            "| A | B | C |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_too_many))
        check(
            "too many cells reported",
            rc == 1 and "Expected: 2; Actual: 3" in out and "Too many cells" in out,
        )

        # 7. Mismatched body row: too few cells
        f_too_few = tmp_path / "too_few.md"
        f_too_few.write_text(
            "| Col 1 | Col 2 | Col 3 |\n"
            "|---|---|---|\n"
            "| Only one |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_too_few))
        check(
            "too few cells reported",
            rc == 1 and "Expected: 3; Actual: 1" in out and "Too few cells" in out,
        )

        # 8. Header / delimiter count mismatch
        f_header_mismatch = tmp_path / "header_mismatch.md"
        f_header_mismatch.write_text(
            "| Col 1 | Col 2 | Col 3 | Col 4 |\n"
            "|---|---|---|\n"
            "| A | B | C |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_header_mismatch))
        check(
            "header delimiter mismatch reported",
            rc == 1 and "Expected: 3; Actual: 4" in out,
        )

        # 9. Fenced code block containing pseudo-table is ignored
        f_fenced = tmp_path / "fenced.md"
        f_fenced.write_text(
            "# Documentation\n\n"
            "```markdown\n"
            "| Col 1 | Col 2 |\n"
            "|---|---|\n"
            "| Broken | Row | With | Extra | Columns |\n"
            "| `invalid|pipe|in|code` |\n"
            "```\n\n"
            "Prose after code block.\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_fenced))
        check("tables inside fenced code blocks are ignored", rc == 0 and "OK:" in out)

        # 10. Escaped backslash before pipe (\\| vs \\\|)
        f_escaped_bs = tmp_path / "escaped_bs.md"
        # Two backslashes before pipe: backslashes escape each other, pipe is UNESCAPED delimiter!
        # In a 2-column table, adding \\| splits into 3 columns => failure.
        f_escaped_bs.write_text(
            "| Col 1 | Col 2 |\n"
            "|---|---|\n"
            r"| Val 1 | `escaped\\|still_delimiter` |"
            "\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_escaped_bs))
        check(
            "double backslash \\\\ before pipe leaves pipe unescaped and fails",
            rc == 1 and "Expected: 2; Actual: 3" in out,
        )

        # 11. Three backslashes before pipe: first two escape each other, third escapes pipe!
        f_triple_bs = tmp_path / "triple_bs.md"
        f_triple_bs.write_text(
            "| Col 1 | Col 2 |\n"
            "|---|---|\n"
            r"| Val 1 | `escaped\\\|real_escape` |"
            "\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_triple_bs))
        check("triple backslash escapes pipe and passes", rc == 0 and "OK:" in out)

        # 12. Non-table constructs: thematic breaks, Setext headings, prose with single pipe
        f_non_table = tmp_path / "non_table.md"
        f_non_table.write_text(
            "# Non-table constructs\n\n"
            "Here is some text.\n\n"
            "---\n\n"
            "Setext Heading\n"
            "---\n\n"
            "A prose line with a | character that is not a table.\n\n"
            "Another line.\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_non_table))
        check("non-table constructs pass cleanly", rc == 0 and "OK:" in out)

        # 13. Blank line before delimiter is not falsely treated as header row
        f_blank_before_delim = tmp_path / "blank_before_delim.md"
        f_blank_before_delim.write_text(
            "Some prose.\n\n"
            "| :--- | :--- |\n"
            "| Val 1 | Val 2 |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_blank_before_delim))
        check("blank line before delimiter row is not parsed as header", rc == 0 and "OK:" in out)

        # 14. 1-column delimiter missing outer pipe is not recognized as delimiter
        f_1col_no_pipe = tmp_path / "1col_no_pipe.md"
        f_1col_no_pipe.write_text(
            "Heading\n"
            "| ---\n"
            "Row 1\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_1col_no_pipe))
        check("1-column delimiter without outer pipes is not treated as table", rc == 0 and "OK:" in out)

        # 15. Unclosed backticks do not prevent later unescaped pipe in code span from being detected
        f_unclosed_backtick = tmp_path / "unclosed_backtick.md"
        f_unclosed_backtick.write_text(
            "| Col 1 | Col 2 |\n"
            "|---|---|\n"
            "| unmatched `` code | `cmd|alt` |\n",
            encoding="utf-8",
        )
        rc, out, _ = run_script(str(f_unclosed_backtick))
        check("unclosed backticks advance correctly and detect subsequent pipe", rc == 1 and "Expected: 2; Actual: 3" in out)

        # 16. CLI JSON output verification
        rc, json_out, _ = run_script(str(f_repro_3737), "--json")
        try:
            data = json.loads(json_out)
            valid_json = (
                data.get("status") == "violations_found"
                and data.get("violations_count") == 1
                and data.get("violations")[0]["expected_cols"] == 3
                and data.get("violations")[0]["actual_cols"] == 7
                and len(data.get("violations")[0]["unescaped_pipes_in_code_spans"]) > 0
            )
        except Exception:
            valid_json = False
        check("JSON output carries structured violation details", rc == 1 and valid_json)

    # 17. Dogfood check: test on current repository
    rc, out, _ = run_script("--root", str(REPO))
    check("dogfood check on current repository passes cleanly", rc == 0 and "OK:" in out)

    print(f"\nResults: {passes} passed, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
