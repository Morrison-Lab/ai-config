#!/usr/bin/env python3
"""Shared test helpers for require-stopping-point hook test suites."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile


def make_test_env(tmpdir: str, extra_env: dict | None = None) -> dict:
    """Create isolated test environment for hook execution."""
    env = dict(
        os.environ,
        TMPDIR=tmpdir,
        TEMP=tmpdir,
        TMP=tmpdir,
        GITHUB_ACTIONS="",
        CI="",
        NON_INTERACTIVE="",
        CLAUDE_NON_INTERACTIVE="",
        HARNESS_MODE="",
    )
    if extra_env:
        env.update(extra_env)
    return env


def has_warning(stdout: str) -> bool:
    """Verify stdout JSON has no blocking decision/reason and check for systemMessage."""
    if not stdout.strip():
        return False
    data = json.loads(stdout)
    decision = str(data.get("decision") or "").strip().lower()
    assert decision not in {"block", "deny"} and "reason" not in data, (
        f"Hook emitted blocking decision or reason: {stdout}"
    )
    return "systemMessage" in data and bool(data.get("systemMessage"))


_DEFAULT_HOOK = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "hooks", "require-stopping-point.py")
)


def streamed_chunks_transcript(
    chunks: list,
    msg_id: str = "msg_1",
    env: dict | None = None,
    cumulative: bool = False,
    hook_path: str | None = None,
) -> bool:
    """Run hook against simulated streamed chunks transcript and report warning presence."""
    if hook_path is None:
        hook_path = _DEFAULT_HOOK
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "do task"}}) + "\n")
        for chunk in chunks:
            if isinstance(chunk, dict):
                text = chunk.get("text", "")
                is_cum = chunk.get("cumulative", cumulative)
            else:
                text = chunk
                is_cum = cumulative
            evt = {
                "type": "assistant",
                "message": {
                    "id": msg_id,
                    "content": [{"type": "text", "text": text}],
                },
            }
            if is_cum:
                evt["cumulative"] = True
                evt["message"]["cumulative"] = True
            f.write(json.dumps(evt) + "\n")
    tmpdir = tempfile.mkdtemp()
    res = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=make_test_env(tmpdir, env),
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return has_warning(res.stdout)
