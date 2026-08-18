#!/usr/bin/env python3
"""Regression test for monitor-open-prs.py."""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

assert subject.POLL_SECONDS == 120
assert subject.STATE_PATH.endswith("all-open-prs.json")
assert "--author" in subject.open_prs.__code__.co_consts[1]
print("PASS: the all-open-PR controller uses a two-minute authenticated-user query")
