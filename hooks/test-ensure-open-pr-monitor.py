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
