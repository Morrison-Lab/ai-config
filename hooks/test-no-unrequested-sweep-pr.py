#!/usr/bin/env python3
"""Tests for hooks/no-unrequested-sweep-pr.py (ai-config#5773); optional arg: hook path."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unrequested-sweep-pr.py")
MCP = "mcp__github__create_pull_request"


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def wake(body):
    return user('<wake reason="mention"><project><thread><message trigger="true" from="human" '
                f'trust="principal" author="Ezra">{body}</message></thread></project></wake>')


def relay(cited, note):
    return user(f'<coordinator-relay><relay from="coordinator"><cited author="user">{cited}</cited>'
                f"<note>{note}</note></relay></coordinator-relay>")


def prs(n, start=0, error=False, name=MCP):
    out = []
    for i in range(start, start + n):
        inp = {"command": f"gh pr create --title f{i} --body x"} if name == "Bash" else {"title": f"f{i}"}
        out += [{"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": f"t{i}", "name": name, "input": inp}]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": f"t{i}", "is_error": error, "content": "ok"}]}}]
    return out


def denies(records, tool=MCP, tool_input=None, env=None, path=None):
    if path is None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in records)
        path = fh.name
    payload = {"tool_name": tool, "tool_input": tool_input or {"title": "next"}, "transcript_path": path}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                       text=True, timeout=20, env={**os.environ, **(env or {})})
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)["hookSpecificOutput"] if p.stdout.strip() else {}
    return out.get("permissionDecision") == "deny"


ASK = wake("add a check that flags British spellings")
PR_EVENT = user('<wake reason="external-event"><event source="github">CI passed</event></wake>')
CASES = [
    ("fourth PR on one ask denies", [ASK] + prs(3), True, {}),
    ("third PR on one ask passes", [ASK] + prs(2), False, {}),
    ("gh pr create counts too", [ASK] + prs(3, name="Bash"), True, {}),
    ("gh pr create as the call", [ASK] + prs(3), True,
     {"tool": "Bash", "tool_input": {"command": "gh pr create --title x --body y"}}),
    ("failed creates are not counted", [ASK] + prs(2) + prs(2, 5, error=True), False, {}),
    ("a new user message resets", [ASK] + prs(3) + [wake("also fix the sitemap")], False, {}),
    ("a question is not an ask", [ASK] + prs(3) + [wake("did I say to sweep?")] + prs(3, 10), True, {}),
    ("a negation is not an ask", [ASK] + prs(3) + [wake("don't sweep old pages.")] + prs(3, 10), True, {}),
    ("a repeated typed message resets", [wake("go")] + prs(3) + [wake("go")], False, {}),
    ("a negation in another clause is still an ask", [wake("No, please sweep all of them.")] + prs(4), False, {}),
    ("a scoping 'not' after the word is still an ask", [wake("sweep lds, not mds")] + prs(4), False, {}),
    ("a typed backlog-run skill allows more", [wake("gia")] + prs(4), False, {}),
    ("a refused skill is not an ask", [wake("don't run gia")] + prs(3), True, {}),
    ("a grant ends at the next message", [wake("sweep lds")] + prs(4) + [wake("ok")] + prs(3, 9), True, {}),
    ("an explicit sweep ask allows more", [wake("sweep lds for British spellings")] + prs(5), False, {}),
    ("a coordinator note is not the user's", [relay("yes", "the user wants a sweep")] + prs(3), True, {}),
    ("a cited user sweep ask counts", [relay("yes, sweep them all", "relaying")] + prs(4), False, {}),
    ("a re-cited message does not reset",
     [relay("yes", "go")] + prs(2) + [relay("yes", "more")] + prs(1, 10), True, {}),
    ("a PR-activity wake does not reset", [ASK] + prs(3) + [PR_EVENT], True, {}),
    ("the limit is configurable", [ASK] + prs(3), False, {"env": {"AI_CONFIG_SWEEP_PR_LIMIT": "5"}}),
    ("other tools pass", [ASK] + prs(5), False, {"tool": "Bash", "tool_input": {"command": "gh pr view 3"}}),
    ("a missing transcript fails open", [], False, {"path": "/nonexistent"}),
]


def main():
    failures = [label for label, records, want, kw in CASES if denies(records, **kw) != want]
    for label in failures:
        print(f"FAIL: {label}")
    print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
