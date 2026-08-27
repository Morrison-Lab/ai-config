#!/usr/bin/env python3
"""Refresh the vendored check-new-line-breaks.py from the SHA CI pins.

Reads the `Morrison-Lab/gha/check-new-line-breaks@<sha>` pin out of
`.github/workflows/validate.yml`, fetches that script, and writes
`scripts/vendor/gha-check-new-line-breaks.py` plus the sibling `.pin`.

Run this after bumping the action pin. Do not hand-edit the vendored copy.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
LIB = SCRIPTS_DIR / "lib" / "nlb_gate.py"

spec = importlib.util.spec_from_file_location("nlb_gate", LIB)
nlb_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nlb_gate)

RAW_URL = (
    "https://raw.githubusercontent.com/Morrison-Lab/gha/"
    "{sha}/check-new-line-breaks/check-new-line-breaks.py"
)


def _fetch(sha: str) -> bytes:
    """Return the checker bytes at `sha`, preferring `gh api` then raw HTTPS."""
    proc = subprocess.run(
        [
            "gh",
            "api",
            f"repos/Morrison-Lab/gha/contents/check-new-line-breaks/"
            f"check-new-line-breaks.py?ref={sha}",
            "-H",
            "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
    )
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout
    url = RAW_URL.format(sha=sha)
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read()
    except OSError as exc:
        gh_err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(
            f"failed to fetch NLB checker at {sha}: gh: {gh_err or proc.returncode}; "
            f"HTTPS: {exc}"
        ) from exc


def main() -> int:
    sha = nlb_gate.parse_ci_nlb_sha()
    body = _fetch(sha)
    if b"classify_line" not in body or b"has_late_semicolon" not in body:
        raise SystemExit(
            f"fetched bytes for {sha} do not look like check-new-line-breaks.py"
        )
    nlb_gate.VENDOR_PY.parent.mkdir(parents=True, exist_ok=True)
    nlb_gate.VENDOR_PY.write_bytes(body)
    nlb_gate.write_vendor_pin(sha, nlb_gate.file_sha256(nlb_gate.VENDOR_PY))
    # Drop a cached import so a same-process caller sees the new file.
    nlb_gate._CHECKER = None
    print(f"wrote {nlb_gate.VENDOR_PY.relative_to(nlb_gate.REPO_ROOT)} at {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
