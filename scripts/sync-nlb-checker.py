#!/usr/bin/env python3
"""Refresh the vendored check-new-line-breaks.py from the SHA CI pins.

Reads the `Morrison-Lab/gha/check-new-line-breaks@<sha>` pin out of
`.github/workflows/validate.yml`, fetches that script, and writes
`scripts/vendor/gha-check-new-line-breaks.py` plus the sibling `.pin`.

Run this after bumping the action pin. Do not hand-edit the vendored copy.
"""
from __future__ import annotations

import argparse
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
    """Return the checker bytes at `sha`, preferring `gh api` then raw HTTPS.

    A missing `gh` binary is one more way the first route can fail, not a
    reason to stop: `subprocess.run` raises `FileNotFoundError` (an
    `OSError`) rather than returning a non-zero exit, so it is caught here
    and the HTTPS route runs as it does for any other `gh` failure
    (ai-config#2338). The reason is kept so the combined error names both
    routes when HTTPS fails too.
    """
    try:
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
    except OSError as exc:
        gh_err = str(exc)
    else:
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        gh_err = proc.stderr.decode("utf-8", errors="replace").strip() or str(proc.returncode)
    url = RAW_URL.format(sha=sha)
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read()
    except OSError as exc:
        raise SystemExit(
            f"failed to fetch NLB checker at {sha}: gh: {gh_err}; HTTPS: {exc}"
        ) from exc


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Consume the command line so `--help` prints usage instead of syncing.

    The sync fetches over the network and rewrites two tracked files, so a
    reader who runs `--help` to learn the usage must not trigger it: before a
    pin bump that is a surprise write, and over local edits to the vendored
    copy it is a silent overwrite (ai-config#3095). The parser takes no
    arguments, so an unknown one exits 2 rather than being ignored.
    """
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _parse_args(argv)
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
