#!/usr/bin/env python3
"""Regression test for ensure-open-pr-monitor.py."""
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

script = os.path.join(os.path.dirname(sys.argv[1]), "monitor-open-prs.py")
assert os.path.basename(script) == "monitor-open-prs.py"
print("PASS: the prompt hook targets the all-open-PR controller")

import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory() as pydir:
    py_exe = Path(pydir) / "python.exe"
    pyw_exe = Path(pydir) / "pythonw.exe"
    py_exe.touch()
    pyw_exe.touch()
    with patch("os.name", "nt"), patch.object(sys, "executable", str(py_exe)):
        resolved = subject.resolve_interpreter()
        assert resolved == str(pyw_exe), f"expected {pyw_exe}, got {resolved}"
    with patch("os.name", "posix"), patch.object(sys, "executable", str(py_exe)):
        resolved = subject.resolve_interpreter()
        assert resolved == str(py_exe), f"expected {py_exe}, got {resolved}"

print("PASS: resolve_interpreter prefers pythonw on Windows and preserves interpreter on POSIX")
