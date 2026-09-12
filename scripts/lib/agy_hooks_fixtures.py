"""Fixtures for testing Antigravity hook commands and rendering."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

def load_script(stem):
    """Import a hyphenated script under scripts/ as a module."""
    path = REPO_ROOT / "scripts" / (stem + ".py")
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_checker():
    """Import the hyphenated checker script as a module."""
    return load_script("check-agy-hook-commands")


def load_renderer():
    """Import the hyphenated renderer script as a module."""
    return load_script("render-agy-hooks")

CHECKER = load_checker()
RENDERER = load_renderer()

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
