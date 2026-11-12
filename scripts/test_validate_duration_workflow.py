#!/usr/bin/env python3
"""Run validate-duration.yml's two steps against stub commands (ai-config#3384).

Each step runs under the shell GitHub gives it: `shell: bash` is
`bash --noprofile --norc -eo pipefail`, which the test requires, since under
the default `bash -e` a failed `gh api` would fall through to a new issue.
The `gh` stub answers `gh api` from a fixture through the step's own --jq
filter, run by the real jq, and records every call, so the tests cover the
query, the filter and each branch. A `python3` stub stands in for the check,
to test how the judge step maps its exit codes. The `run:` blocks come from
yaml.safe_load, which already dedents them
(shared/coding/yaml-embedded-script-double-dedent.md).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/validate-duration.yml"
TITLE = "validate job on main has slowed down"
MARKER = "<!-- validate-duration-tracking -->"
SHELLS = {"bash": ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c"]}
GH = """#!/bin/bash
echo "$*" | tr '\\n' ' ' >> "$LOG"
echo >> "$LOG"
for ((i = 1; i < $#; i++)); do
  j=$((i + 1))
  case "${!i}" in
    --title) printf '%s' "${!j}" > title ;;
    --body-file) cp "${!j}" body ;;
  esac
done
if [ "$1" = api ]; then
  [ -n "$API_FAILS" ] && exit 1
  while [ "$#" -gt 0 ] && [ "$1" != --jq ]; do shift; done
  jq -r "$2" "$FIXTURE"
fi
"""
PYTHON = '#!/bin/bash\necho report\nexit "$CODE"\n'

steps = {s.get("name"): s for s in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["check"]["steps"]}
now = datetime.now(timezone.utc)
failures = 0
total = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures, total
    total += 1
    print(("PASS: " if ok else "FAIL: ") + name + ("" if ok else f" -- {detail}"))
    failures += not ok


def run(step: str, **env: str) -> tuple[int, list[str], str, dict[str, str]]:
    """Run `step` with stubbed gh and python3.

    Returns the exit code, the gh calls, the step outputs, and the title and
    body that gh was last given.
    """
    shell = steps[step].get("shell")
    if shell not in SHELLS:
        raise SystemExit(f"step {step!r} has shell {shell!r}; the test needs one of {list(SHELLS)}")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name, body in (("gh", GH), ("python3", PYTHON)):
            (d / name).write_text(body, encoding="utf-8")
            (d / name).chmod(0o755)
        (d / "report.txt").write_text("report\n", encoding="utf-8")
        (d / "out").write_text("", encoding="utf-8")
        full = {**os.environ, "PATH": f"{d}{os.pathsep}{os.environ['PATH']}", "LOG": str(d / "log"),
                "GITHUB_OUTPUT": str(d / "out"), "GH_REPO": "o/r",
                "RUN_URL": "https://example.invalid/run", "LAG_DAYS": "28", **env}
        done = subprocess.run([*SHELLS[shell], steps[step]["run"]], cwd=d, env=full,
                              capture_output=True, text=True)
        log = (d / "log").read_text(encoding="utf-8").splitlines() if (d / "log").exists() else []
        sent = {k: (d / k).read_text(encoding="utf-8") for k in ("title", "body") if (d / k).exists()}
        return done.returncode, log, (d / "out").read_text(encoding="utf-8"), sent


def ago(days: int) -> str:
    return (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def issue(number: int, state: str = "open", reason: str | None = None, closed: str | None = None,
          title: str = TITLE, body: str | None = MARKER, **extra) -> dict:
    return {"number": number, "state": state, "state_reason": reason, "closed_at": closed,
            "title": title, "body": body, **extra}


JUDGE = "Compare recent and baseline durations"
for code, want_exit, want_out in (("0", 0, "code=0\n"), ("1", 0, "code=1\n"), ("3", 3, ""), ("4", 4, "")):
    got, _, out, _ = run(JUDGE, CODE=code)
    check(f"judge step: check exit {code} gives step exit {want_exit}", got == want_exit and out == want_out,
          f"exit {got}, output {out!r}")

ISSUE = "Open or update the tracking issue"
cases = [
    ("no tracking issue opens one and fails", [issue(5, title="other", body=None),
                                               issue(4, pull_request={})], 1, "issue create"),
    ("an open issue gets a comment", [issue(7), issue(3, "closed", "completed", ago(90))],
     0, "issue comment 7"),
    ("a recent not-planned close only warns", [issue(8, "closed", "not_planned", ago(10))], 0, None),
    ("an old not-planned close opens a new issue", [issue(9, "closed", "not_planned", ago(40))],
     1, "issue create"),
    ("a fixed issue opens a new one", [issue(10, "closed", "completed", ago(3)), issue(2)],
     1, "issue create"),
    ("an issue without the marker is ignored", [issue(11, body="no marker")], 1, "issue create"),
]


def run_issue(items: list[dict], **env: str) -> tuple[int, list[str], list[str], dict[str, str]]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(items, f)
    try:
        code, log, _, sent = run(ISSUE, FIXTURE=f.name, **env)
    finally:
        os.unlink(f.name)
    return code, log, [c for c in log if not c.startswith("api ")], sent


for name, items, want_code, want_call in cases:
    code, log, calls, sent = run_issue(items)
    check(name, code == want_code and (calls == [] if want_call is None
                                       else len(calls) == 1 and calls[0].startswith(want_call)),
          f"exit {code}, calls {calls}")
    if want_call:
        check(f"{name}: the body carries the marker and the report",
              MARKER in sent.get("body", "") and "report" in sent.get("body", ""), str(sent))
    if want_call == "issue create":
        check(f"{name}: the issue is labelled P2", "--label P2" in calls[0], calls[0])
        again = run_issue([issue(99, title=sent.get("title", ""), body=sent.get("body"))])[2]
        check(f"{name}: the next run finds the issue it opened", bool(again)
              and again[0].startswith("issue comment 99"), str(again))

api = next((c for c in log if c.startswith("api ")), "")
for part in ("--paginate", "repos/o/r/issues?", "state=all", "creator=github-actions%5Bbot%5D",
             "sort=created", "direction=desc"):
    check(f"the lookup asks for {part}", part in api, api)

code, log, _, _ = run(ISSUE, FIXTURE="/nonexistent", API_FAILS="1")
check("a failed lookup stops the step before any create",
      code != 0 and not any(c.startswith("issue ") for c in log), f"exit {code}, calls {log}")

print(f"\n{total - failures} passed, {failures} failed")
sys.exit(1 if failures else 0)
