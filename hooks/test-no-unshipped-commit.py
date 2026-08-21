#!/usr/bin/env python3
"""Regression tests for no-unshipped-commit.py."""
import importlib.util
import json
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def transcript(commands):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for command in commands:
            record = {"type": "assistant", "message": {"content": [{
                "type": "tool_use", "name": "Bash", "input": {"command": command}
            }]}}
            stream.write(json.dumps(record) + "\n")
    return path


unshipped = transcript(["git commit -m hook"])
pushed = transcript(["git commit -m hook", "git push origin branch"])
pr_opened = transcript(["git commit -m hook", "gh pr create --fill"])
multiline_unshipped = transcript(["git add -A\ngit commit -m hook"])
multiline_pushed = transcript(["git commit -m hook", "git add .\ngit push origin branch"])

# Test malformed line resilience
handle, malformed_path = tempfile.mkstemp()
with os.fdopen(handle, "w") as stream:
    stream.write("not valid json\n")
    stream.write(json.dumps({"type": "assistant", "message": {"content": [{
        "type": "tool_use", "name": "Bash", "input": {"command": "git commit -m x"}
    }]}}) + "\n")

# Test last_assistant_text
handle, text_path = tempfile.mkstemp()
with os.fdopen(handle, "w") as stream:
    stream.write(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "git commit -m x"}},
        {"type": "text", "text": "Done with task."}
    ]}}) + "\n")


# --- ai-config#1806: a quoted example must not arm the guard -----------------
# A corpus about git workflow quotes git commands in issue and PR bodies
# constantly. The heredoc body is written to a file, so nothing in it runs.
QUOTED_EXAMPLE = """cat > /tmp/iss.md <<'EOF'
Its prescribed opening move:

```bash
git commit --allow-empty -m "start: <issue title> (closes #<N>)"
```
EOF
gh issue create --repo o/r --title x --body-file /tmp/iss.md"""

# The MIRROR case, and the reason the strip is scoped to file redirects: this
# heredoc really does execute, so it must still arm. A fix that blinded the
# guard here would trade a false positive for a hole -- the population-shrink
# trap of ai-config#1803.
EXECUTED_HEREDOC = """bash <<'EOF'
git commit -m real
EOF"""

# A quoted example followed later by a REAL commit must still arm, so the
# strip cannot swallow the rest of the command.
QUOTED_THEN_REAL = """cat > /tmp/n.md <<'EOF'
git commit -m quoted
EOF
git commit -m real"""

# A file-redirect heredoc whose body quotes a PUSH must not DISCHARGE either:
# the strip has to be symmetric, or quoting `git push` in an issue body would
# clear a genuinely pending commit.
QUOTED_PUSH_DOES_NOT_DISCHARGE = """cat > /tmp/n.md <<'EOF'
git push origin main
EOF
gh issue create --repo o/r --title x --body-file /tmp/n.md"""

quoted_example = transcript([QUOTED_EXAMPLE])
executed_heredoc = transcript([EXECUTED_HEREDOC])
quoted_then_real = transcript([QUOTED_THEN_REAL])
quoted_push = transcript(["git commit -m hook", QUOTED_PUSH_DOES_NOT_DISCHARGE])

try:
    assert subject.pending_commit(unshipped) == "git commit -m hook"
    assert subject.pending_commit(pushed) is None
    assert subject.pending_commit(pr_opened) is None
    assert subject.pending_commit(multiline_unshipped) == "git add -A\ngit commit -m hook"
    assert subject.pending_commit(multiline_pushed) is None
    assert subject.pending_commit(malformed_path) == "git commit -m x"
    assert subject.last_assistant_text(text_path) == "Done with task."
    assert subject.pending_commit(quoted_example) is None, "a quoted example must not arm"
    assert subject.pending_commit(executed_heredoc) is not None, "an executed heredoc must still arm"
    assert subject.pending_commit(quoted_then_real) is not None, "a real commit after a quoted one must arm"
    assert subject.pending_commit(quoted_push) is not None, "a quoted push must not discharge"
finally:
    os.unlink(unshipped)
    os.unlink(pushed)
    os.unlink(pr_opened)
    os.unlink(multiline_unshipped)
    os.unlink(multiline_pushed)
    os.unlink(malformed_path)
    os.unlink(text_path)
    os.unlink(quoted_example)
    os.unlink(executed_heredoc)
    os.unlink(quoted_then_real)
    os.unlink(quoted_push)
print("PASS: an unshipped commit blocks, while push and PR creation discharge it")
print("PASS: a heredoc written to a file is quoted text; an executed heredoc still arms")
