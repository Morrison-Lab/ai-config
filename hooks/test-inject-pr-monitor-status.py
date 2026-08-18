#!/usr/bin/env python3
"""Regression tests for inject-pr-monitor-status.py."""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

first = {"data": {"state": "OPEN", "reviewDecision": ""}}
second = {"data": {"state": "OPEN", "reviewDecision": "APPROVED"}}
assert subject.fingerprint(first) == subject.fingerprint(first)
assert subject.fingerprint(first) != subject.fingerprint(second)
assert subject.fingerprint({"error": "offline"}) != subject.fingerprint(first)
assert subject.fingerprint({"error": "offline"}) == subject.fingerprint({"error": "offline"})
print("PASS: only changed PR observations are injected")
