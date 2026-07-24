#!/usr/bin/env python3
"""Regression tests for check-new-line-breaks.py."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "cnlb", Path(__file__).parent / "check-new-line-breaks.py"
)
cnlb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cnlb)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def make_repo(tmpdir: Path) -> Path:
    scripts_dir = tmpdir / "scripts"
    scripts_dir.mkdir()
    for name in ("check-new-line-breaks.py", "semantic-line-breaks.py"):
        (scripts_dir / name).write_text(
            (Path(__file__).parent / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmpdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmpdir, check=True)
    return tmpdir


def commit(tmpdir: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=tmpdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=tmpdir, check=True)


def run_check(tmpdir: Path, base: str) -> list:
    result = subprocess.run(
        [sys.executable, "scripts/check-new-line-breaks.py", "--base", base],
        cwd=tmpdir,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout, result.returncode


with tempfile.TemporaryDirectory() as tmp:
    repo = make_repo(Path(tmp))
    (repo / "notes.md").write_text("# Notes\n\n- A short bullet.\n", encoding="utf-8")
    commit(repo, "base")

    (repo / "notes.md").write_text(
        "# Notes\n\n- A short bullet.\n"
        "- Two sentences on one line. This should be flagged as a violation.\n",
        encoding="utf-8",
    )
    commit(repo, "add violation")

    out, code = run_check(repo, "HEAD~1")
    check("flags a newly-added multi-sentence bullet", "notes.md:4" in out)
    check("advisory mode always exits 0", code == 0)

with tempfile.TemporaryDirectory() as tmp:
    repo = make_repo(Path(tmp))
    (repo / "notes.md").write_text("# Notes\n\n- A short bullet.\n", encoding="utf-8")
    commit(repo, "base")

    (repo / "notes.md").write_text(
        "# Notes\n\n- A short bullet.\n"
        "- One clause, cleanly on its own line.\n"
        "\n"
        "```\n"
        "code with a period. not prose.\n"
        "```\n"
        "\n"
        "| a | b. Two sentences in a cell. |\n"
        "| - | - |\n"
        "\n"
        "See https://example.com/a/very/long/single/token/url/should/not/trip/this/check.\n",
        encoding="utf-8",
    )
    commit(repo, "add non-violations")

    out, _code = run_check(repo, "HEAD~1")
    check("code fences are not checked", "code with a period" not in out)
    check("table cells are not checked", "Two sentences in a cell" not in out)
    check("a single-token URL line is not flagged", "example.com" not in out)
    check("no violations reported", out.strip() == "No new lines missing semantic breaks.")

with tempfile.TemporaryDirectory() as tmp:
    repo = make_repo(Path(tmp))
    (repo / "notes.md").write_text("# Notes\n\n- Fine as-is. Two sentences here.\n", encoding="utf-8")
    commit(repo, "base with pre-existing drift")

    (repo / "notes.md").write_text(
        "# Notes\n\n- Fine as-is. Two sentences here.\n- A brand-new short bullet.\n",
        encoding="utf-8",
    )
    commit(repo, "unrelated addition")

    out, _code = run_check(repo, "HEAD~1")
    check(
        "pre-existing drift in an untouched line is not re-flagged",
        "Fine as-is" not in out,
    )

with tempfile.TemporaryDirectory() as tmp:
    repo = make_repo(Path(tmp))
    (repo / "notes.md").write_text("# Notes\n\n- A short bullet.\n", encoding="utf-8")
    commit(repo, "base")
    (repo / "new.md").write_text(
        "# New file\n\n- One clause. Two sentences smashed together.\n",
        encoding="utf-8",
    )
    commit(repo, "add new file")

    _out, code_advisory = run_check(repo, "HEAD~1")
    result = subprocess.run(
        [sys.executable, "scripts/check-new-line-breaks.py", "--base", "HEAD~1", "--strict"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    check("brand-new files are scanned too", "new.md:3" in result.stdout)
    check("--strict exits non-zero on a violation", result.returncode == 1)
    check("default mode still exits 0 for the same input", code_advisory == 0)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
