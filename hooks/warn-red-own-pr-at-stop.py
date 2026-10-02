#!/usr/bin/env python3
"""Stop warn: a PR this session opened still shows failing checks nobody acted on.

The rule "fix red CI on your own PRs unprompted" lives in the PR-driving rules,
and nothing fired at turn end, so a turn could end over a red PR and the person
had to ask "fix failing CI?" (twice in one day). This hook checks the one thing
that is decidable from the transcript. It is a warning: a Stop hook that emits
only `systemMessage` cannot block the stop.

Own PRs: numbers returned by a successful `create_pull_request` call, or by a
successful Bash command with a `gh pr create` segment (at the start of the line
or after `;`, `&&`, `||`, `|` or `cd x &&`, with optional `VAR=value` prefixes).
Only the `/pull/N` URL of that result counts. A failed create that prints an
existing PR's URL is not adopted, and subscribing to a PR does not make it ours.

Latest status evidence per PR, in transcript order:
  - a `check_run` wake event (a user-side record, JSON carrying `conclusion`),
  - a `get_check_runs` result (`pull_request_read`).
A failing conclusion is `failure`, `timed_out` or `startup_failure`. `success`,
`skipped`, `neutral`, `cancelled` and an unfinished run (no conclusion) are not.
Evidence is keyed by check name and head SHA where the event carries one: a
success clears the same name on the same head or an older one, never a newer
head, so a late success for an old head cannot hide a failure on the current one.
A `get_check_runs` result replaces the PR's earlier evidence only when it holds
a parsed `check_runs` array that is non-empty and whose length equals
`total_count`; an error, an empty list or a paginated page merges instead.
Wake events seen before the PR is registered are kept and attributed once it is.

A failure is acted on when, after the evidence, the transcript shows an action
that had an effect: a `git push` (or an MCP file write) that updated a branch,
`update_pull_request_branch` or an `add_issue_comment` on that PR, or
`gh pr comment` on it, or a later reading in which the check no longer fails.
Not effective: a call that errored, a rejected push, `Everything up-to-date`, a
`--dry-run`, a branch-delete push, or a push to a remote given as a URL.
The warning repeats every turn until then; that is intended.

A PR is dropped when a successful `gh pr merge` / `gh pr close`,
`merge_pull_request`, or `update_pull_request` with `state` closed names it. A
blocked or failed one does not drop it.

Exempt: a check whose name matches `claude-review`, `require-review` or
`require-clean-verdict` AND whose title or summary says quota, session limit or
did not finish, since nothing in the PR can fix that. A failing check with any
other name warns whatever its text says.

Deliberate limits:
  - Transcript only, no network. A failure the session never saw is not seen.
    The wake-event shape is a guess: no real sample was available (see the test).
  - PRs are keyed by number alone, so the same number in two repositories
    shares one state.
  - A push names no PR, so any effective push acts on every PR, and a push made
    from another checkout (`cd other && git push`) is not told apart.
  - A quoted `gh pr create` inside a string argument can be read as a call.
  - Failure detection of a tool result is by its `is_error` flag or an
    `Exit code`/`Error`/`failed` opening, so an odd error shape reads as success.
  - A record that cannot be processed is skipped and counted on stderr; the rest
    of the transcript is still read. At most 64 unparseable braces are tried per
    string, to stay linear.
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
GH_CREATE = re.compile(
    r"(?:^|[;&|(\n])\s*(?:[A-Za-z_]\w*=\S*\s+)*gh\s+pr\s+create\b")
PR_KEYS = ("pullNumber", "pull_number", "prNumber", "pr_number", "number")
MCP_PUSH = re.compile(r"(push_files|create_or_update_file)$")
# A rejected push. `error:` alone would also match prose (a hook's "error: 0").
REJECTED = re.compile(
    r"\[(?:remote )?rejected\]|^error: failed to push|^fatal: |^remote: error:",
    re.I | re.M)
UP_TO_DATE = re.compile(r"Everything up-to-date", re.I)
FAILED_RESULT = re.compile(r"\s*(?:exit code [1-9]|error\b|failed\b)", re.I)
URL_REMOTE = re.compile(r"://|^[\w.-]+@[\w.-]+:")
MAX_BRACE_TRIES = 64
# Fallback for a wake event that is not JSON: one name and one conclusion, on
# one line, so it cannot span two events.
TEXT_RUN = re.compile(
    r"check_run.*?name\W+([^\n,\"']+).*?conclusion\W+"
    r"(failure|timed_out|startup_failure|success|skipped|neutral|cancelled)",
    re.I)

NOTE = (
    "[hook: warn-red-own-pr-at-stop] PR {prs} opened in this session still "
    "shows failing checks that nothing since has acted on: {detail}. This note "
    "does not block the stop; fix it, or comment once why it is not this PR's."
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
    """Every JSON object or array found in a string (whole, or from a brace).

    Linear in the text: after MAX_BRACE_TRIES braces that do not parse it stops.
    """
    try:
        yield json.loads(text)
        return
    except ValueError:
        pass
    decoder, pos, misses = json.JSONDecoder(), 0, 0
    while misses < MAX_BRACE_TRIES:
        found = [p for p in (text.find("{", pos), text.find("[", pos)) if p >= 0]
        if not found:
            return
        pos = min(found)
        try:
            value, end = decoder.raw_decode(text, pos)
        except ValueError:
            misses += 1
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


def ascii_number(value):
    """int(value) for an int or an ASCII-digit string, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


def number_from_input(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in PR_KEYS:
        number = ascii_number(tool_input.get(key))
        if number is not None:
            return number
    for value in tool_input.values():
        if isinstance(value, str) and PR_URL.search(value):
            return int(PR_URL.search(value).group(1))
    return None


def issue_number(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in ("issue_number", "issueNumber", "pullNumber", "pull_number", "number"):
        number = ascii_number(tool_input.get(key))
        if number is not None:
            return number
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
                number = ascii_number(word)
                if number is not None:
                    return number
    return None


def is_push(command):
    """A `git [options] push` that can update a branch of this repository."""
    words = bash_words(command)
    for i, word in enumerate(words):
        if word != "git":
            continue
        rest = words[i + 1:]
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        if not rest or rest[0] != "push":
            continue
        args = rest[1:]
        if any(w in ("--dry-run", "-n", "--delete", "-d") for w in args):
            return False
        positional = [w for w in args if not w.startswith("-")]
        if any(w.startswith(":") for w in positional):
            return False
        if positional and URL_REMOTE.search(positional[0]):
            return False
        return True
    return False


def failed(block, text):
    """True for a tool result that reports an error."""
    return bool(block.get("is_error")) or bool(FAILED_RESULT.match(text))


def push_effective(text):
    return not (REJECTED.search(text) or UP_TO_DATE.search(text))


def conclusion_of(run):
    value = run.get("conclusion")
    return value.lower() if isinstance(value, str) else None


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
        self.failing = {}   # pr -> {(check name, head sha or None): evidence index}
        self.heads = {}     # pr -> head shas in first-seen order
        self.actions = {}   # pr -> [record index]
        self.pushes = []    # record indexes; a push names no PR
        self.dropped = set()

    def rank(self, pr, sha):
        order = self.heads.get(pr, [])
        return order.index(sha) if sha in order else -1

    def supersedes(self, pr, sha, other):
        """Does a success on `sha` settle a failure recorded for head `other`?"""
        return sha is None or other is None or sha == other or \
            self.rank(pr, other) < self.rank(pr, sha)

    def evidence(self, pr, runs, index, complete):
        """Fold check runs into a PR's state. A complete listing replaces it."""
        mine = self.failing.setdefault(pr, {})
        order = self.heads.setdefault(pr, [])
        for run in runs:
            sha = run.get("head_sha") if isinstance(run.get("head_sha"), str) else None
            if sha and sha not in order:
                order.append(sha)
        if complete:
            shas = [r.get("head_sha") for r in runs if isinstance(r.get("head_sha"), str)]
            top = max(shas, key=lambda s: self.rank(pr, s)) if shas else None
            for key in [k for k in mine if self.supersedes(pr, top, k[1])]:
                del mine[key]
        for run in runs:
            name = str(run.get("name"))
            sha = run.get("head_sha") if isinstance(run.get("head_sha"), str) else None
            conclusion = conclusion_of(run)
            if conclusion in FAILING and not unfixable(run):
                mine[(name, sha)] = index
            elif conclusion is not None:
                for key in [k for k in mine
                            if k[0] == name and self.supersedes(pr, sha, k[1])]:
                    del mine[key]

    def unacted(self):
        found = {}
        for pr in sorted(self.own - self.dropped):
            later = self.actions.get(pr, []) + self.pushes
            names = sorted({name for (name, _), i in self.failing.get(pr, {}).items()
                            if not any(a > i for a in later)})
            if names:
                found[pr] = names
        return found


def scan(path):
    """Read the transcript. Returns (state, number of records skipped)."""
    state = State()
    uses = {}      # tool_use id -> (name, input)
    pending = {}   # tool_use id -> [(kind, pr, record index)] effects awaiting a result
    skipped = 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    for index, line in enumerate(lines):
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            for block in blocks(record):
                handle_block(state, uses, pending, record, block, index)
        except ValueError:
            continue  # not JSON: not a record
        except Exception:  # RecursionError, a odd shape: skip this record only
            skipped += 1
    return state, skipped


def handle_block(state, uses, pending, record, block, index):
    kind = block.get("type")
    if kind == "tool_use":
        name = str(block.get("name") or "")
        tool_input = block.get("input")
        uses[block.get("id")] = (name, tool_input)
        effects = effects_of(name, tool_input, index)
        if effects:
            pending[block.get("id")] = effects
    elif kind == "tool_result":
        ident = block.get("tool_use_id")
        name, tool_input = uses.get(ident, ("", None))
        text = text_of(block.get("content"))
        bad = failed(block, text)
        if not bad:
            for effect in pending.get(ident, []):
                apply_effect(state, effect, text)
        if not bad:
            note_result(state, name, tool_input, text, index)
    elif kind == "text" and record.get("type") == "user":
        if not (record.get("isMeta") and record.get("sourceToolUseID")):
            note_wake(state, block.get("text") or "", index)


def effects_of(name, tool_input, index):
    """Effects a tool call has IF its result is not an error: (kind, pr, index)."""
    effects = []
    if name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if not isinstance(command, str):
            return effects
        words = bash_words(command)
        for verb in ("merge", "close"):
            pr = gh_pr_number(words, verb)
            if pr is not None:
                effects.append(("drop", pr, index))
        pr = gh_pr_number(words, "comment")
        if pr is not None:
            effects.append(("action", pr, index))
        if is_push(command):
            effects.append(("push", None, index))
    elif MCP_PUSH.search(name):
        effects.append(("push", None, index))
    elif name.endswith(("update_pull_request_branch", "add_issue_comment")):
        pr = issue_number(tool_input)
        if pr is not None:
            effects.append(("action", pr, index))
    elif name.endswith("merge_pull_request"):
        pr = number_from_input(tool_input)
        if pr is not None:
            effects.append(("drop", pr, index))
    elif name.endswith("update_pull_request") and isinstance(tool_input, dict) \
            and str(tool_input.get("state")).lower() == "closed":
        pr = number_from_input(tool_input)
        if pr is not None:
            effects.append(("drop", pr, index))
    return effects


def apply_effect(state, effect, text):
    kind, pr, index = effect
    if kind == "drop":
        state.dropped.add(pr)
    elif kind == "action":
        state.actions.setdefault(pr, []).append(index)
    elif kind == "push" and push_effective(text):
        state.pushes.append(index)


def created_number(name, tool_input, text):
    """The PR a create call returned, or None. Only that call's own result counts."""
    if name.endswith("create_pull_request"):
        for value in decoded(text):
            if isinstance(value, dict) and isinstance(value.get("number"), int):
                return value["number"]
        match = PR_URL.search(text)
        return int(match.group(1)) if match else None
    if name == "Bash" and isinstance(tool_input, dict) \
            and GH_CREATE.search(str(tool_input.get("command"))):
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
        if pr is not None:
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
    skipped = 0
    try:
        try:
            payload = json.load(sys.stdin)
        except ValueError:
            return 0  # stdin is not a hook payload: nothing to scan, nothing to report
        path = payload.get("transcript_path") if isinstance(payload, dict) else None
        if not isinstance(path, str) or not os.path.exists(path):
            return 0
        state, skipped = scan(path)
        found = state.unacted()
    except Exception as exc:  # fail open, but say so: a silent guard looks like a clean run
        sys.stderr.write(
            f"warn-red-own-pr-at-stop: skipped ({type(exc).__name__}: {exc})\n")
        return 0
    if skipped:
        sys.stderr.write(
            f"warn-red-own-pr-at-stop: skipped {skipped} unreadable record(s)\n")
    if not found:
        return 0
    prs = ", ".join(f"#{pr}" for pr in found)
    detail = "; ".join(f"#{pr}: {', '.join(names)}" for pr, names in found.items())
    print(json.dumps({"systemMessage": NOTE.format(prs=prs, detail=detail)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
