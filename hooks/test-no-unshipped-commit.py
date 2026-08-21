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

# --- ai-config#1807 review round 1: two false NEGATIVES in the first fix ----
# Both let a real unpushed commit past the guard, which is strictly worse than
# the false positive being fixed: that one over-blocked, these under-block.

# A heredoc-start line can redirect AND still execute its body. Testing only
# for "a redirect somewhere on the line" classified these as data.
EXECUTED_WITH_FILE_REDIRECT = """bash <<'EOF' > /tmp/log
git commit -m real
EOF"""

# `2>&1` is fd duplication, not a file write at all.
EXECUTED_WITH_FD_DUP = """bash <<'EOF' 2>&1
git commit -m real
EOF"""

# bash terminates a plain `<<TAG` only on a line EQUAL to TAG. An indented
# decoy is body text to bash, but `.strip()` accepted it as a terminator,
# ending the strip early and exposing a quoted `git push` -- which then
# discharged a genuinely pending commit. The mirror of QUOTED_PUSH above.
INDENTED_DECOY_TERMINATOR = """cat > /tmp/n.md <<'EOF'
  EOF
git push origin main
EOF
gh issue create --repo o/r --title x --body-file /tmp/n.md"""

# `<<-TAG` strips leading TABS, so a tab-indented terminator is real.
TAB_TERMINATOR_IS_REAL = """cat > /tmp/n.md <<-'EOF'
git commit -m quoted
\tEOF"""

executed_redirect = transcript([EXECUTED_WITH_FILE_REDIRECT])
executed_fd_dup = transcript([EXECUTED_WITH_FD_DUP])
indented_decoy = transcript(["git commit -m hook", INDENTED_DECOY_TERMINATOR])
tab_terminator = transcript([TAB_TERMINATOR_IS_REAL])

# --- ai-config#1807 review round 2: the same class, one token to the right --
# WRITER and REDIRECT were matched against the WHOLE line, so a `cat`/`tee`
# or a redirect belonging to a DIFFERENT command in the same pipeline or list
# satisfied them. Both hide a real commit.
PIPED_TO_SHELL = """cat <<'EOF' | bash 2>&1
git commit -m real
EOF"""

SEPARATOR_THEN_SHELL = """cat notes.txt > /tmp/x; bash <<'EOF'
git commit -m real
EOF"""

# The positive side of the same scoping: a writer reached through `&&` is
# still a writer, so this must stay quoted rather than arming.
WRITER_AFTER_SEPARATOR = """cd /x && cat > /tmp/i.md <<'EOF'
git commit -m quoted
EOF"""

piped_to_shell = transcript([PIPED_TO_SHELL])
separator_then_shell = transcript([SEPARATOR_THEN_SHELL])
writer_after_separator = transcript([WRITER_AFTER_SEPARATOR])

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
    assert subject.pending_commit(executed_redirect) is not None, "bash <<EOF > file still executes"
    assert subject.pending_commit(executed_fd_dup) is not None, "2>&1 is not a file write"
    assert subject.pending_commit(indented_decoy) is not None, "an indented decoy is not a terminator"
    assert subject.pending_commit(tab_terminator) is None, "<<- strips leading tabs"
    assert subject.pending_commit(piped_to_shell) is not None, "a heredoc piped to a shell executes"
    assert subject.pending_commit(separator_then_shell) is not None, "another command's redirect is not this heredoc's"
    assert subject.pending_commit(writer_after_separator) is None, "a writer reached through && is still a writer"
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
    os.unlink(executed_redirect)
    os.unlink(executed_fd_dup)
    os.unlink(indented_decoy)
    os.unlink(tab_terminator)
    os.unlink(piped_to_shell)
    os.unlink(separator_then_shell)
    os.unlink(writer_after_separator)
print("PASS: an unshipped commit blocks, while push and PR creation discharge it")
print("PASS: a heredoc written to a file is quoted text; an executed heredoc still arms")
print("PASS: a redirect does not make a heredoc data, and only bash's own terminator ends one")
print("PASS: WRITER and REDIRECT are scoped to the segment that owns the heredoc")
