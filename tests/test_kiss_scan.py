"""Tests for scripts/kiss_scan.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kiss_scan.py"
_spec = importlib.util.spec_from_file_location("kiss_scan", MODULE_PATH)
assert _spec is not None and _spec.loader is not None, f"cannot load {MODULE_PATH}"
kiss_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kiss_scan)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def kinds(findings) -> list[str]:
    return [f.kind for f in findings]


def only(findings, kind):
    return [f for f in findings if f.kind == kind]


BLOCK = "\n".join(f"    value_{i} = compute({i})" for i in range(10))


def test_duplicate_block_across_files(tmp_path):
    a = write(tmp_path / "a.py", f"def a():\n{BLOCK}\n")
    b = write(tmp_path / "b.py", f"def b():\n{BLOCK}\n")

    findings = kiss_scan.scan_paths([a, b], kiss_scan.ScanConfig(), tmp_path)
    duplicates = only(findings, "duplicate-block")

    assert len(duplicates) == 1
    reported = {loc.path for loc in duplicates[0].locations}
    assert reported == {"a.py", "b.py"}


def test_duplicate_block_ignores_runs_below_threshold(tmp_path):
    short = "\n".join(f"    value_{i} = compute({i})" for i in range(4))
    a = write(tmp_path / "a.py", f"def a():\n{short}\n")
    b = write(tmp_path / "b.py", f"def b():\n{short}\n")

    findings = kiss_scan.scan_paths([a, b], kiss_scan.ScanConfig(), tmp_path)

    assert only(findings, "duplicate-block") == []


def test_duplicate_block_ignores_comment_and_blank_noise(tmp_path):
    spaced = "\n\n".join(f"    value_{i} = compute({i})" for i in range(10))
    a = write(tmp_path / "a.py", f"def a():\n{BLOCK}\n")
    b = write(tmp_path / "b.py", f"# leading note\ndef b():\n{spaced}\n")

    findings = kiss_scan.scan_paths([a, b], kiss_scan.ScanConfig(), tmp_path)

    assert len(only(findings, "duplicate-block")) == 1


def test_identical_files_reported(tmp_path):
    body = "def shared():\n    return 1\n"
    a = write(tmp_path / "one.py", body)
    b = write(tmp_path / "nested" / "two.py", body)

    findings = kiss_scan.scan_paths([a, b], kiss_scan.ScanConfig(), tmp_path)
    duplicates = only(findings, "duplicate-file")

    assert len(duplicates) == 1
    assert {loc.path for loc in duplicates[0].locations} == {"one.py", "nested/two.py"}


def test_long_function_reported(tmp_path):
    body = "\n".join(f"    step_{i}()" for i in range(70))
    target = write(tmp_path / "long.py", f"def sprawling():\n{body}\n")

    findings = kiss_scan.scan_paths([target], kiss_scan.ScanConfig(), tmp_path)
    long_functions = only(findings, "long-function")

    assert len(long_functions) == 1
    assert long_functions[0].line == 1
    assert "sprawling()" in long_functions[0].message


def test_long_function_within_budget_is_quiet(tmp_path):
    body = "\n".join(f"    step_{i}()" for i in range(10))
    target = write(tmp_path / "short.py", f"def tidy():\n{body}\n")

    findings = kiss_scan.scan_paths([target], kiss_scan.ScanConfig(), tmp_path)

    assert only(findings, "long-function") == []


def test_deep_nesting_reported(tmp_path):
    lines = ["def deep(flag):"]
    for level in range(6):
        lines.append("    " * (level + 1) + f"if flag == {level}:")
    lines.append("    " * 7 + "return True")
    target = write(tmp_path / "deep.py", "\n".join(lines) + "\n")

    findings = kiss_scan.scan_paths([target], kiss_scan.ScanConfig(), tmp_path)
    nesting = only(findings, "deep-nesting")

    assert len(nesting) == 1
    assert "7 levels deep" in nesting[0].message


def test_elif_chain_is_not_deep_nesting(tmp_path):
    lines = ["def choose(value):"]
    for level in range(8):
        keyword = "if" if level == 0 else "elif"
        lines.append(f"    {keyword} value == {level}:")
        lines.append(f"        return {level}")
    target = write(tmp_path / "chain.py", "\n".join(lines) + "\n")

    findings = kiss_scan.scan_paths([target], kiss_scan.ScanConfig(), tmp_path)

    assert only(findings, "deep-nesting") == []


def test_long_file_reported(tmp_path):
    body = "\n".join(f"value_{i} = {i}" for i in range(900))
    target = write(tmp_path / "big.py", body + "\n")

    findings = kiss_scan.scan_paths([target], kiss_scan.ScanConfig(), tmp_path)
    long_files = only(findings, "long-file")

    assert len(long_files) == 1
    assert "900 lines" in long_files[0].message


def test_unparseable_python_is_reported_not_swallowed(tmp_path):
    target = write(tmp_path / "broken.py", "def oops(:\n    pass\n")

    findings = kiss_scan.scan_paths([target], kiss_scan.ScanConfig(), tmp_path)

    assert "unparseable" in kinds(findings)


def test_clean_tree_produces_no_findings(tmp_path):
    write(tmp_path / "a.py", "def alpha():\n    return 1\n")
    write(tmp_path / "b.py", "def beta():\n    return 2\n")

    findings = kiss_scan.scan_paths(
        [tmp_path / "a.py", tmp_path / "b.py"], kiss_scan.ScanConfig(), tmp_path
    )

    assert findings == []


def test_non_text_extensions_are_not_scannable(tmp_path):
    binary = write(tmp_path / "blob.bin", "irrelevant")

    with pytest.raises(kiss_scan.ScanError, match="no scannable files"):
        kiss_scan.scan_paths([binary], kiss_scan.ScanConfig(), tmp_path)


def test_config_rejects_meaningless_duplicate_threshold():
    with pytest.raises(kiss_scan.ScanError, match="min-duplicate-lines"):
        kiss_scan.ScanConfig(min_duplicate_lines=1)


def test_config_rejects_zero_budgets():
    with pytest.raises(kiss_scan.ScanError, match="max-function-lines"):
        kiss_scan.ScanConfig(max_function_lines=0)
    with pytest.raises(kiss_scan.ScanError, match="max-nesting"):
        kiss_scan.ScanConfig(max_nesting=0)
    with pytest.raises(kiss_scan.ScanError, match="max-file-lines"):
        kiss_scan.ScanConfig(max_file_lines=0)


def test_main_clean_tree_exits_zero(tmp_path, capsys):
    a = write(tmp_path / "a.py", "def alpha():\n    return 1\n")

    code = kiss_scan.main(["--root", str(tmp_path), "--paths", str(a)])

    assert code == 0
    assert "no simplification opportunities" in capsys.readouterr().out


def test_main_strict_exits_one_on_findings(tmp_path, capsys):
    a = write(tmp_path / "a.py", f"def a():\n{BLOCK}\n")
    b = write(tmp_path / "b.py", f"def b():\n{BLOCK}\n")

    code = kiss_scan.main(
        ["--root", str(tmp_path), "--paths", str(a), str(b), "--strict"]
    )

    assert code == 1
    assert "exceeds budget" in capsys.readouterr().err


def test_main_without_strict_reports_but_succeeds(tmp_path):
    a = write(tmp_path / "a.py", f"def a():\n{BLOCK}\n")
    b = write(tmp_path / "b.py", f"def b():\n{BLOCK}\n")

    code = kiss_scan.main(["--root", str(tmp_path), "--paths", str(a), str(b)])

    assert code == 0


def test_main_json_output_is_parseable(tmp_path, capsys):
    a = write(tmp_path / "a.py", f"def a():\n{BLOCK}\n")
    b = write(tmp_path / "b.py", f"def b():\n{BLOCK}\n")

    code = kiss_scan.main(
        ["--root", str(tmp_path), "--paths", str(a), str(b), "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["total"] == len(payload["findings"])
    assert payload["counts"]["duplicate-block"] == 1


def test_main_rejects_conflicting_budget_flags(tmp_path, capsys):
    a = write(tmp_path / "a.py", "def alpha():\n    return 1\n")

    code = kiss_scan.main(
        ["--root", str(tmp_path), "--paths", str(a), "--strict", "--max-findings", "3"]
    )

    assert code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_main_reports_missing_paths(tmp_path, capsys):
    code = kiss_scan.main(
        ["--root", str(tmp_path), "--paths", str(tmp_path / "ghost.py")]
    )

    assert code == 2
    assert "do not exist" in capsys.readouterr().err


def test_main_reports_bad_root(tmp_path, capsys):
    code = kiss_scan.main(["--root", str(tmp_path / "nowhere")])

    assert code == 2
    assert "not a directory" in capsys.readouterr().err
