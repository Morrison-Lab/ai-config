#!/usr/bin/env python3
"""Regression tests for flag-unexplained-analysis-choice.py."""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

FENCE = "`" * 3
CUT = FENCE + "{r}\nbins <- cut(d$age, breaks = c(38, 41, 44))\n" + FENCE + "\n"

# The lds case: a bin in code and a caption that never says why.
bare = CUT + "The groups are ages 39 to 41 and 42 to 44.\n"
assert subject.choices_without_reason(bare), "binning without a reason must warn"
print("PASS: a bin with no explaining prose warns")

# The same edit with the reasoning is quiet.
reasoned = CUT + "Three-year groups are a compromise: wider ones hide the trend.\n"
assert not subject.choices_without_reason(reasoned)
print("PASS: a bin with a stated reason is quiet")

# A seed is a choice too.
seed = FENCE + "{r}\nset.seed(1)\n" + FENCE + "\n"
assert subject.choices_without_reason(seed)
print("PASS: a seed with no explaining prose warns")

# Plain code with no choice is quiet, and so is a code comment.
plain = FENCE + "{r}\nfit <- lm(y ~ x, data = d)\n# cut(x, breaks = 3)\n" + FENCE + "\n"
assert not subject.choices_without_reason(plain)
print("PASS: ordinary code and commented-out code are quiet")

# The agent reads additionalContext: run the hook end to end.
import io
import json

payload = {"tool_name": "Edit", "tool_input": {"file_path": "chapters/x.qmd", "new_string": bare}}
sys.stdin = io.StringIO(json.dumps(payload))
buf = io.StringIO()
sys.stdout, real = buf, sys.stdout
try:
    subject.main()
finally:
    sys.stdout = real
out = json.loads(buf.getvalue())
assert "additionalContext" in out["hookSpecificOutput"]
assert "ai-config#4905" in out["hookSpecificOutput"]["additionalContext"]
print("PASS: the warning reaches additionalContext for a page edit")

sys.stdin = io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x.py", "new_string": bare}}))
buf = io.StringIO()
sys.stdout, real = buf, sys.stdout
try:
    subject.main()
finally:
    sys.stdout = real
assert buf.getvalue() == ""
print("PASS: a non-page file is out of scope")

assert subject.added_text("Edit", {"new_string": "x"}) == "x"
assert subject.added_text("MultiEdit", {"edits": [{"new_string": "a"}, {"new_string": "b"}]}) == "a\nb"
print("PASS: added text is read from Write, Edit and MultiEdit")
