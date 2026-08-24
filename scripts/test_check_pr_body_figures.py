#!/usr/bin/env python3
"""Regression and unit tests for scripts/check-pr-body-figures.py.

Tests:
1. Parsing of verification sections, derived-at SHAs, diff stats, and file sizes.
2. Pin against known-stale fixture from #1531 at 3a373100 (flags SHA, diff, file size).
3. Pin against known-good fixture from #1531 at 84cf85e2 (clean verification).
4. Reporting of examined figures count (vacuous-zero detection per fail-fast.md).
5. File size extraction across various markdown table shapes and bold styling.
6. CLI arguments and exit codes (0 = clean, 1 = mismatch, 2 = usage error).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "checker", Path(__file__).parent / "check-pr-body-figures.py"
)
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = ""):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        msg = f"FAIL: {name}"
        if extra:
            msg += f" --- {extra}"
        print(msg)
        failures += 1


def test_parsing():
    body = """
# Feature Description

Some text here.

## Verification

**All figures below re-derived at `84cf85e2`**, after committing, with the three-dot range.

| check | result |
| --- | --- |
| `check-links.py` | **1659** links across 503 files, **0 broken** |
| `check-context-closure.py` | 80 fragments examined, **0 over** the 100,000-byte cap |
| `markdownlint-cli2` | 512 files linted, 0 issues |
| banned punctuation / any non-ASCII | **35** added lines examined, **0** each |
| multi-sentence / clause rule | **31** prose lines examined, **0** each |

Denominator cross-checked independently: `git diff --numstat origin/main...HEAD` gives +35/-4.

File sizes, before to after:

| file | before | after |
| --- | --- | --- |
| `shared/workflow/ardi.rationale.md` | 67,491 bytes | **69,269** bytes |
| `shared/workflow/pr-on-claim.rationale.md` | 26,839 bytes | 26,862 bytes |

## Corrections to this body

1. **`3a373100`** --- stale figures originally derived at `685b5dc8` claiming +31/-3.
"""
    stated = checker.parse_body_figures(body)
    check("parse derived_at_sha", stated.derived_at_sha == "84cf85e2")
    check("parse diff_additions", stated.diff_additions == 35)
    check("parse diff_deletions", stated.diff_deletions == 4)
    check("parse added_lines_examined", stated.added_lines_examined == 35)
    check("parse prose_lines_examined", stated.prose_lines_examined == 31)
    check("parse links_count", stated.links_count == 1659)
    check("parse links_files_count", stated.links_files_count == 503)
    check("parse context_fragments", stated.context_fragments == 80)
    check("parse linted_files", stated.linted_files == 512)
    check(
        "parse file_sizes ardi.rationale.md",
        stated.file_sizes.get("shared/workflow/ardi.rationale.md") == 69269,
    )
    check(
        "parse file_sizes pr-on-claim.rationale.md",
        stated.file_sizes.get("shared/workflow/pr-on-claim.rationale.md") == 26862,
    )


def test_stale_body_pin_1531():
    """Pin against the real labelled failure from #1531 at 3a373100.

    At commit 3a373100, the body still carried the 685b5dc8 figures (+31/-3,
    31 added lines, 69,170 bytes for ardi.rationale.md) against a real git diff
    of +35/-4 and 69,269 bytes. The detector MUST flag all of these.
    """
    stale_body = """
## Verification

**All figures derived at `685b5dc8`**, after committing.

| check | result |
| --- | --- |
| banned punctuation / any non-ASCII | **31** added lines examined, **0** each |
| multi-sentence / clause rule | **27** prose lines examined, **0** each |

Denominator cross-checked: `git diff --numstat origin/main...HEAD` gives +31/-3.

File sizes, before to after:

| file | before | after |
| --- | --- | --- |
| `shared/workflow/ardi.rationale.md` | 67,491 bytes | **69,170** bytes |
"""
    head_sha = "3a37310028d2f0e96c45da0e644ff88a0c252768"
    base_ref = "origin/main"
    stated = checker.parse_body_figures(stale_body)

    with patch.object(
        checker,
        "get_git_diff_numstat",
        return_value=(
            35,
            4,
            2,
            {
                "shared/workflow/ardi.rationale.md": (33, 3),
                "shared/workflow/pr-on-claim.rationale.md": (2, 1),
            },
        ),
    ), patch.object(
        checker,
        "get_git_file_size",
        side_effect=lambda repo, head, path: 69269
        if path == "shared/workflow/ardi.rationale.md"
        else None,
    ):
        results = checker.verify_pr_body_figures(
            stated, Path("/dummy"), base_ref, head_sha
        )

        mismatches = [r for r in results if r.status == "MISMATCH"]
        check("stale body 1531 has 4 figures examined", len(results) == 4)
        check("stale body 1531 has 4 mismatches", len(mismatches) == 4)

        mismatch_names = {r.name for r in mismatches}
        check("stale body flags derived_at_sha mismatch", "derived_at_sha" in mismatch_names)
        check("stale body flags diff_add_del mismatch", "diff_add_del" in mismatch_names)
        check("stale body flags added_lines mismatch", "added_lines_examined" in mismatch_names)
        check(
            "stale body flags file_size mismatch",
            "file_size:shared/workflow/ardi.rationale.md" in mismatch_names,
        )


def test_clean_body_pin_1531():
    """Pin against the clean state of #1531 at 84cf85e2."""
    clean_body = """
## Verification

**All figures derived at `84cf85e2`**, after committing, with the three-dot range.

| check | result |
| --- | --- |
| banned punctuation / any non-ASCII | **35** added lines examined, **0** each |
| multi-sentence / clause rule | **31** prose lines examined, **0** each |

Denominator cross-checked independently: `git diff --numstat origin/main...HEAD` gives +35/-4.

File sizes, before to after:

| file | before | after |
| --- | --- | --- |
| `shared/workflow/ardi.rationale.md` | 67,491 bytes | **69,269** bytes |
| `shared/workflow/pr-on-claim.rationale.md` | 26,839 bytes | **26,862** bytes |
"""
    head_sha = "84cf85e2300b83a026eca7a2a1da1dbac09980c3"
    base_ref = "origin/main"
    stated = checker.parse_body_figures(clean_body)

    file_sizes_map = {
        "shared/workflow/ardi.rationale.md": 69269,
        "shared/workflow/pr-on-claim.rationale.md": 26862,
    }

    with patch.object(
        checker,
        "get_git_diff_numstat",
        return_value=(
            35,
            4,
            2,
            {
                "shared/workflow/ardi.rationale.md": (33, 3),
                "shared/workflow/pr-on-claim.rationale.md": (2, 1),
            },
        ),
    ), patch.object(
        checker,
        "get_git_file_size",
        side_effect=lambda repo, head, path: file_sizes_map.get(path),
    ):
        results = checker.verify_pr_body_figures(
            stated, Path("/dummy"), base_ref, head_sha
        )

        matches = [r for r in results if r.status == "MATCH"]
        mismatches = [r for r in results if r.status == "MISMATCH"]
        check("clean body 1531 has 5 figures examined", len(results) == 5)
        check("clean body 1531 has 5 matches", len(matches) == 5)
        check("clean body 1531 has 0 mismatches", len(mismatches) == 0)


def test_vacuous_zero():
    """A body with no verification table reports examined_count == 0."""
    empty_body = "Just a small docs fix with no verification table."
    stated = checker.parse_body_figures(empty_body)
    with patch.object(checker, "get_git_diff_numstat", return_value=(0, 0, 0, {})):
        results = checker.verify_pr_body_figures(
            stated, Path.cwd(), "origin/main", "12345678"
        )
    check("vacuous body has 0 examined figures", len(results) == 0)


def test_cli_exit_codes():
    """Verify exit code behavior: 0 on clean, 1 on mismatch, 2 on usage error."""
    clean_body = "## Verification\n**All figures derived at `abcd1234`**\n"
    stale_body = "## Verification\n**All figures derived at `deadbeef`**\n"

    with patch.object(checker, "get_git_diff_numstat", return_value=(0, 0, 0, {})):
        # Clean body matching HEAD -> exit 0
        code_clean = checker.main(
            ["--body", clean_body, "--head", "abcd12345678", "--quiet"]
        )
        check("CLI exit code 0 on clean body", code_clean == 0)

        # Stale body mismatching HEAD -> exit 1
        code_mismatch = checker.main(
            ["--body", stale_body, "--head", "abcd12345678", "--quiet"]
        )
        check("CLI exit code 1 on mismatching body", code_mismatch == 1)

    # Missing body file -> exit 2
    try:
        checker.main(["--body-file", "/nonexistent/path/to/file.md"])
        check("CLI exit code 2 on missing file", False, "Expected SystemExit(2)")
    except SystemExit as e:
        check("CLI exit code 2 on missing file", e.code == 2)


def test_live_tools_verification():
    """Verify live tool checks for links and context fragments."""
    body = """
## Verification
| `check-links.py` | 100 links across 20 files |
| `check-context-closure.py` | 50 fragments examined |
"""
    stated = checker.parse_body_figures(body)

    # When live tool counters match
    with patch.object(checker, "get_link_counts", return_value=(100, 20)), \
         patch.object(checker, "get_context_fragment_count", return_value=50), \
         patch.object(checker, "get_git_diff_numstat", return_value=(0, 0, 0, {})):
        results = checker.verify_pr_body_figures(
            stated, Path.cwd(), "origin/main", "12345678", verify_live_tools=True
        )
        matches = [r for r in results if r.status == "MATCH"]
        check("live tools match link and fragment counts", len(matches) == 2)

    # When live tool counters mismatch
    with patch.object(checker, "get_link_counts", return_value=(105, 20)), \
         patch.object(checker, "get_context_fragment_count", return_value=48), \
         patch.object(checker, "get_git_diff_numstat", return_value=(0, 0, 0, {})):
        results = checker.verify_pr_body_figures(
            stated, Path.cwd(), "origin/main", "12345678", verify_live_tools=True
        )
        mismatches = [r for r in results if r.status == "MISMATCH"]
        check("live tools flag link and fragment mismatches", len(mismatches) == 2)


def test_json_output():
    """Verify JSON output structure."""
    import io
    import contextlib

    clean_body = "## Verification\n**All figures derived at `abcd1234`**\n"
    buf = io.StringIO()
    with patch.object(checker, "get_git_diff_numstat", return_value=(0, 0, 0, {})), \
         contextlib.redirect_stdout(buf):
        code = checker.main(["--body", clean_body, "--head", "abcd12345678", "--json"])
    check("JSON mode returns exit 0 on clean", code == 0)
    data = json.loads(buf.getvalue().strip())
    check("JSON payload clean field is True", data.get("clean") is True)
    check("JSON payload examined_count is 1", data.get("examined_count") == 1)


def test_formatting_variations():
    """Verify figure extraction across varied headings, markdown backticks, and tables."""
    body = """
### Verification

Figures re-derived at '11223344':

| File | Before | After |
|---|---|---|
| `docs/guide.md` | 1,000 bytes | 2,500 bytes |

Diff gives +10/-2 with 10 added lines examined and 8 prose lines examined.
"""
    stated = checker.parse_body_figures(body)
    check("variations: derived SHA with single quotes", stated.derived_at_sha == "11223344")
    check("variations: diff additions", stated.diff_additions == 10)
    check("variations: diff deletions", stated.diff_deletions == 2)
    check("variations: added lines examined", stated.added_lines_examined == 10)
    check("variations: prose lines examined", stated.prose_lines_examined == 8)
    check("variations: file size extraction", stated.file_sizes.get("docs/guide.md") == 2500)


def test_undecodable_stream_guards():
    """A stream that came back None is an environment failure, not a finding.

    This script is the one that actually crashed: its `res.stderr.strip()` on
    the non-zero-exit path raised AttributeError when the Windows reader thread
    died on a decode error. `check-pr-fully-clean.py` carries the equivalent
    pins, but a pin over there proves nothing about this file -- the previous
    round's finding was exactly a fix generalized along one axis and left
    unguarded along another.
    """
    class _NoneStdout:
        returncode = 0
        stdout = None
        stderr = ""

    with patch.object(checker.subprocess, "run", lambda *a, **kw: _NoneStdout()):
        try:
            checker.run_cmd(["gh", "pr", "view", "1"])
            outcome = "returned normally"
        except SystemExit as exc:
            outcome = f"SystemExit:{exc.code}"
        except AttributeError:
            outcome = "AttributeError"
    check("None stdout exits 2 rather than raising AttributeError",
          outcome == f"SystemExit:{checker.USAGE_EXIT}", extra=outcome)

    class _NoneStderr:
        returncode = 1
        stdout = ""
        stderr = None

    with patch.object(checker.subprocess, "run", lambda *a, **kw: _NoneStderr()):
        try:
            checker.run_cmd(["gh", "pr", "view", "1"])
            outcome = "returned normally"
        except SystemExit as exc:
            outcome = f"SystemExit:{exc.code}"
        except RuntimeError:
            outcome = "RuntimeError"
        except AttributeError:
            outcome = "AttributeError"
    # SystemExit specifically, not RuntimeError: `verify_pr_body_figures` wraps
    # its run_cmd calls in `except Exception`, converts the failure to
    # status="UNVERIFIED", and main() then exits 0 CLEAN. SystemExit derives
    # from BaseException, so it escapes that wrapper.
    check("undecodable stderr on a failed command exits 2, not RuntimeError",
          outcome == f"SystemExit:{checker.USAGE_EXIT}", extra=outcome)

    class _RealStderr:
        returncode = 1
        stdout = ""
        stderr = "gh: Not Found (HTTP 404)\n"

    with patch.object(checker.subprocess, "run", lambda *a, **kw: _RealStderr()):
        try:
            checker.run_cmd(["gh", "pr", "view", "1"])
            outcome = "returned normally"
        except SystemExit:
            outcome = "SystemExit"
        except RuntimeError as exc:
            outcome = f"RuntimeError:{exc}"
    check("negative control: a readable-stderr failure still raises RuntimeError",
          outcome.startswith("RuntimeError:") and "404" in outcome, extra=outcome)

    recorded = {}

    class _Ok:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def _rec(cmd, **kwargs):
        recorded.update(kwargs)
        return _Ok()

    with patch.object(checker.subprocess, "run", _rec):
        checker.run_cmd(["gh", "pr", "view", "1"])
    check("run_cmd decodes as UTF-8 explicitly",
          recorded.get("encoding") == "utf-8", extra=str(recorded.get("encoding")))


def main() -> int:
    print("Testing check-pr-body-figures.py...")
    test_undecodable_stream_guards()
    test_parsing()
    test_stale_body_pin_1531()
    test_clean_body_pin_1531()
    test_vacuous_zero()
    test_cli_exit_codes()
    test_live_tools_verification()
    test_json_output()
    test_formatting_variations()

    print(f"\nResults: {passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
