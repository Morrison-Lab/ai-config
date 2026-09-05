#!/usr/bin/env python3
"""Pin the new-line-breaks job's pull_request gate in .github/workflows/validate.yml.

Morrison-Lab/ai-config#1730: on a push run the diff-scoped action skipped with
a warning and concluded success, which read as a pass. The fix is a job-level
`if:` plus a base-ref that names the PR base directly. Nothing else exercises
those two lines, so reverting either would leave every other suite green.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

passes = 0
failures = 0


def check(name, cond, extra=""):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name} {extra}")


doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
job = (doc.get("jobs") or {}).get("new-line-breaks")
check("validate.yml has a new-line-breaks job", job is not None)
if job is not None:
    check("the job is gated on pull_request events",
          job.get("if") == "github.event_name == 'pull_request'", repr(job.get("if")))
    step = next((st for st in job.get("steps", []) if "check-new-line-breaks" in str(st.get("uses", ""))), None)
    check("the job calls the check-new-line-breaks action", step is not None)
    if step is not None:
        base_ref = str((step.get("with") or {}).get("base-ref", ""))
        check("base-ref names the PR base directly (no push-event fallback to an empty string)",
              base_ref.strip() == "${{ github.event.pull_request.base.sha }}", repr(base_ref))

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
