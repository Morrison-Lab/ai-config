"""Tests for post.sh: rejecting trailing CLI errors after VERDICT and valid review posting."""
import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _setup_post_env(tmp_path, out_text, pr_state="OPEN", head_sha="a" * 40):
    """Copy post.sh into tmp_path and stub `gh` on PATH."""
    shutil.copy(os.path.join(_HERE, "post.sh"), tmp_path / "post.sh")
    (tmp_path / "out-o_r-7.txt").write_text(out_text, encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_stub = bin_dir / "gh"
    gh_stub.write_text(
        f"""#!/bin/bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo "{pr_state} {head_sha}"
  exit 0
fi
if [ "$1" = "pr" ] && [ "$2" = "comment" ]; then
  echo "POSTED $*"
  exit 0
fi
exit 1
""",
        encoding="utf-8",
    )
    gh_stub.chmod(gh_stub.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    return env


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_post_rejects_early_verdict_followed_by_cli_error_dump(tmp_path):
    """Regression test for #4762: VERDICT: FINDINGS followed by >=100 chars of CLI error must not post."""
    out_text = (
        "HEAD: " + ("a" * 40) + "\n"
        "STATE: OPEN\n"
        "VERDICT: FINDINGS\n"
        "Stream terminated unexpectedly while reading response chunk from upstream model endpoint: "
        "connection reset by peer after partial token stream.\n"
    )
    env = _setup_post_env(tmp_path, out_text)
    res = subprocess.run(
        ["bash", str(tmp_path / "post.sh"), "o/r", "7"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 3
    assert not (tmp_path / "comment-o_r-7.md").exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
@pytest.mark.parametrize(
    "error_line",
    [
        '{"short_error": "model overloaded, please retry later --- dummy padding to exceed one hundred characters in total length"}',
        "Error: upstream request failed after partial output --- dummy padding to exceed one hundred characters in total length",
        "Rate limit exceeded for model gemini-4-argon-medium --- dummy padding to exceed one hundred characters in total length",
        "Quota exhausted on project endpoint (HTTP/1.1 429 Too Many Requests) --- dummy padding to exceed one hundred characters",
    ],
)
def test_post_rejects_broadened_error_patterns_even_with_closing_verdict(tmp_path, error_line):
    """Regression test for #4762: broadened CLI error markers are rejected even if VERDICT appears at end."""
    out_text = (
        "HEAD: " + ("a" * 40) + "\n"
        "STATE: OPEN\n"
        f"{error_line}\n"
        "VERDICT: FINDINGS\n"
    )
    env = _setup_post_env(tmp_path, out_text)
    res = subprocess.run(
        ["bash", str(tmp_path / "post.sh"), "o/r", "7"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 3
    assert "AGY ERROR" in res.stdout
    assert not (tmp_path / "comment-o_r-7.md").exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_post_accepts_repeated_findings_when_closed_by_second_verdict(tmp_path):
    """When agy prints findings, VERDICT: FINDINGS, then repeats findings and a second VERDICT: FINDINGS, post succeeds."""
    finding = (
        "1. `foo.qmd:12` --- The definition of variance omits the expectation operator on the squared deviation, "
        "contradicting the display equation immediately below it."
    )
    out_text = (
        "HEAD: " + ("a" * 40) + "\n"
        "STATE: OPEN\n"
        "Short summary.\n"
        "VERDICT: FINDINGS\n"
        f"{finding}\n"
        "**Stopping Point**: done\n"
        "VERDICT: FINDINGS\n"
    )
    env = _setup_post_env(tmp_path, out_text)
    res = subprocess.run(
        ["bash", str(tmp_path / "post.sh"), "o/r", "7"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    comment = (tmp_path / "comment-o_r-7.md").read_text(encoding="utf-8")
    assert finding in comment
    assert "VERDICT: FINDINGS" in comment
