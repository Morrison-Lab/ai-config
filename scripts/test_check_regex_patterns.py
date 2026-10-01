#!/usr/bin/env python3
"""Regression test suite for scripts/check_regex_patterns.py.

Verifies that:
  1. Static AST analysis catches nested quantifiers (e.g. `(a+)+`, `(a*)*`).
  2. Static AST analysis catches self-ambiguous alternatives under repetition (e.g. `={3,}`).
  3. Static AST analysis catches nullable alternatives in repeated groups (e.g. `\\s*`, `a?`).
  4. Static AST analysis catches overlapping alternation branches under repetition.
  5. Dynamic probe execution detects exponential backtracking timeouts on crafted payloads.
  6. Safe, disjoint, and bounded regex patterns pass cleanly with zero findings.
  7. AST regex extraction correctly extracts calls (`re.compile`, `re.search`, `re.sub`, etc.) and flags.
  8. CLI arguments (`--json`, `--timeout`, `--no-dynamic`, `--strict`) behave as expected.
  9. Success output encodes on a cp1252 stdout stream (ai-config#2038).
 10. `regex-safe:` markers silence a pattern only with a measured reason, and the
     repo's own baseline is zero (ai-config#3989).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_regex_patterns.py"

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


# --- Load module for direct unit testing ---
spec = importlib.util.spec_from_file_location("check_regex_patterns", SCRIPT)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


# --- 1. Static AST analysis of dangerous patterns ---

def test_static_dangerous_patterns() -> None:
    # Nested quantifier: (a+)+
    f1 = mod.check_static_ast(r"(a+)+")
    check(
        "static check catches nested quantifier `(a+)+`",
        any(f.kind == "nested_quantifier" for f in f1),
        f"findings: {f1!r}",
    )

    # Nested quantifier: (a*)*
    f2 = mod.check_static_ast(r"(a*)*")
    check(
        "static check catches nested quantifier `(a*)*`",
        any(f.kind == "nested_quantifier" for f in f2),
        f"findings: {f2!r}",
    )

    # Self-ambiguous alternative: (?:[A-Za-z]+|={3,}|\s*)*
    f3 = mod.check_static_ast(r"(?:[A-Za-z]+|={3,}|\s*)*")
    check(
        "static check catches self-ambiguous alternative `={3,}` under repetition",
        any(f.kind == "self_ambiguous_alternative" for f in f3),
        f"findings: {f3!r}",
    )
    check(
        "static check catches nullable branch `\\s*` under repetition",
        any(f.kind == "nullable_branch_under_repetition" for f in f3),
        f"findings: {f3!r}",
    )

    # Overlapping alternation branches: ([a-z]+|\w+)*
    f4 = mod.check_static_ast(r"([a-z]+|\w+)*")
    check(
        "static check catches overlapping branches under repetition",
        any(f.kind in ("overlapping_alternation_branches", "self_ambiguous_alternative") for f in f4),
        f"findings: {f4!r}",
    )


test_static_dangerous_patterns()


# --- 2. Static AST analysis of safe patterns ---

def test_static_safe_patterns() -> None:
    safe_patterns = [
        r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$",
        r"'[^']*'|\"(?:\\[\s\S]|[^\"\\])*\"",
        r"^\s*#{1,6}[\s#]",
        r"\A---\r?\n(.*?)\r?\n---\r?\n",
        r"^\d+(?:\.\d+)+$",
        r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@",
        r"\bpython3?\s+[^\n]*\btest\b",
    ]
    for pat in safe_patterns:
        findings = mod.check_static_ast(pat)
        check(
            f"safe pattern has no static findings: {pat!r}",
            len(findings) == 0,
            f"unexpected findings: {findings!r}",
        )


test_static_safe_patterns()


# --- 3. Dynamic probe execution ---

def test_dynamic_probes() -> None:
    # Catastrophic backtracking pattern from pitfalls doc
    dangerous_pat = r"Reviewed-Commit:\s*[a-f0-9A-F]+(?:\s*(?:[A-Za-z]+|={3,}|\s*))*\Z"
    findings = mod.check_dynamic_probes(dangerous_pat, timeout=0.15)
    check(
        "dynamic probe detects catastrophic backtracking timeout",
        any(f.kind == "dynamic_backtracking_timeout" for f in findings),
        f"findings: {findings!r}",
    )

    # Catastrophic backtracking pattern in copy-pasted _GIT_FLAGS (Issue #3172)
    git_flags_vulnerable = (
        r"(?:^|[;&|\n])\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*git\s+"
        r"(?:-(?:C\s*\S+|c\s*\S+|[a-zA-Z0-9_-]+(?:=\S*)?)\s+|--[a-zA-Z0-9_-]+(?:=\S*)?\s+)*"
        r"commit(?![\w-])"
    )
    git_flags_findings = mod.check_dynamic_probes(git_flags_vulnerable, timeout=0.15)
    check(
        "dynamic probe detects catastrophic backtracking in unanchored _GIT_FLAGS alternatives",
        any(f.kind == "dynamic_backtracking_timeout" for f in git_flags_findings),
        f"findings: {git_flags_findings!r}",
    )

    # Safe pattern passes dynamic probe quickly
    safe_pat = r"Reviewed-Commit:\s*[a-f0-9A-F]+"
    safe_findings = mod.check_dynamic_probes(safe_pat, timeout=0.15)
    check(
        "dynamic probe passes safe pattern with zero findings",
        len(safe_findings) == 0,
        f"findings: {safe_findings!r}",
    )


test_dynamic_probes()


# --- 4. Subprocess execution against synthetic Python files ---

def run_script(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_synthetic_files() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        clean_file = tmp_path / "clean.py"
        clean_file.write_text(
            'import re\n'
            'RX_VALID = re.compile(r"^[a-zA-Z0-9_-]+$")\n'
            'def match_it(text):\n'
            '    local_pat = r"\\bhello\\s+world\\b"\n'
            '    parts = re.split(r"\\s+", text, 1, re.IGNORECASE)\n'
            '    return re.search(local_pat, text, flags=re.I)\n',
            encoding="utf-8",
        )

        vuln_file = tmp_path / "vuln.py"
        vuln_file.write_text(
            'import re\n'
            'def bad():\n'
            '    local_vuln = r"(a+)+"\n'
            '    return re.search(local_vuln, "text")\n',
            encoding="utf-8",
        )

        # Test clean file
        rc, out, err = run_script(["--paths", str(clean_file)])
        check(
            "clean file exits 0",
            rc == 0 and "OK: Checked regex patterns" in out,
            f"rc={rc} out={out!r} err={err!r}",
        )

        # Test clean file with --json
        rc, out, err = run_script(["--paths", str(clean_file), "--json"])
        check(
            "clean file with --json emits status 'clean'",
            rc == 0 and '"status": "clean"' in out,
            f"out={out!r}",
        )

        # Test vulnerable file with scoped pattern
        rc, out, err = run_script(["--paths", str(vuln_file)])
        check(
            "vulnerable file with scoped pattern exits 1",
            rc == 1 and "FAILED: Found" in err,
            f"rc={rc} out={out!r} err={err!r}",
        )

        # Test vulnerable file with --json
        rc, out, err = run_script(["--paths", str(vuln_file), "--json"])
        check(
            "vulnerable file with --json emits status 'vulnerabilities_found'",
            rc == 1 and '"status": "vulnerabilities_found"' in out,
            f"out={out!r}",
        )

        # Test lexical scope isolation between functions
        scope_file = Path(td) / "test_scopes.py"
        scope_code = (
            "import re\n\n"
            "def func_safe():\n"
            "    pat = r'^[a-z]+$'\n"
            "    return re.search(pat, 'test')\n\n"
            "def func_danger():\n"
            "    pat = r'(a+)+'\n"
            "    return re.search(pat, 'test')\n"
        )
        scope_file.write_text(scope_code, encoding="utf-8")
        rc, out, err = run_script(["--paths", str(scope_file), "--json"])
        data = json.loads(out)
        reports = data.get("reports", [])
        check(
            "lexical scope correctly attributes vulnerability to func_danger line 9",
            len(reports) == 1 and reports[0]["line_number"] == 9,
            f"reports={reports!r}",
        )

        # Test module-level forward reference (pattern defined below function)
        fwd_file = Path(td) / "test_fwd.py"
        fwd_code = (
            "import re\n\n"
            "def func():\n"
            "    return re.search(PATTERN, 'test')\n\n"
            "PATTERN = r'(a+)+'\n"
        )
        fwd_file.write_text(fwd_code, encoding="utf-8")
        rc, out, err = run_script(["--paths", str(fwd_file), "--json"])
        data = json.loads(out)
        reports = data.get("reports", [])
        check(
            "module constant forward reference detected in func call line 4",
            len(reports) == 1 and reports[0]["line_number"] == 4,
            f"reports={reports!r}",
        )


test_synthetic_files()


# --- 5. Missing / invalid paths exit with usage code 2 ---

def test_missing_paths() -> None:
    rc, out, err = run_script(["--paths", "/nonexistent/directory/path/12345"])
    check(
        "nonexistent path exits 2 with error diagnostic",
        rc == 2 and ("ERROR" in err or "error" in out),
        f"rc={rc} out={out!r} err={err!r}",
    )


test_missing_paths()


# --- 6. cp1252 stdout compatibility (ai-config#2038) ---

def test_cp1252_encoding() -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    with tempfile.TemporaryDirectory() as td:
        tmp_file = Path(td) / "test_clean.py"
        tmp_file.write_text('import re\nRX = re.compile(r"^abc$")\n', encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--paths", str(tmp_file)],
            capture_output=True,
            env=env,
        )
        check(
            "script succeeds on cp1252 stdout without UnicodeEncodeError",
            proc.returncode == 0,
            f"rc={proc.returncode} stderr={proc.stderr!r}",
        )
        try:
            ascii_text = proc.stdout.decode("ascii")
            is_ascii = True
        except UnicodeDecodeError:
            ascii_text = ""
            is_ascii = False
        check(
            "success output contains only ASCII characters",
            is_ascii and "OK: Checked" in ascii_text,
            f"ascii={is_ascii} out={proc.stdout!r}",
        )


test_cp1252_encoding()


# --- 7. Recorded-safe markers (ai-config#3989) ---

BAD_CALL = 'import re\nRX = re.compile(r"(a+)+")\n'
MARKER = "# regex-safe: worst case 1k-char run of a 0.001s, hook timeout 10s"


def scan_text(text: str, *extra: str) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "marked.py"
        f.write_text(text, encoding="utf-8")
        rc, out, err = run_script(["--paths", str(f), "--json", *extra])
        return rc, json.loads(out)


def test_safe_markers() -> None:
    # Negative control: the unmarked known-bad pattern is still reported.
    rc, data = scan_text(BAD_CALL)
    check(
        "negative control: unmarked `(a+)+` is still reported",
        rc == 1 and data["vulnerabilities_count"] > 0,
        f"rc={rc} data={data!r}",
    )

    # Marker on the line above, with a measurement, silences it.
    rc, data = scan_text(f"import re\n{MARKER}\nRX = re.compile(r\"(a+)+\")\n")
    check(
        "measured marker on the line above silences the finding",
        rc == 0 and data["status"] == "clean",
        f"rc={rc} data={data!r}",
    )

    # Marker as a trailing comment on the reported line also silences it.
    rc, data = scan_text(f"import re\nRX = re.compile(r\"(a+)+\")  {MARKER}\n")
    check(
        "measured marker on the reported line silences the finding",
        rc == 0 and data["status"] == "clean",
        f"rc={rc} data={data!r}",
    )

    # Marker inside the unbroken comment block above also counts.
    rc, data = scan_text(f"import re\n{MARKER}\n# more prose about it\nRX = re.compile(r\"(a+)+\")\n")
    check(
        "measured marker earlier in the comment block above silences the finding",
        rc == 0 and data["status"] == "clean",
        f"rc={rc} data={data!r}",
    )

    # A marker separated by code does not reach the pattern.
    rc, data = scan_text(f"import re\n{MARKER}\nX = 1\nRX = re.compile(r\"(a+)+\")\n")
    check(
        "marker separated from the pattern by code does not silence it",
        rc == 1 and data["vulnerabilities_count"] > 0,
        f"rc={rc} data={data!r}",
    )

    # A marker with no reason is itself an error and silences nothing.
    rc, data = scan_text("import re\n# regex-safe:\nRX = re.compile(r\"(a+)+\")\n")
    kinds = {f["kind"] for r in data["reports"] for f in r["findings"]}
    check(
        "marker with no reason is an error and does not silence the pattern",
        rc == 1 and "marker_without_measurement" in kinds and "nested_quantifier" in kinds,
        f"rc={rc} kinds={kinds!r}",
    )

    # A reason with prose but no timing figure is rejected the same way.
    rc, data = scan_text("import re\n# regex-safe: it is fine\nRX = re.compile(r\"(a+)+\")\n")
    kinds = {f["kind"] for r in data["reports"] for f in r["findings"]}
    check(
        "marker whose reason has no measured time is an error",
        rc == 1 and "marker_without_measurement" in kinds,
        f"rc={rc} kinds={kinds!r}",
    )

    # Each part of the measurement is required: a time alone is not enough.
    weak_reasons = {
        "time only": "tested 1s",
        "no timeout": "worst case 1k-char run of a 0.001s",
        "timeout without a figure": "worst case 1k-char run of a 0.001s, timeout ok",
        "no worst case": "1k-char run of a 0.001s, hook timeout 10s",
        "no measured time (only the timeout's)": "worst case 1k-char run, hook timeout 10s",
    }
    for label, reason in weak_reasons.items():
        rc, data = scan_text(f"import re\n# regex-safe: {reason}\nRX = re.compile(r\"(a+)+\")\n")
        kinds = {f["kind"] for r in data["reports"] for f in r["findings"]}
        check(
            f"marker reason with {label} is a marker_without_measurement finding",
            rc == 1 and "marker_without_measurement" in kinds and "nested_quantifier" in kinds,
            f"rc={rc} kinds={kinds!r}",
        )

    # `timeout none` and the hyphenated phrase are accepted.
    rc, data = scan_text(
        "import re\n# regex-safe: worst-case 1k-char run of a 0.001s; timeout none (CLI)\n"
        "RX = re.compile(r\"(a+)+\")\n"
    )
    check(
        "worst-case spelling and `timeout none` are accepted",
        rc == 0 and data["status"] == "clean",
        f"rc={rc} data={data!r}",
    )

    # A valid marker above a pattern with no finding is an unused_marker finding.
    rc, data = scan_text(f"import re\n{MARKER}\nRX = re.compile(\"a\")\n")
    kinds = {f["kind"] for r in data["reports"] for f in r["findings"]}
    check(
        "valid marker above a clean pattern is an unused_marker finding",
        rc == 1 and kinds == {"unused_marker"},
        f"rc={rc} kinds={kinds!r}",
    )

    # A used marker is not reported as unused.
    rc, data = scan_text(f"import re\n{MARKER}\nRX = re.compile(r\"(a+)+\")\n")
    check(
        "a marker that silences a finding is not reported as unused",
        data["vulnerabilities_count"] == 0,
        f"data={data!r}",
    )

    # A bare marker on a safe pattern is still reported (stray marker).
    rc, data = scan_text("import re\n# regex-safe:\nRX = re.compile(r\"^abc$\")\n")
    check(
        "bare marker is reported even when the pattern is clean",
        rc == 1 and data["vulnerabilities_count"] == 1,
        f"rc={rc} data={data!r}",
    )

    # Marker text inside a string or docstring is not a marker.
    rc, data = scan_text('import re\n"""# regex-safe:"""\nRX = re.compile(r"^abc$")\n')
    check(
        "marker text inside a docstring is not treated as a marker",
        rc == 0 and data["status"] == "clean",
        f"rc={rc} data={data!r}",
    )

    # --no-markers ignores a valid marker (the control for the repo-wide run).
    rc, data = scan_text(f"import re\n{MARKER}\nRX = re.compile(r\"(a+)+\")\n", "--no-markers")
    check(
        "--no-markers reports a pattern a valid marker would silence",
        rc == 1 and data["vulnerabilities_count"] > 0,
        f"rc={rc} data={data!r}",
    )


test_safe_markers()


# --- 8. The repo's own baseline is zero (ai-config#3989) ---

def test_repo_baseline_is_zero() -> None:
    rc, out, err = run_script(["--json"])
    data = json.loads(out)
    check(
        "repo scan reports zero findings",
        rc == 0 and data["vulnerabilities_count"] == 0,
        f"count={data['vulnerabilities_count']} "
        f"first={[(r['file_path'], r['line_number']) for r in data['reports'][:5]]}",
    )
    rc, out, err = run_script(["--json", "--no-markers"])
    data = json.loads(out)
    check(
        "negative control: --no-markers still finds the annotated patterns",
        data["vulnerabilities_count"] > 0,
        f"count={data['vulnerabilities_count']}",
    )


test_repo_baseline_is_zero()


# --- Final summary ---

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
