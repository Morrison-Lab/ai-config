#!/usr/bin/env python3
"""Stop warn: a PR this session opened still shows failing checks nobody acted on.

The rule "fix red CI on your own PRs unprompted" lives in the PR-driving rules,
and nothing fired at turn end, so a turn could end over a red PR and the person
had to ask "fix failing CI?" (twice in one day). This hook checks the one thing
that is decidable from the transcript.

Own PRs: numbers returned by a `create_pull_request` result, or by a Bash
command that starts with `gh pr create` (only the `/pull/N` URL of that result).
Subscribing to a PR does not make it ours.

Latest status evidence per PR, in transcript order:
  - a `check_run` wake event (a user-side record, JSON carrying `conclusion`),
  - a `get_check_runs` result (`pull_request_read`).
A failing conclusion is `failure`, `timed_out` or `startup_failure`. `success`,
`skipped`, `neutral`, `cancelled` and an unfinished run (no conclusion) are not.
A `get_check_runs` result replaces the PR's earlier evidence only when it holds
a parsed `check_runs` array that is non-empty and whose length equals
`total_count`; an error, an empty list or a paginated page merges instead.
Wake events seen before the PR is registered are kept and attributed once it is.

A failure is acted on when, after the evidence, the transcript shows a
`git push` (or an MCP file write) that was not rejected or a dry run,
`update_pull_request_branch` or an `add_issue_comment` on that PR,
`gh pr comment` on it, or a later reading in which the check no longer fails.
The warning repeats every turn until then; that is intended.

A PR is dropped when the session ran `gh pr merge` / `gh pr close` on it,
`merge_pull_request`, or `update_pull_request` with `state` closed.

Not fired for a bot-review check (`review / claude-review`, `require-review`,
`require-clean-verdict`) whose name or output title/summary says quota, session
limit or did not finish: nothing in the PR can fix that.

Deliberate limits:
  - Transcript only, no network. A failure the session never saw is not seen.
  - PRs are keyed by number alone, so the same number in two repositories
    shares one state.
  - Any push counts as acting on every PR, because the push does not name one.
  - Warns, never blocks. A missing transcript is silent; any other error prints
    one line to stderr and exits 0.
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
GH_CREATE = re.compile(r"\s*gh\s+pr\s+create\b")
PR_KEYS = ("pullNumber", "pull_number", "prNumber", "pr_number", "number")
MCP_PUSH = re.compile(r"(push_files|create_or_update_file)$")
REJECTED = re.compile(r"\[rejected\]|error:")
# Fallback for a wake event that is not JSON: one name and one conclusion, on
# one line, so it cannot span two events.
TEXT_RUN = re.compile(
    r"check_run.*?name\W+([^\n,\"']+).*?conclusion\W+"
    r"(failure|timed_out|startup_failure|success|skipped|neutral|cancelled)",
    re.I)

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


def gh_pr_number(words, verb):
    """PR number of `gh pr <verb> N-or-URL`, or None when the line has no such call."""
    for i in range(len(words) - 2):
        if words[i:i + 3] == ["gh", "pr", verb]:
            for word in words[i + 3:]:
                if PR_URL.search(word):
                    return int(PR_URL.search(word).group(1))
                if word.isdigit():
                    return int(word)
    return None


def is_push(command):
    """A `git [options] push` that is not a dry run."""
    words = bash_words(command)
    for i, word in enumerate(words):
        if word == "git":
            rest = words[i + 1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
            if rest and rest[0] == "push":
                return not any(w in ("--dry-run", "-n") for w in rest[1:])
    return False


def unfixable(run):
    """A bot-review check whose own name and title/summary say nothing can fix it."""
    if not BOT_REVIEW.search(str(run.get("name"))):
        return False
    parts = [run.get("title"), run.get("summary")]
    output = run.get("output")
    if isinstance(output, dict):
        parts += [output.get("title"), output.get("summary")]
    return bool(UNFIXABLE.search(" ".join(p for p in parts if isinstance(p, str))))


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


def scan(path):
    state = State()
    uses = {}      # tool_use id -> (name, input)
    pending = {}   # tool_use id -> record index of a push awaiting its result
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
                if note_action(state, name, tool_input, index):
                    pending[block.get("id")] = index
            elif kind == "tool_result":
                ident = block.get("tool_use_id")
                name, tool_input = uses.get(ident, ("", None))
                text = text_of(block.get("content"))
                if ident in pending and not (
                        block.get("is_error") or REJECTED.search(text)):
                    state.pushes.append(pending[ident])
                note_result(state, name, tool_input, text, index)
            elif kind == "text" and record.get("type") == "user":
                if not (record.get("isMeta") and record.get("sourceToolUseID")):
                    note_wake(state, block.get("text") or "", index)
    return state


def note_action(state, name, tool_input, index):
    """Record an action; return True for a push whose result decides if it counts."""
    if name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if not isinstance(command, str):
            return False
        words = bash_words(command)
        for verb in ("merge", "close"):
            pr = gh_pr_number(words, verb)
            if pr:
                state.dropped.add(pr)
        pr = gh_pr_number(words, "comment")
        if pr:
            state.actions.setdefault(pr, []).append(index)
        return is_push(command)
    if MCP_PUSH.search(name):
        return True
    if name.endswith(("update_pull_request_branch", "add_issue_comment")):
        pr = issue_number(tool_input)
        if pr:
            state.actions.setdefault(pr, []).append(index)
    elif name.endswith("merge_pull_request"):
        pr = number_from_input(tool_input)
        if pr:
            state.dropped.add(pr)
    elif name.endswith("update_pull_request") and isinstance(tool_input, dict) \
            and str(tool_input.get("state")).lower() == "closed":
        pr = number_from_input(tool_input)
        if pr:
            state.dropped.add(pr)
    return False


def created_number(name, tool_input, text):
    """The PR a create call returned, or None. Only that call's own result counts."""
    if name.endswith("create_pull_request"):
        for value in decoded(text):
            if isinstance(value, dict) and isinstance(value.get("number"), int):
                return value["number"]
        match = PR_URL.search(text)
        return int(match.group(1)) if match else None
    if name == "Bash" and isinstance(tool_input, dict) \
            and GH_CREATE.match(str(tool_input.get("command"))):
        urls = PR_URL.findall(text)
        return int(urls[-1]) if urls else None
    return None


def is_full_listing(values):
    """A parsed check_runs array, non-empty, whose length is total_count."""
    for value in values:
        runs = value.get("check_runs") if isinstance(value, dict) else None
        if isinstance(runs, list) and runs and value.get("total_count") == len(runs):
            return True
    return False


def note_result(state, name, tool_input, text, index):
    number = created_number(name, tool_input, text)
    if number:
        state.own.add(number)
        return
    if name.endswith("pull_request_read") and isinstance(tool_input, dict) \
            and tool_input.get("method") == "get_check_runs":
        pr = number_from_input(tool_input)
        if pr:
            values = list(decoded(text))
            runs = [r for v in values for r in check_runs(v)]
            state.evidence(pr, runs, index, complete=is_full_listing(values))


def note_wake(state, text, index):
    """Fold check_run wake events into per-PR evidence, owned or not yet."""
    if "check_run" not in text:
        return
    found = False
    for value in decoded(text):
        runs, prs = list(check_runs(value)), set(pr_numbers(value))
        found = found or bool(runs)
        for pr in prs if runs else ():
            state.evidence(pr, runs, index, complete=False)
    if found:
        return
    for line in text.splitlines():
        match = TEXT_RUN.search(line)
        if not match:
            continue
        run = {"name": match.group(1).strip(), "conclusion": match.group(2).lower()}
        for a, b, c in PR_REF.findall(line):
            state.evidence(int(a or b or c), [run], index, complete=False)


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") if isinstance(payload, dict) else None
        if not isinstance(path, str) or not os.path.exists(path):
            return 0
        found = scan(path).unacted()
    except Exception as exc:  # fail open, but say so: a silent guard looks like a clean run
        sys.stderr.write(
            f"warn-red-own-pr-at-stop: skipped ({type(exc).__name__}: {exc})\n")
        return 0
    if not found:
        return 0
    prs = ", ".join(f"#{pr}" for pr in found)
    detail = "; ".join(f"#{pr}: {', '.join(names)}" for pr, names in found.items())
    print(json.dumps({"systemMessage": NOTE.format(prs=prs, detail=detail)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
