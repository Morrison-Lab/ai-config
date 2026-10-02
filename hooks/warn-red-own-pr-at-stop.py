#!/usr/bin/env python3
"""Stop warn: a PR this session opened still shows failing checks nobody acted on.

The rule "fix red CI on your own PRs unprompted" lives in the PR-driving rules,
and nothing fired at turn end, so a turn could end over a red PR and the person
had to ask "fix failing CI?" (twice in one day). This hook checks the one thing
that is decidable from the transcript.

Own PRs: numbers returned by a `create_pull_request` result or a `gh pr create`
result, plus PRs passed to `subscribe_pr_activity`.

Latest status evidence per PR, in transcript order:
  - a `check_run` wake event (a user-side record, JSON carrying `conclusion`),
  - a `get_check_runs` result (`pull_request_read`), read as a complete listing.
A failing conclusion is `failure`, `timed_out` or `startup_failure`. `success`,
`skipped`, `neutral`, `cancelled` and an unfinished run (no conclusion) are not.

A failure is acted on when, after the evidence, the transcript shows a
`git push` (or an MCP file write), `update_pull_request_branch` or an
`add_issue_comment` on that PR, `gh pr comment` on it, or a later reading in
which the check no longer fails.

Not fired for a bot-review check (`review / claude-review`, `require-review`,
`require-clean-verdict`) whose text says quota, session limit or did not finish:
nothing in the PR can fix that.

Deliberate limits:
  - Transcript only, no network. A failure the session never saw is not seen.
  - PRs are keyed by number alone, so the same number in two repositories
    shares one state.
  - Any push counts as acting on every PR, because the push does not name one.
  - A merged or closed PR is dropped only when this session called
    `merge_pull_request` on it.
  - Warns, never blocks; a missing or unreadable transcript is silent.
"""
import json
import os
import re
import shlex
import sys

FAILING = {"failure", "timed_out", "startup_failure"}
BOT_REVIEW = re.compile(r"claude-review|require-review|require-clean-verdict", re.I)
UNFIXABLE = re.compile(r"quota|session limit|did not finish", re.I)
PR_URL = re.compile(r"/pull/(\d+)")
PR_REF = re.compile(r"/pull/(\d+)|#(\d+)|\bPR (\d+)", re.I)
PR_KEYS = ("pullNumber", "pull_number", "prNumber", "pr_number", "number")
MCP_PUSH = re.compile(r"(push_files|create_or_update_file)$")
# Fallback for a wake event that is not JSON: one name and one conclusion.
TEXT_RUN = re.compile(
    r"check_run.*?name\W+([^\n,\"']+).*?conclusion\W+(failure|timed_out|startup_failure)",
    re.I | re.S)

NOTE = (
    "[hook: warn-red-own-pr-at-stop] PR {prs} opened in this session still "
    "shows failing checks that nothing since has acted on: {detail}. Fix it, "
    "or comment once why it is not this PR's; do not end the turn."
)


def blocks(record):
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else record.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(c.get("text", c) if isinstance(c, dict) else c)
                         for c in content)
    return ""


def decoded(text):
    """Every JSON object or array found in a string (whole, or from each brace)."""
    try:
        yield json.loads(text)
        return
    except ValueError:
        pass
    decoder, pos = json.JSONDecoder(), 0
    while True:
        found = [p for p in (text.find("{", pos), text.find("[", pos)) if p >= 0]
        if not found:
            return
        pos = min(found)
        try:
            value, end = decoder.raw_decode(text, pos)
        except ValueError:
            pos += 1
            continue
        yield value
        pos = end


def check_runs(node):
    """Dicts that look like check runs: a name and a conclusion key."""
    if isinstance(node, dict):
        if "name" in node and "conclusion" in node:
            yield node
        for value in node.values():
            yield from check_runs(value)
    elif isinstance(node, list):
        for value in node:
            yield from check_runs(value)


def pr_numbers(node):
    """PR numbers named under a `pull_requests` key anywhere in a decoded event."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pull_requests" and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and isinstance(item.get("number"), int):
                        yield item["number"]
            else:
                yield from pr_numbers(value)
    elif isinstance(node, list):
        for value in node:
            yield from pr_numbers(value)


def number_from_input(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in PR_KEYS:
        value = tool_input.get(key)
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return int(value)
    for value in tool_input.values():
        if isinstance(value, str) and PR_URL.search(value):
            return int(PR_URL.search(value).group(1))
    return None


def issue_number(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in ("issue_number", "issueNumber", "pullNumber", "pull_number", "number"):
        value = tool_input.get(key)
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return int(value)
    return None


def bash_words(command):
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


def is_push(command):
    words = bash_words(command)
    for i, word in enumerate(words):
        if word == "git":
            rest = words[i + 1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
            if rest and rest[0] == "push":
                return True
    return False


def unfixable(run):
    return bool(BOT_REVIEW.search(str(run.get("name"))) and UNFIXABLE.search(json.dumps(run)))


class State:
    def __init__(self):
        self.own = set()
        self.failing = {}   # pr -> {check name: record index of the evidence}
        self.actions = {}   # pr -> [record index]
        self.pushes = []    # record indexes; a push names no PR
        self.dropped = set()

    def evidence(self, pr, runs, index, complete):
        """Fold check runs into a PR's state. A complete listing replaces it."""
        mine = self.failing.setdefault(pr, {})
        if complete:
            mine.clear()
        for run in runs:
            name = str(run.get("name"))
            if run.get("conclusion") in FAILING and not unfixable(run):
                mine[name] = index
            elif run.get("conclusion") is not None:
                mine.pop(name, None)

    def unacted(self):
        found = {}
        for pr in sorted(self.own - self.dropped):
            later = self.actions.get(pr, []) + self.pushes
            names = sorted(n for n, i in self.failing.get(pr, {}).items()
                           if not any(a > i for a in later))
            if names:
                found[pr] = names
        return found


def own_from_result(text, state):
    for match in PR_URL.finditer(text):
        state.own.add(int(match.group(1)))
    for value in decoded(text):
        if isinstance(value, dict) and isinstance(value.get("number"), int):
            state.own.add(value["number"])


def scan(path):
    state = State()
    uses = {}  # tool_use id -> (name, input)
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    for index, line in enumerate(lines):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        for block in blocks(record):
            kind = block.get("type")
            if kind == "tool_use":
                name = str(block.get("name") or "")
                tool_input = block.get("input")
                uses[block.get("id")] = (name, tool_input)
                note_action(state, name, tool_input, index)
            elif kind == "tool_result":
                name, tool_input = uses.get(block.get("tool_use_id"), ("", None))
                note_result(state, name, tool_input, text_of(block.get("content")), index)
            elif kind == "text" and record.get("type") == "user":
                if not (record.get("isMeta") and record.get("sourceToolUseID")):
                    note_wake(state, block.get("text") or "", index)
    return state


def note_action(state, name, tool_input, index):
    if name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            if is_push(command):
                state.pushes.append(index)
            words = bash_words(command)
            if "gh" in words and "comment" in words and "pr" in words:
                pr = next((int(w) for w in words if w.isdigit()), None)
                for w in words:
                    if PR_URL.search(w):
                        pr = int(PR_URL.search(w).group(1))
                if pr:
                    state.actions.setdefault(pr, []).append(index)
        return
    if MCP_PUSH.search(name):
        state.pushes.append(index)
    elif name.endswith("subscribe_pr_activity") and not name.endswith("unsubscribe_pr_activity"):
        pr = number_from_input(tool_input)
        if pr:
            state.own.add(pr)
    elif name.endswith(("update_pull_request_branch", "add_issue_comment")):
        pr = issue_number(tool_input)
        if pr:
            state.actions.setdefault(pr, []).append(index)
    elif name.endswith("merge_pull_request"):
        pr = number_from_input(tool_input)
        if pr:
            state.dropped.add(pr)


def note_result(state, name, tool_input, text, index):
    is_create = name.endswith("create_pull_request") or (
        name == "Bash" and isinstance(tool_input, dict)
        and re.search(r"\bgh pr create\b", str(tool_input.get("command"))))
    if is_create:
        own_from_result(text, state)
        return
    if name.endswith("pull_request_read") and isinstance(tool_input, dict) \
            and tool_input.get("method") == "get_check_runs":
        pr = number_from_input(tool_input)
        if pr:
            runs = [r for v in decoded(text) for r in check_runs(v)]
            state.evidence(pr, runs, index, complete=True)


def note_wake(state, text, index):
    if "check_run" not in text:
        return
    if state.own:
        runs, prs = [], set()
        for value in decoded(text):
            runs += list(check_runs(value))
            prs |= set(pr_numbers(value))
        if not runs:
            runs = [{"name": m.group(1).strip(), "conclusion": m.group(2).lower()}
                    for m in TEXT_RUN.finditer(text)]
        if not prs:
            prs = {int(a or b or c) for a, b, c in PR_REF.findall(text)}
        for pr in prs & state.own:
            state.evidence(pr, runs, index, complete=False)


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") if isinstance(payload, dict) else None
        if not isinstance(path, str) or not os.path.exists(path):
            return 0
        state = scan(path)
        found = state.unacted()
    except Exception:  # fail open: a guard that crashes must not wedge a session
        return 0
    if not found:
        return 0
    prs = ", ".join(f"#{pr}" for pr in found)
    detail = "; ".join(f"#{pr}: {', '.join(names)}" for pr, names in found.items())
    print(json.dumps({"systemMessage": NOTE.format(prs=prs, detail=detail)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
