#!/usr/bin/env python3
"""Regression tests for no-unexplained-analysis-choice.py."""
import importlib.util
import io
import json
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

FENCE = "`" * 3
CUT = FENCE + "{r}\nbins <- cut(d$age, breaks = c(38, 41, 44))\n" + FENCE + "\n"

# The lds case: a bin in code and a caption that never says why.
bare = CUT + "The groups are ages 39 to 41 and 42 to 44.\n"
assert subject.choices_without_reason(bare), "binning without a reason must block"
print("PASS: a bin with no explaining prose is flagged")

# The same edit with the reasoning is quiet.
reasoned = CUT + "Three-year groups are a compromise: wider ones hide the trend.\n"
assert not subject.choices_without_reason(reasoned)
print("PASS: a bin with a stated reason is quiet")

# A seed is not recognized: only binning blocks, to keep false positives low.
seed = FENCE + "{r}\nset.seed(1)\n" + FENCE + "\n"
assert not subject.choices_without_reason(seed)
print("PASS: a seed is not a recognized choice")

# Plain code with no choice is quiet, and so is a code comment.
plain = FENCE + "{r}\nfit <- lm(y ~ x, data = d)\n# cut(x, breaks = 3)\n" + FENCE + "\n"
assert not subject.choices_without_reason(plain)
print("PASS: ordinary code and commented-out code are quiet")

# The allow marker exempts a line.
allowed = FENCE + "{r}\nx <- cut(a, breaks = 3)  # check-unexplained-choices: allow\n" + FENCE + "\n"
assert not subject.choices_without_reason(allowed)
print("PASS: the allow marker exempts a line")

assert subject.apply_edits("Write", {"content": "w"}, "old") == "w"
assert subject.apply_edits("Edit", {"old_string": "b", "new_string": "X"}, "abc") == "aXc"
multi = {"edits": [{"old_string": "a", "new_string": "1"}, {"old_string": "c", "new_string": "3"}]}
assert subject.apply_edits("MultiEdit", multi, "abc") == "1b3"
print("PASS: the post-edit page is rebuilt for Write, Edit and MultiEdit")


def run(tool, path, text):
    payload = {"tool_name": tool, "tool_input": {"file_path": path, "new_string": text}}
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    sys.stdout, real = buf, sys.stdout
    try:
        subject.main()
    finally:
        sys.stdout = real
    return buf.getvalue()


# The agent reads the denial: run the hook end to end.
out = json.loads(run("Edit", "chapters/x.qmd", bare))
assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
assert "ai-config#4905" in out["hookSpecificOutput"]["additionalContext"]
print("PASS: a page edit with an unexplained bin is denied, with the reason in additionalContext")

assert run("Edit", "x.py", bare) == ""
assert run("Edit", "chapters/x.qmd", reasoned) == ""
print("PASS: a non-page file and an explained bin pass through silently")

# The review finding on ai-config#4908: a line added INSIDE an existing chunk
# carries no fence marker, and must still be seen as code.
import os
import tempfile

page = "Intro.\n\n" + FENCE + "{r}\nd <- read.csv('x.csv')\n" + FENCE + "\n\nAfter.\n"
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "p.qmd")
    with open(path, "w") as handle:
        handle.write(page)
    inside = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": path,
            "old_string": "d <- read.csv('x.csv')\n",
            "new_string": "d <- read.csv('x.csv')\nd$g <- cut(d$age, breaks = 3)\n",
        },
    }
    sys.stdin = io.StringIO(json.dumps(inside))
    buf = io.StringIO()
    sys.stdout, real = buf, sys.stdout
    try:
        subject.main()
    finally:
        sys.stdout = real
    assert json.loads(buf.getvalue())["hookSpecificOutput"]["permissionDecision"] == "deny"
    print("PASS: a bin added inside an existing chunk is denied")

    # A reason word in the page's prose within the window clears it.
    with open(path, "w") as handle:
        handle.write("We chose three groups because the data hold three clusters.\n\n" + page)
    sys.stdin = io.StringIO(json.dumps(inside))
    buf = io.StringIO()
    sys.stdout, real = buf, sys.stdout
    try:
        subject.main()
    finally:
        sys.stdout = real
    assert buf.getvalue() == ""
    print("PASS: a reason in nearby prose of the existing page clears the edit")

    # An edit that leaves an existing bin untouched is not blamed for it.
    with open(path, "w") as handle:
        handle.write(page.replace("read.csv('x.csv')", "cut(a, breaks = 3)"))
    untouched = {
        "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": "After.", "new_string": "After the chunk."},
    }
    sys.stdin = io.StringIO(json.dumps(untouched))
    buf = io.StringIO()
    sys.stdout, real = buf, sys.stdout
    try:
        subject.main()
    finally:
        sys.stdout = real
    assert buf.getvalue() == ""
    print("PASS: an existing bin the edit does not add is not blocked")
