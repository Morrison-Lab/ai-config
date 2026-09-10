"""Fixtures for testing Antigravity hook commands and rendering."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

def load_checker():
    """Import the hyphenated checker script as a module."""
    path = REPO_ROOT / "scripts" / "check-agy-hook-commands.py"
    spec = importlib.util.spec_from_file_location("check_agy_hook_commands", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CHECKER = load_checker()

BACKSLASH = chr(92)
PYTHON_EXE = "C:/Users/u/AppData/Local/Programs/Python/Python312/python.exe"
ADAPTER = "C:/Users/u/.gemini/config/plugins/ai-config/claude-hook-adapter.py"

# The exact string the installed manifest carried, per the issue: each quote
# preceded by a backslash inside the JSON string VALUE.
ESCAPED_FORM = (
    BACKSLASH + '"' + PYTHON_EXE + BACKSLASH + '" '
    + BACKSLASH + '"' + ADAPTER + BACKSLASH + '"'
)
QUOTED_FORM = '"' + PYTHON_EXE + '" "' + ADAPTER + '"'
UNQUOTED_FORM = PYTHON_EXE + " " + ADAPTER

def manifest_with(command: str) -> dict:
    """Wrap one command in both manifest shapes Antigravity uses."""
    return {
        "enforce-merge-control": {
            "PreToolUse": [
                {"matcher": "run_command", "hooks": [{"type": "command", "command": command}]}
            ],
            "Stop": [{"type": "command", "command": command}],
        }
    }
