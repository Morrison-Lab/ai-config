#!/usr/bin/env python3
"""Tests for flag-partial-put-to-resource-root.py.

Run: python3 hooks/test-flag-partial-put-to-resource-root.py

The mutation block at the bottom asserts each of the three conditions is
load-bearing, so a later widening that drops one fails here rather than turning
the guard into a PUT detector.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "flag-partial-put-to-resource-root.py")
FAILURES = []


def run(text, tool="mcp__claude-in-chrome__javascript_tool"):
    key = "command" if tool == "Bash" else "text"
    payload = {"tool_name": tool, "tool_input": {key: text}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30)
    return p.stdout.strip()


def check(name, got, want_fire):
    fired = bool(got)
    if fired != want_fire:
        FAILURES.append(f"{name}: expected {'fire' if want_fire else 'silence'}, "
                        f"got {'fire' if fired else 'silence'}")
    if fired:
        try:
            json.loads(got)
        except Exception as exc:
            FAILURES.append(f"{name}: stdout not valid JSON ({exc})")


# ------------------------------------------------------------- the real case

INCIDENT = """
const r = await fetch(`/api/v1/courses/${C}`, {method:'PUT',
  headers:{'Content-Type':'application/json'},
  body: JSON.stringify({course:{apply_assignment_group_weights:true}})});
"""
check("the measured incident fires", run(INCIDENT), True)

# ------------------------------------------------- each condition is required

check("sub-resource PUT stays silent",
      run("""await fetch(`/api/v1/courses/${C}/pages/calendar`, {method:'PUT',
             body: JSON.stringify({wiki_page:{published:true}})});"""), False)

check("deeper sub-resource stays silent",
      run("""await fetch('/api/v1/courses/1906010/assignments/11781497',
             {method:'PUT', body:'{}'});"""), False)

check("GET to a resource root stays silent (no PUT)",
      run("const c = await fetch(`/api/v1/courses/${C}`).then(r=>r.json());"), False)

check("POST to a resource root stays silent",
      run("""await fetch('/api/v1/courses/1906010', {method:'POST', body:'{}'});"""),
      False)

check("resource-root PUT WITH a whole-object diff stays silent",
      run("""const before = await (await fetch(`/api/v1/courses/${C}`)).json();
             await fetch(`/api/v1/courses/${C}`, {method:'PUT', body:'{}'});
             const after = await (await fetch(`/api/v1/courses/${C}`)).json();
             const lost = Object.keys(before).filter(k => before[k]!==null && after[k]===null);"""),
      False)

# --------------------------------------------------------------- url shapes

check("absolute URL resource root fires",
      run("""await fetch('https://wwu.instructure.com/api/v1/courses/1906010',
             {method:'PUT', body:'{}'});"""), True)

check("trailing slash still counts as the root",
      run("""await fetch('/api/v1/users/42/', {method:'PUT', body:'{}'});"""), True)

check("interpolated id fires",
      run("""await fetch(`/api/v1/accounts/${A}`, {method:'PUT', body:'{}'});"""), True)

# ------------------------------------------------------------------- Bash

check("curl -X PUT to a resource root fires",
      run("""curl -X PUT https://example.test/api/v1/courses/12 -d '{}'""", tool="Bash"),
      True)

check("curl -X PUT to a sub-resource stays silent",
      run("""curl -X PUT https://example.test/api/v1/courses/12/pages/x -d '{}'""", tool="Bash"),
      False)

check("an unrelated tool stays silent",
      run(INCIDENT, tool="Read"), False)

# ------------------------------------------------------------- robustness

p = subprocess.run([sys.executable, HOOK], input="not json",
                   capture_output=True, text=True, timeout=30)
if p.returncode != 0 or p.stdout.strip():
    FAILURES.append(f"non-JSON stdin: expected silent exit 0, got rc={p.returncode}")

check("empty text is silent", run(""), False)

# --------------------------------------------------------- mutation checks
#
# Each constructs the input a guard missing that condition would mishandle.

check("mutation: without the resource-root test, a sub-resource PUT would fire",
      run("""await fetch('/api/v1/courses/1/pages/p', {method:'PUT', body:'{}'});"""),
      False)
check("mutation: without the PUT test, a plain GET would fire",
      run("await fetch('/api/v1/courses/1');"), False)
check("mutation: without the diff test, a careful call would fire",
      run("""const before = await (await fetch('/api/v1/courses/1')).json();
             await fetch('/api/v1/courses/1', {method:'PUT', body:'{}'});
             const after = await (await fetch('/api/v1/courses/1')).json();
             const lost = Object.keys(before).filter(k=>after[k]===null);"""),
      False)

if FAILURES:
    print(f"FAIL ({len(FAILURES)})")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok")
