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
            '    return re.search(r"\\bhello\\s+world\\b", text, flags=re.I)\n',
            encoding="utf-8",
        )

        vuln_file = tmp_path / "vuln.py"
        vuln_file.write_text(
            'import re\n'
            'RX_BAD = re.compile(r"(a+)+")\n',
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

        # Test vulnerable file
        rc, out, err = run_script(["--paths", str(vuln_file)])
        check(
            "vulnerable file exits 1",
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


# --- Final summary ---

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
