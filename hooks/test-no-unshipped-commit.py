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

# --- ai-config#1807 review round 3: a `<<<` HERESTRING is not a heredoc -----
# `HEREDOC_START.search()` could begin matching at the SECOND `<`, reading
# `cat <<< hello` as a heredoc tagged `hello`. A herestring has no body and no
# terminator, so the terminator search ran off the end and swallowed every
# remaining line -- unbounded trailing text, strictly worse than rounds 1-2,
# which lost one heredoc body each.
HERESTRING_BAREWORD = """cat <<< hello > /tmp/f
git commit -m real"""

HERESTRING_QUOTED = """cat <<< "literal" > /tmp/out
git commit -m real"""

herestring_bareword = transcript([HERESTRING_BAREWORD])
herestring_quoted = transcript([HERESTRING_QUOTED])

# --- ai-config#1963: `\b` treats the hyphen as a word boundary ---------------
# `git\s+commit\b` matched `git commit-tree`, git plumbing that writes a commit
# object and moves no ref -- so nothing is ever pushed, `pending` was never
# cleared, and every later Stop blocked on a fully-pushed branch. All three
# commands below are spelled out in one suite because the defect is exactly
# that the guard could not tell them apart.
COMMIT_TREE = 'git commit-tree "$tree" -p "$BASE" -m "synthetic"'
COMMIT_GRAPH = "git commit-graph write --reachable"
REAL_COMMIT = "git commit -m real"

# The mirror of the population-shrink trap: the lookahead must not blind the
# guard to a real commit sharing a command with plumbing. The `git commit-tree`
# here came from a `git merge-tree` negative control, which is the shape that
# produced the original report.
PLUMBING_THEN_REAL = 'git commit-tree "$t" -p "$b" -m x\ngit commit -m real'

# PUSH carries the same lookahead for symmetry. No hyphenated `git push-*`
# exists today, so this pins the mirror bug rather than a live one: a
# hypothetical sibling must not DISCHARGE a genuinely pending commit.
PUSH_SIBLING_DOES_NOT_DISCHARGE = "git push-mirror --all"

commit_tree = transcript([COMMIT_TREE])
commit_graph = transcript([COMMIT_GRAPH])
real_commit = transcript([REAL_COMMIT])
plumbing_then_real = transcript([PLUMBING_THEN_REAL])
push_sibling = transcript([REAL_COMMIT, PUSH_SIBLING_DOES_NOT_DISCHARGE])

# --- ai-config#2365 / #2395: an env-prefixed push must discharge -------------
# `ALLOW_UNREVIEWED_PUSH=1 git push` is the sibling pre-push guard's own
# documented override spelling; a session whose every push carries it was
# blocked on every Stop, and only a no-op plain push silenced it.
env_prefixed_push = transcript([
    "git commit -m hook",
    "ALLOW_UNREVIEWED_PUSH=1 git push origin HEAD",
])
env_prefixed_commit = transcript([
    "GIT_AUTHOR_DATE='2026-01-01T00:00:00' git commit -m hook",
])
two_env_push = transcript([
    "git commit -m hook",
    "A=1 B=2 git push origin HEAD",
])
# The discriminating anchor probe: `git push` IS present, preceded by an
# env-shaped token, but the whole thing sits mid-`echo` -- dropping the
# segment anchor from PUSH makes this discharge, so the case pins the
# anchor rather than merely restating the tolerance.
env_word_not_push = transcript([
    "git commit -m hook",
    "echo ALLOW_UNREVIEWED_PUSH=1 git push is the spelling",
])
# The anchor rewrite ((?:^|[;&|\n])\s* instead of (?:^|[;&|\n]\s*)) also
# admits leading whitespace before an unprefixed command -- deliberate, and
# pinned here so the widening is documented rather than incidental.
leading_ws_push = transcript([
    "git commit -m hook",
    "  git push origin HEAD",
])
env_prefixed_create = transcript([
    "git commit -m hook",
    "GH_TOKEN=x gh pr create --fill",
])

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
    assert subject.pending_commit(env_prefixed_push) is None, \
        "an env-prefixed push must discharge (ai-config#2365/#2395)"
    assert subject.pending_commit(env_prefixed_commit) is not None, \
        "an env-prefixed commit must still arm"
    assert subject.pending_commit(two_env_push) is None, \
        "several env assignments before the push still discharge"
    assert subject.pending_commit(env_word_not_push) is not None, \
        "prose mentioning the env token mid-command is not a push"
    assert subject.pending_commit(leading_ws_push) is None, \
        "a leading-whitespace push still discharges (documented widening)"
    assert subject.pending_commit(env_prefixed_create) is None, \
        "an env-prefixed gh pr create discharges too (CREATE symmetry)"
    assert subject.pending_commit(executed_redirect) is not None, "bash <<EOF > file still executes"
    assert subject.pending_commit(executed_fd_dup) is not None, "2>&1 is not a file write"
    assert subject.pending_commit(indented_decoy) is not None, "an indented decoy is not a terminator"
    assert subject.pending_commit(tab_terminator) is None, "<<- strips leading tabs"
    assert subject.pending_commit(piped_to_shell) is not None, "a heredoc piped to a shell executes"
    assert subject.pending_commit(separator_then_shell) is not None, "another command's redirect is not this heredoc's"
    assert subject.pending_commit(writer_after_separator) is None, "a writer reached through && is still a writer"
    assert subject.pending_commit(herestring_bareword) is not None, "<<< is a herestring, not a heredoc"
    assert subject.pending_commit(herestring_quoted) is not None, "a quoted herestring operand is not a tag"
    assert subject.pending_commit(commit_tree) is None, "git commit-tree moves no ref, so it cannot arm"
    assert subject.pending_commit(commit_graph) is None, "git commit-graph write is not a commit"
    assert subject.pending_commit(real_commit) is not None, "a plain git commit must still arm"
    assert subject.pending_commit(plumbing_then_real) is not None, "plumbing must not hide a real commit beside it"
    assert subject.pending_commit(push_sibling) is not None, "a hyphenated push sibling must not discharge"
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
    os.unlink(herestring_bareword)
    os.unlink(herestring_quoted)
    os.unlink(commit_tree)
    os.unlink(commit_graph)
    os.unlink(real_commit)
    os.unlink(plumbing_then_real)
    os.unlink(push_sibling)
    os.unlink(env_prefixed_push)
    os.unlink(env_prefixed_commit)
    os.unlink(two_env_push)
    os.unlink(env_word_not_push)
    os.unlink(leading_ws_push)
    os.unlink(env_prefixed_create)
print("PASS: an unshipped commit blocks, while push and PR creation discharge it")
print("PASS: a heredoc written to a file is quoted text; an executed heredoc still arms")
print("PASS: a redirect does not make a heredoc data, and only bash's own terminator ends one")
print("PASS: WRITER and REDIRECT are scoped to the segment that owns the heredoc")
print("PASS: a <<< herestring is not mistaken for a heredoc")
print("PASS: commit-tree and commit-graph are not commits, while a plain commit still arms")
print("PASS: an env-prefixed push discharges; an env-prefixed commit still arms")


def antigravity_transcript(tool_calls):
    import tempfile
    import os
    import json
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        stream.write(json.dumps({"type": "PLANNER_RESPONSE", "tool_calls": tool_calls}) + "\n")
    return path

def combine_transcripts(paths):
    import tempfile
    import os
    handle, outpath = tempfile.mkstemp()
    with os.fdopen(handle, "w") as out:
        for p in paths:
            with open(p) as inc:
                out.write(inc.read())
    return outpath

ag_commit = antigravity_transcript([{"name": "run_command", "args": {"CommandLine": "git commit -m \"fix\""}}])
ag_commit_truncated = antigravity_transcript([{"name": "run_command", "args": {"CommandLine": "\"git commit -m \\\"fix\\\"\\n"}}])
ag_push = antigravity_transcript([{"name": "run_command", "args": {"CommandLine": "git push origin main"}}])

try:
    assert subject.pending_commit(ag_commit) == "git commit -m \"fix\""
    assert subject.pending_commit(ag_commit_truncated) == 'git commit -m "fix"\n'
    # Test push discharging
    combined = combine_transcripts([ag_commit_truncated, ag_push])
    try:
        assert subject.pending_commit(combined) is None
    finally:
        import os
        os.unlink(combined)
finally:
    import os
    os.unlink(ag_commit)
    os.unlink(ag_commit_truncated)
    os.unlink(ag_push)

print("PASS: Antigravity PLANNER_RESPONSE parses and correctly discharges")
