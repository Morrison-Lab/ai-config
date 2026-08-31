#!/usr/bin/env python3
"""Static regex linter and catastrophic backtracking (ReDoS) timeout checker.

Analyzes regular expressions across Python source files (hooks, scripts, plugins)
for vulnerability to catastrophic backtracking and self-ambiguous partitioning:
  1. Nested quantifiers (repetition of repeated or optional tokens, e.g. `(a+)+`, `(a*)*`).
  2. Self-ambiguous alternatives under repetition (e.g. `={3,}` or `[A-Za-z]+` inside `(...)*`).
  3. Nullable alternatives under repetition (e.g. `\\s*` or `a?` inside repeated alternations).
  4. Overlapping alternation branches under repetition (e.g. `([a-z]+|\\w+)*`).
  5. Dynamic timeout probes: executes crafted non-matching probe inputs against regexes
     with a hard timeout to empirically catch exponential backtracking.

Usage:
  python3 scripts/check_regex_patterns.py
  python3 scripts/check_regex_patterns.py --paths hooks/ scripts/ plugins/
  python3 scripts/check_regex_patterns.py --json
  python3 scripts/check_regex_patterns.py --timeout 0.25 --strict
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import signal
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import re._parser as parser
except ImportError:
    import sre_parse as parser  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCAN_DIRS = ["hooks", "scripts", "plugins"]
DEFAULT_TIMEOUT = 0.25  # seconds per dynamic probe


@dataclass
class RegexInstance:
    file_path: str
    line_number: int
    col_offset: int
    pattern_str: str
    flags: int
    source_call: str


@dataclass
class Finding:
    kind: str
    message: str
    severity: str  # "vulnerability" or "warning"
    details: str = ""


@dataclass
class RegexReport:
    file_path: str
    line_number: int
    col_offset: int
    pattern_str: str
    flags: int
    source_call: str
    findings: list[Finding] = field(default_factory=list)


# --- Flag evaluation from AST ---

RE_FLAG_MAP: dict[str, int] = {
    "IGNORECASE": re.IGNORECASE,
    "I": re.I,
    "MULTILINE": re.MULTILINE,
    "M": re.M,
    "DOTALL": re.DOTALL,
    "S": re.S,
    "VERBOSE": re.VERBOSE,
    "X": re.X,
    "ASCII": re.ASCII,
    "A": re.A,
    "LOCALE": re.LOCALE,
    "L": re.L,
}


def evaluate_ast_flags(node: ast.AST | None) -> int:
    """Evaluate regex flags from an AST expression (e.g. re.I | re.M)."""
    if node is None:
        return 0
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == "re":
            return RE_FLAG_MAP.get(node.attr, 0)
    if isinstance(node, ast.Name):
        return RE_FLAG_MAP.get(node.id, 0)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return evaluate_ast_flags(node.left) | evaluate_ast_flags(node.right)
    return 0


# --- AST Regex Extraction ---

RE_CALL_NAMES = {
    "compile",
    "search",
    "match",
    "fullmatch",
    "findall",
    "finditer",
    "sub",
    "subn",
    "split",
}


def extract_regex_instances_from_ast(tree: ast.AST, file_path: str) -> list[RegexInstance]:
    """Extract regex pattern strings, line numbers, and flags from Python AST."""
    string_constants: dict[str, str] = {}
    instances: list[RegexInstance] = []

    # First pass: collect string constants across all scopes (module, class, function)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, str):
                        string_constants[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    string_constants[node.target.id] = node.value.value

    # Second pass: walk all call nodes
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        call_name = ""
        is_re_call = False

        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "re":
            if func.attr in RE_CALL_NAMES:
                is_re_call = True
                call_name = f"re.{func.attr}"

        if not is_re_call or not node.args:
            continue

        arg0 = node.args[0]
        pattern_str: str | None = None

        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            pattern_str = arg0.value
        elif isinstance(arg0, ast.Name) and arg0.id in string_constants:
            pattern_str = string_constants[arg0.id]

        if pattern_str is None:
            continue

        # Extract flags
        flags = 0
        if call_name == "re.compile":
            if len(node.args) >= 2:
                flags = evaluate_ast_flags(node.args[1])
            for kw in node.keywords:
                if kw.arg == "flags":
                    flags |= evaluate_ast_flags(kw.value)
        elif call_name in ("re.search", "re.match", "re.fullmatch", "re.findall", "re.finditer"):
            if len(node.args) >= 3:
                flags = evaluate_ast_flags(node.args[2])
            for kw in node.keywords:
                if kw.arg == "flags":
                    flags |= evaluate_ast_flags(kw.value)
        elif call_name == "re.split":
            # re.split(pattern, string, maxsplit=0, flags=0)
            if len(node.args) >= 4:
                flags = evaluate_ast_flags(node.args[3])
            for kw in node.keywords:
                if kw.arg == "flags":
                    flags |= evaluate_ast_flags(kw.value)
        elif call_name in ("re.sub", "re.subn"):
            if len(node.args) >= 5:
                flags = evaluate_ast_flags(node.args[4])
            for kw in node.keywords:
                if kw.arg == "flags":
                    flags |= evaluate_ast_flags(kw.value)

        instances.append(
            RegexInstance(
                file_path=file_path,
                line_number=node.lineno,
                col_offset=node.col_offset,
                pattern_str=pattern_str,
                flags=flags,
                source_call=call_name,
            )
        )

    return instances


# --- Static Pattern Analysis ---


def is_unbounded_quantifier(min_r: int, max_r: int) -> bool:
    """Return True if quantifier upper bound is unbounded (MAXREPEAT, e.g. *, +, {n,})."""
    return max_r == parser.MAXREPEAT


def is_subpattern_nullable(subpattern: list[tuple[Any, Any]]) -> bool:
    """Return True if subpattern can match the empty string (0 characters)."""
    for node in subpattern:
        op, arg = node
        if op in (parser.AT, parser.ASSERT, parser.ASSERT_NOT):
            continue
        elif op in (parser.MAX_REPEAT, parser.MIN_REPEAT):
            min_r, _, inner = arg
            if min_r == 0 or is_subpattern_nullable(inner):
                continue
            return False
        elif op == parser.SUBPATTERN:
            inner = arg[-1]
            if is_subpattern_nullable(inner):
                continue
            return False
        elif op == parser.BRANCH:
            _, branches = arg
            if any(is_subpattern_nullable(b) for b in branches):
                continue
            return False
        else:
            return False
    return True


def has_unbounded_internal_quantifier(subpattern: list[tuple[Any, Any]]) -> bool:
    """Return True if subpattern contains any repeat with unbounded/high max."""
    for node in subpattern:
        op, arg = node
        if op in (parser.MAX_REPEAT, parser.MIN_REPEAT):
            min_r, max_r, _ = arg
            if is_unbounded_quantifier(min_r, max_r):
                return True
        elif op == parser.SUBPATTERN:
            inner = arg[-1]
            if has_unbounded_internal_quantifier(inner):
                return True
        elif op == parser.BRANCH:
            _, branches = arg
            if any(has_unbounded_internal_quantifier(b) for b in branches):
                return True
    return False


def get_first_chars(subpattern: list[tuple[Any, Any]]) -> set[str]:
    """Extract set of possible first characters for a subpattern (for overlap analysis)."""
    chars: set[str] = set()
    for node in subpattern:
        op, arg = node
        if op in (parser.AT, parser.ASSERT, parser.ASSERT_NOT):
            continue
        elif op == parser.LITERAL:
            chars.add(chr(arg))
            break
        elif op == parser.NOT_LITERAL:
            chars.add("?")
            break
        elif op == parser.IN:
            is_negated = any(item_op == parser.NEGATE for item_op, _ in arg)
            if is_negated:
                chars.add("?")
            else:
                for item in arg:
                    item_op, item_arg = item
                    if item_op == parser.LITERAL:
                        chars.add(chr(item_arg))
                    elif item_op == parser.RANGE:
                        lo, hi = item_arg
                        for c in range(lo, min(hi + 1, lo + 128)):
                            chars.add(chr(c))
                    elif item_op == parser.CATEGORY:
                        cat_str = str(item_arg).upper()
                        if "SPACE" in cat_str:
                            chars.update(" \t\n\r\f\v")
                        elif "DIGIT" in cat_str:
                            chars.update("0123456789")
                        elif "WORD" in cat_str:
                            chars.update("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
            break
        elif op == parser.CATEGORY:
            cat_str = str(arg).upper()
            if "SPACE" in cat_str:
                chars.update(" \t\n\r\f\v")
            elif "DIGIT" in cat_str:
                chars.update("0123456789")
            elif "WORD" in cat_str:
                chars.update("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
            break
        elif op == parser.ANY:
            chars.add("?")
            break
        elif op == parser.SUBPATTERN:
            inner = arg[-1]
            sub_chars = get_first_chars(inner)
            chars.update(sub_chars)
            if not is_subpattern_nullable(inner):
                break
        elif op == parser.BRANCH:
            _, branches = arg
            for b in branches:
                chars.update(get_first_chars(b))
            if not any(is_subpattern_nullable(b) for b in branches):
                break
        elif op in (parser.MAX_REPEAT, parser.MIN_REPEAT):
            min_r, _, inner = arg
            chars.update(get_first_chars(inner))
            if min_r > 0 and not is_subpattern_nullable(inner):
                break
    return chars


def is_subpattern_delimited(subpattern: list[tuple[Any, Any]]) -> bool:
    """Return True if subpattern begins or ends with a fixed non-quantified literal token."""
    if not subpattern:
        return False
    first = subpattern[0]
    if first[0] == parser.LITERAL:
        return True
    if first[0] == parser.SUBPATTERN and is_subpattern_delimited(first[1][-1]):
        return True
    last = subpattern[-1]
    if last[0] == parser.LITERAL:
        return True
    if last[0] == parser.SUBPATTERN and is_subpattern_delimited(last[1][-1]):
        return True
    return False


def check_static_ast(pattern_str: str, flags: int = 0) -> list[Finding]:
    """Statically check regex AST for ReDoS structures."""
    findings: list[Finding] = []
    try:
        parsed = parser.parse(pattern_str, flags)
    except Exception:
        return []

    def check_subpattern(subpattern: list[tuple[Any, Any]], in_unbounded_quantifier: bool = False) -> None:
        for idx_node, node in enumerate(subpattern):
            op, arg = node
            if op in (parser.MAX_REPEAT, parser.MIN_REPEAT):
                min_r, max_r, inner = arg
                is_unbounded = is_unbounded_quantifier(min_r, max_r)

                if in_unbounded_quantifier and is_unbounded:
                    # Flag if directly nested or unanchored repetition
                    if len(inner) == 1 or all(op_n in (parser.MAX_REPEAT, parser.MIN_REPEAT, parser.SUBPATTERN, parser.BRANCH) for op_n, _ in inner):
                        findings.append(
                            Finding(
                                kind="nested_quantifier",
                                message="Nested quantifier: repetition inside repeated group can cause exponential backtracking.",
                                severity="vulnerability",
                                details=f"Outer repeat contains inner repeat with bounds ({min_r}, {max_r})",
                            )
                        )

                # If inner is anchored by a fixed literal or separated by delimiters, repetitions are partitioned cleanly
                delimited = is_subpattern_delimited(inner) or len(inner) > 2
                next_in_quantifier = (is_unbounded and not delimited) or in_unbounded_quantifier
                check_subpattern(inner, in_unbounded_quantifier=next_in_quantifier)

            elif op == parser.SUBPATTERN:
                inner = arg[-1]
                check_subpattern(inner, in_unbounded_quantifier=in_unbounded_quantifier)

            elif op == parser.BRANCH:
                _, branches = arg
                if in_unbounded_quantifier:
                    # 1. Check self-ambiguous alternatives: branch containing unbounded repetition
                    for idx, branch in enumerate(branches):
                        if has_unbounded_internal_quantifier(branch):
                            findings.append(
                                Finding(
                                    kind="self_ambiguous_alternative",
                                    message="Self-ambiguous alternative under repetition: branch contains repetition, causing exponential partition ambiguity.",
                                    severity="vulnerability",
                                    details=f"Branch index {idx} contains repeated elements under outer quantifier.",
                                )
                            )

                    # 2. Check nullable alternative in repeated group
                    if any(is_subpattern_nullable(b) for b in branches):
                        findings.append(
                            Finding(
                                kind="nullable_branch_under_repetition",
                                message="Nullable alternative in repeated group: branch can match empty string, permitting zero-width repetitions.",
                                severity="vulnerability",
                                details="One or more alternation branches are nullable.",
                            )
                        )

                    # 3. Check overlapping branches under repetition
                    branch_charsets = [get_first_chars(b) for b in branches]
                    for i in range(len(branch_charsets)):
                        for j in range(i + 1, len(branch_charsets)):
                            s1, s2 = branch_charsets[i], branch_charsets[j]
                            if "?" in s1 or "?" in s2 or (s1 and s2 and not s1.isdisjoint(s2)):
                                if has_unbounded_internal_quantifier(branches[i]) or has_unbounded_internal_quantifier(branches[j]):
                                    findings.append(
                                        Finding(
                                            kind="overlapping_alternation_branches",
                                            message="Overlapping alternation branches under repetition: branches match overlapping tokens with variable length.",
                                            severity="vulnerability",
                                            details=f"Branches {i} and {j} share starting characters.",
                                        )
                                    )

                for branch in branches:
                    check_subpattern(branch, in_unbounded_quantifier=in_unbounded_quantifier)

    check_subpattern(parsed.data)
    return findings


# --- Dynamic Probe Testing ---


class RegexTimeoutError(Exception):
    """Raised when regex execution exceeds hard timeout limit."""


def _alarm_handler(signum: int, frame: Any) -> None:
    raise RegexTimeoutError("Regex execution timed out")


def extract_probe_characters(pattern_str: str) -> set[str]:
    """Extract character tokens from a regex to generate targeted test probes."""
    chars: set[str] = {"a", "=", " ", "\n", "0", "-", "_", "/", "\\", '"', "'", "(", "<"}
    for m in re.finditer(r"[A-Za-z0-9_= \t\n\r\-+*/\\()\[\]{}<>:;.,!?|~`@#$%^&]", pattern_str):
        c = m.group(0)
        if c not in "\\^$*+?{}[]().|":
            chars.add(c)
    return chars


def generate_probes(pattern_str: str) -> list[str]:
    """Generate crafted probe strings to test for catastrophic backtracking."""
    chars = extract_probe_characters(pattern_str)
    probes: list[str] = []

    for c in sorted(chars):
        if c in ("\n", "\r"):
            probes.append((c * 40) + "!")
        else:
            probes.append((c * 45) + "!")

    probes.extend(
        [
            ("=" * 50) + "!",
            (" " * 50) + "!",
            ("\t" * 40) + "!",
            ("a" * 50) + "!",
            ("0" * 50) + "!",
            ("#" * 50) + "!",
            ("(1) " * 25) + "!",
            ('{"k":"v"}' * 15) + "!",
            ("<tag>" * 15) + "!",
            ("Reviewed-Commit: 12345678" + ("=" * 45) + "!"),
            ("Reviewed-Commit: 12345678" + (" a" * 25) + "!"),
        ]
    )
    return probes


def test_dynamic_probe(
    pattern_str: str,
    flags: int,
    probe: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[bool, float, str | None]:
    """Execute regex search on probe input with hard timeout.

    Uses signal.setitimer on Unix for microsecond setup; falls back to
    daemon thread on platforms without SIGALRM.
    Returns (passed, duration, error_or_timeout_msg).
    """
    try:
        compiled = re.compile(pattern_str, flags)
    except Exception as exc:
        return True, 0.0, str(exc)

    # Fast path: Unix ITIMER_REAL signal
    if hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread():
        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        t0 = time.perf_counter()
        try:
            compiled.search(probe)
            dur = time.perf_counter() - t0
            return True, dur, None
        except RegexTimeoutError:
            dur = time.perf_counter() - t0
            return False, dur, f"Execution timed out (> {timeout:.2f}s)"
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)

    # Fallback path: daemon thread with join
    result_holder: list[tuple[bool, float, str | None]] = []

    def _worker() -> None:
        t0 = time.perf_counter()
        try:
            compiled.search(probe)
            dur = time.perf_counter() - t0
            result_holder.append((True, dur, None))
        except Exception as exc:
            result_holder.append((True, 0.0, str(exc)))

    t = threading.Thread(target=_worker, daemon=True)
    t0 = time.perf_counter()
    t.start()
    t.join(timeout)

    if t.is_alive():
        dur = time.perf_counter() - t0
        return False, dur, f"Execution timed out (> {timeout:.2f}s)"

    if result_holder:
        return result_holder[0]

    return True, time.perf_counter() - t0, None


def check_dynamic_probes(
    pattern_str: str,
    flags: int = 0,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[Finding]:
    """Run dynamic timeout probes against a regex pattern."""
    findings: list[Finding] = []
    if not any(c in pattern_str for c in ("*", "+", "{")):
        return []

    probes = generate_probes(pattern_str)

    for probe in probes:
        passed, dur, msg = test_dynamic_probe(pattern_str, flags, probe, timeout=timeout)
        if not passed:
            probe_repr = repr(probe)
            if len(probe_repr) > 40:
                probe_repr = probe_repr[:37] + "...'"
            findings.append(
                Finding(
                    kind="dynamic_backtracking_timeout",
                    message=f"Catastrophic backtracking dynamic failure: {msg} on probe input {probe_repr}.",
                    severity="vulnerability",
                    details=f"Probe: {probe_repr}, duration: {dur:.3f}s",
                )
            )
            break

    return findings


# --- File and Directory Scanning ---


def scan_file(
    file_path: Path,
    timeout: float = DEFAULT_TIMEOUT,
    enable_dynamic: bool = True,
) -> list[RegexReport]:
    """Scan a single Python file for regex patterns and analyze them."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return []

    instances = extract_regex_instances_from_ast(tree, str(file_path))
    reports: list[RegexReport] = []

    for inst in instances:
        findings = check_static_ast(inst.pattern_str, inst.flags)
        if enable_dynamic:
            dynamic_findings = check_dynamic_probes(inst.pattern_str, inst.flags, timeout=timeout)
            findings.extend(dynamic_findings)

        if findings:
            reports.append(
                RegexReport(
                    file_path=inst.file_path,
                    line_number=inst.line_number,
                    col_offset=inst.col_offset,
                    pattern_str=inst.pattern_str,
                    flags=inst.flags,
                    source_call=inst.source_call,
                    findings=findings,
                )
            )

    return reports


def discover_python_files(paths: list[Path], excludes: list[str]) -> list[Path]:
    """Discover Python files across specified paths, respecting exclude patterns."""
    discovered: set[Path] = set()

    for p in paths:
        if p.is_file() and p.suffix == ".py":
            discovered.add(p.resolve())
        elif p.is_dir():
            for sub in p.rglob("*.py"):
                parts = sub.parts
                if any(ignored in parts for ignored in (".git", "vendor", "__pycache__", ".venv", "build", "dist")):
                    continue
                if sub.name.startswith("test_") or sub.name.startswith("test-"):
                    continue
                discovered.add(sub.resolve())

    filtered: list[Path] = []
    for f in sorted(discovered):
        try:
            rel = str(f.relative_to(ROOT))
        except ValueError:
            rel = str(f)
        if any(re.search(exc, rel) for exc in excludes):
            continue
        filtered.append(f)

    return filtered


def main(argv: list[str] | None = None) -> int:
    parser_cli = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_cli.add_argument(
        "--paths",
        "-p",
        nargs="*",
        type=Path,
        default=None,
        help="Directories or files to scan (default: hooks/ scripts/ plugins/)",
    )
    parser_cli.add_argument(
        "--exclude",
        "-e",
        nargs="*",
        default=[],
        help="Regex patterns for files/paths to exclude",
    )
    parser_cli.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Dynamic probe timeout in seconds (default: {DEFAULT_TIMEOUT}s)",
    )
    parser_cli.add_argument(
        "--no-dynamic",
        action="store_true",
        help="Skip dynamic probe timeout execution checks",
    )
    parser_cli.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of text",
    )
    parser_cli.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero code on any finding or warning",
    )
    args = parser_cli.parse_args(argv)

    scan_dirs = args.paths if args.paths is not None else [ROOT / d for d in DEFAULT_SCAN_DIRS]
    existing_dirs = [p for p in scan_dirs if p.exists()]

    if not existing_dirs:
        if args.json:
            print(json.dumps({"status": "error", "error": "No scan paths found."}))
        else:
            print("ERROR: No valid scan paths found.", file=sys.stderr)
        return 2

    files_to_scan = discover_python_files(existing_dirs, args.exclude)
    all_reports: list[RegexReport] = []

    for f in files_to_scan:
        reports = scan_file(f, timeout=args.timeout, enable_dynamic=not args.no_dynamic)
        all_reports.extend(reports)

    vuln_count = sum(len(r.findings) for r in all_reports)

    has_dynamic_timeout = any(f.kind == "dynamic_backtracking_timeout" for r in all_reports for f in r.findings)
    has_vulnerability = any(f.severity == "vulnerability" for r in all_reports for f in r.findings)
    should_fail = has_dynamic_timeout or (args.strict and vuln_count > 0) or (args.paths is not None and has_vulnerability)

    if args.json:
        payload = {
            "status": "vulnerabilities_found" if vuln_count > 0 else "clean",
            "files_scanned": len(files_to_scan),
            "vulnerabilities_count": vuln_count,
            "reports": [
                {
                    "file_path": r.file_path,
                    "line_number": r.line_number,
                    "col_offset": r.col_offset,
                    "pattern": r.pattern_str,
                    "flags": r.flags,
                    "source_call": r.source_call,
                    "findings": [asdict(f) for f in r.findings],
                }
                for r in all_reports
            ],
        }
        print(json.dumps(payload, indent=2))
        return 1 if should_fail else 0

    if vuln_count > 0:
        header = "FAILED" if should_fail else "WARNING"
        print(f"{header}: Found {vuln_count} regex finding(s) across {len(all_reports)} pattern(s):", file=sys.stderr)
        for r in all_reports:
            rel = r.file_path
            try:
                rel = str(Path(r.file_path).relative_to(ROOT))
            except ValueError:
                pass
            print(f"\n  {rel}:{r.line_number} in {r.source_call}:", file=sys.stderr)
            print(f"    Pattern: {r.pattern_str!r}", file=sys.stderr)
            for f in r.findings:
                print(f"    - [{f.severity.upper()}] {f.kind}: {f.message}", file=sys.stderr)
                if f.details:
                    print(f"      Details: {f.details}", file=sys.stderr)
        if should_fail:
            return 1

    print(f"OK: Checked regex patterns across {len(files_to_scan)} Python file(s); no catastrophic backtracking risks found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
