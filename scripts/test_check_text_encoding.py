#!/usr/bin/env python3
"""Tests for scripts/check-text-encoding.py (ai-config#4121).

Verifies that:
1. Bare text-mode I/O operations without explicit encoding are flagged:
   - open(path) [default mode='r']
   - open(path, "w")
   - open(path, mode="w")
   - path.open("w")
   - path.read_text()
   - path.write_text("data")
   - tempfile.NamedTemporaryFile("w")
   - io.open(path, "r")
2. Text-mode operations with explicit encoding or binary mode pass:
   - open(path, encoding="utf-8")
   - open(path, "rb")
   - open(path, mode="wb")
   - path.open("rb")
   - path.read_text(encoding="utf-8")
   - path.write_text("data", encoding="utf-8")
   - tempfile.NamedTemporaryFile() (default binary mode)
   - tempfile.NamedTemporaryFile("w", encoding="utf-8")
   - lines carrying # noqa: text-encoding or # pragma: no-encoding
3. Empty search space fails under --fail-if-empty.
4. Syntax errors are reported.
5. JSON output mode produces expected payload.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-text-encoding.py"

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


def run_script(*args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write_file(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    print("Testing check-text-encoding.py...")

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)

        # 1. Positive tests: bare text I/O operations are flagged
        write_file(d, "bad_open_default.py", 'with open("file.txt") as f:\n    pass\n')
        code, out, err = run_script(str(d / "bad_open_default.py"))
        check("bare open() with default mode is flagged", code == 1)
        check("error message names bare open", "bare open()" in err)
        check("names line number 1", ":1:" in err)

        write_file(d, "bad_open_write.py", 'open("file.txt", "w").close()\n')
        code, out, err = run_script(str(d / "bad_open_write.py"))
        check("bare open(..., 'w') is flagged", code == 1)

        write_file(d, "bad_open_keyword.py", 'with open("file.txt", mode="w") as f:\n    pass\n')
        code, out, err = run_script(str(d / "bad_open_keyword.py"))
        check("bare open(..., mode='w') is flagged", code == 1)

        write_file(d, "bad_read_text.py", 'content = p.read_text()\n')
        code, out, err = run_script(str(d / "bad_read_text.py"))
        check("bare read_text() is flagged", code == 1)
        check("error message names read_text", "read_text()" in err)

        write_file(d, "bad_read_text_errors.py", 'content = p.read_text(errors="replace")\n')
        code, out, err = run_script(str(d / "bad_read_text_errors.py"))
        check("read_text(errors='replace') without encoding is flagged", code == 1)

        write_file(d, "bad_write_text.py", 'p.write_text("hello")\n')
        code, out, err = run_script(str(d / "bad_write_text.py"))
        check("bare write_text() is flagged", code == 1)
        check("error message names write_text", "write_text()" in err)

        write_file(d, "bad_path_open.py", 'with p.open("w") as fh:\n    pass\n')
        code, out, err = run_script(str(d / "bad_path_open.py"))
        check("bare path.open('w') is flagged", code == 1)
        check("error message names path.open", "path.open()" in err)

        write_file(d, "bad_io_open.py", 'import io\nwith io.open("f", "r") as f:\n    pass\n')
        code, out, err = run_script(str(d / "bad_io_open.py"))
        check("bare io.open('r') is flagged", code == 1)

        write_file(d, "bad_tempfile.py", 'import tempfile\ntf = tempfile.NamedTemporaryFile("w")\n')
        code, out, err = run_script(str(d / "bad_tempfile.py"))
        check("bare tempfile.NamedTemporaryFile('w') is flagged", code == 1)
        check("error message names tempfile", "tempfile.NamedTemporaryFile" in err)

        write_file(d, "bad_tempfile_kw.py", 'import tempfile\ntf = tempfile.NamedTemporaryFile(mode="w")\n')
        code, out, err = run_script(str(d / "bad_tempfile_kw.py"))
        check("bare tempfile.NamedTemporaryFile(mode='w') is flagged", code == 1)

        # 2. Negative tests: operations with explicit encoding or binary mode pass
        clean_code = (
            'import io, tempfile\n'
            'with open("file.txt", encoding="utf-8") as f: pass\n'
            'with open("file.txt", "w", encoding="utf-8") as f: pass\n'
            'with open("file.bin", "rb") as f: pass\n'
            'with open("file.bin", mode="wb") as f: pass\n'
            'with p.open("rb") as f: pass\n'
            'with p.open(encoding="utf-8") as f: pass\n'
            'with p.open("w", encoding="utf-8") as f: pass\n'
            't = p.read_text(encoding="utf-8")\n'
            't2 = p.read_text("utf-8")\n'
            'p.write_text("data", encoding="utf-8")\n'
            'p.write_text("data", "utf-8")\n'
            'b = p.read_bytes()\n'
            'p.write_bytes(b"data")\n'
            'tf1 = tempfile.NamedTemporaryFile()\n'
            'tf2 = tempfile.NamedTemporaryFile(mode="wb")\n'
            'tf3 = tempfile.NamedTemporaryFile("w", encoding="utf-8")\n'
            'tf4 = tempfile.TemporaryFile("wb")\n'
            'tf5 = tempfile.TemporaryFile("w", encoding="utf-8")\n'
            'with open("f.txt") as f: pass  # noqa: text-encoding\n'
            'with open("f.txt") as f: pass  # pragma: no-encoding\n'
        )
        write_file(d, "clean_all.py", clean_code)
        code, out, err = run_script(str(d / "clean_all.py"))
        check("clean file passes with exit 0", code == 0)
        check("clean summary reports verified calls", "explicit encoding verified" in out)

        # 3. Non-vacuous check: empty search space fails under --fail-if-empty
        empty_dir = d / "empty_dir"
        empty_dir.mkdir()
        code, out, err = run_script(str(empty_dir), "--fail-if-empty")
        check("empty search space fails under --fail-if-empty", code == 2)
        check("error reports no files found", "No Python files" in err)

        # 4. Syntax error handling
        write_file(d, "syntax_err.py", "def broken(:\n")
        code, out, err = run_script(str(d / "syntax_err.py"))
        check("syntax error causes failure", code != 0)
        check("syntax error is reported in output", "SyntaxError" in (out + err))

        # 5. JSON output mode
        code, out, err = run_script(str(d / "bad_open_default.py"), "--json")
        check("json output exits 1 on violation", code == 1)
        data = json.loads(out)
        check("json status is violations", data["status"] == "violations")
        check("json has files_examined", data["files_examined"] == 1)
        check("json has violations list", len(data["violations"]) == 1)
        check("json violation specifies kind", data["violations"][0]["kind"] == "open")

        code, out, err = run_script(str(d / "clean_all.py"), "--json")
        check("json output exits 0 on clean file", code == 0)
        clean_data = json.loads(out)
        check("json status is clean", clean_data["status"] == "clean")
        check("json has zero violations", clean_data["violations_count"] == 0)

        # 6. Diff mode tests in a test git repo fixture
        # (Path explicitly contains '.gemini' segment to prevent regression of Finding 1)
        repo_dir = d / ".gemini" / "test_repo"
        repo_dir.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, capture_output=True, check=True)

        # Base commit on main
        write_file(repo_dir, "initial.py", 'with open("file.txt", encoding="utf-8") as f:\n    pass\n')
        subprocess.run(["git", "add", "initial.py"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, capture_output=True, check=True)

        # Clean change in diff
        write_file(repo_dir, "clean_change.py", 'with open("c.txt", encoding="utf-8") as f:\n    pass\n')
        subprocess.run(["git", "add", "clean_change.py"], cwd=repo_dir, capture_output=True, check=True)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff", "--base", "HEAD", "--repo-root", str(repo_dir)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        check("diff mode clean change passes", proc.returncode == 0)
        check("diff mode clean reports verified", "explicit encoding verified" in proc.stdout)

        # Bad change in diff
        write_file(repo_dir, "bad_change.py", 'with open("b.txt") as f:\n    pass\n')
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff", "--base", "HEAD", "--repo-root", str(repo_dir)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        check("diff mode flags uncommitted bad text I/O", proc.returncode == 1)
        check("diff mode error names bare open", "bare open()" in proc.stderr)

        # Multi-line call in diff where only later lines are in diff
        write_file(repo_dir, "multiline.py", 'content = (\n    p\n    .read_text()\n)\n')
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff", "--base", "HEAD", "--repo-root", str(repo_dir)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        check("diff mode flags multi-line bare read_text", proc.returncode == 1)

        # Multi-line with exemption comment on later line
        write_file(repo_dir, "multiline_exempt.py", 'content = (\n    p\n    .read_text()  # noqa: text-encoding\n)\n')
        (repo_dir / "bad_change.py").unlink(missing_ok=True)
        (repo_dir / "multiline.py").unlink(missing_ok=True)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff", "--base", "HEAD", "--repo-root", str(repo_dir)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        check("diff mode honors multi-line exemption comment", proc.returncode == 0)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
