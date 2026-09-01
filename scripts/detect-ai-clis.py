#!/usr/bin/env python3
"""Inspect and report availability of AI coding CLIs and forge tools.

Scans active environment PATH, standard install locations, and environment
variable overrides for recognized AI subagent CLIs (Claude, Cursor, Codex,
OpenCode, Antigravity/Gemini, Ollama, Grok, Aider) and developer forge
tools (gh, glab, git).

Usage:
    python3 scripts/detect-ai-clis.py
    python3 scripts/detect-ai-clis.py --json
    python3 scripts/detect-ai-clis.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import ai_cli


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0]
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if at least one AI CLI engine is available, 1 otherwise",
    )
    args = parser.parse_args()

    report = ai_cli.get_tool_status_report()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(ai_cli.format_tool_status_table(report))

    if args.check:
        return 0 if bool(report.get("available_engines")) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
