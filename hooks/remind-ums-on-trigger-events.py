#!/usr/bin/env python3
"""Reminders that a UMS pass is owed at moments no admission or review marks.

ai-config#4480. The existing UMS triggers key on an admission, a read review,
a questioned claim, or a pause. Five more moments owe a pass, each with a
decidable signature; the rest (below) stay rules in run-ums-proactively.md.

  coordinator-note   UserPromptSubmit: a <coordinator-relay> whose reason is
                     not "spawn" carries a note that steers or corrects the
                     thread. The note is a colleague's correction, and it is
                     the same lesson for every thread the coordinator tells.
  needless-question  UserPromptSubmit: the user's whole message is a grant
                     ("daytb", "yes, do it", "your call", "rec?"). The thread
                     asked something it could have decided.
  ums-word           UserPromptSubmit: the user wrote the word "ums" (ai-config#5162).
                     The reminder is inject-only because no deny can decide
                     whether a lesson was persisted; a correction has no
                     lexical signature, so AGENTS.md carries that half.
  compaction         SessionStart (source compact): learnings held only in
                     the compacted context may be summarized away.
  revert             PreToolUse Bash running `git revert`, `git reset --hard`
                     or `git restore --source`: work was undone or redone.
  tool-error         PreToolUse, any tool (ai-config#5630): the transcript's
                     most recent tool result is an error (a non-zero exit, a
                     hook denial, an InputValidationError, an MCP error), so
                     this call is usually its revision. Ezra, 2026-11-13: "any
                     time you format a command incorrectly and need to revise
                     it, run ums?", then "in other words, any time a command
                     produces an error?". Inject-only, because a deny would
                     block the retry that fixes the error. EXPECTED_ERRORS
                     lists results that are not mistakes (a grep with no
                     match, a false test, a diff), EXPECT_FAIL a call marked
                     expect-fail, and USER_REJECTED a call the user declined.
                     Every error among parallel results counts.
  ci-failure         PreToolUse, any tool (ai-config#1100): the newest batch of
                     tool results holds a JSON check run, job or workflow run
                     whose newest run of that name ended failure, timed_out or
                     startup_failure (a run history's older failures do not
                     count, and a job's steps are not walked). Ezra:
                     "our goal is that all CI workflows pass (or skip, if
                     appropriate) on the first push; no failures". Inject-only,
                     once per transcript and set of failed check names.

Inject-only: every path prints context and exits 0. Fails OPEN and SILENT.
Each reminder fires once per distinct trigger text (sentinel in the temp dir).
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile

RELAY = re.compile(r"<relay\b([^>]*)>(.*?)</relay>", re.DOTALL)
NOTE = re.compile(r"<note>(.*?)</note>", re.DOTALL)
GRANT = re.compile(
    r"^\s*(?:daytb|dmmhyh|rec\??|do as you think best|do it|yes,? do it|yes,? go ahead"
    r"|your call|up to you|you decide|go ahead|just do it)\s*[.!]?\s*$",
    re.I,
)
REVERT = re.compile(r"\bgit\s+(?:revert|reset\s+--hard|restore\s+--source)\b")

# Errors that are not mistakes: (command regex, error-text regex) pairs. When
# both search-match the failed call's "command" input (empty for other tools)
# and its error text, the tool-error reminder is skipped. Ezra said "daytb" on
# which expected non-zero results to exempt (2026-11-13, ai-config#5630); edit
# this list to change the answer.
#
# Each command regex is matched against the LAST non-empty stage of the
# command (after the final unquoted &&, ||, ;, |, & or newline), because that
# stage sets the exit code: "cd r && grep x f" fails exactly when its grep
# finds nothing. last_stage() splits with shlex, so a quoted operator, as in
# rg "a|b" f, stays inside its stage. A heredoc body or a compound command
# ending in "done" or "fi" has no exempt last stage, so it is never exempted.
# EXPECT_FAIL is matched against the whole command instead, anchored to its
# start or its end, so the words inside a commit message do not count.
# grep -c prints a count of 0 (per file, "f:0") before exiting 1.
_EXIT_1_NO_MATCH = r"\A\s*Exit code 1(?:\s*\n\s*(?:\S+:)?0)*\s*\Z"
EXPECTED_ERRORS = (
    # A search that finds nothing: grep, rg or git grep, exit 1, no output.
    (r"\A\s*(?:git(?:\s+-C\s+\S+)?\s+grep|grep|egrep|fgrep|rg)\b", _EXIT_1_NO_MATCH),
    # A test whose answer is "no": test, [ or [[, exit 1.
    (r"\A\s*(?:test|\[\[?)\s", r"\A\s*Exit code 1\b"),
    # diff, cmp or git diff --exit-code reporting a difference: exit 1.
    (r"\A\s*(?:diff|cmp)\b|\A\s*git(?:\s+-C\s+\S+)?\s+diff\b.*--(?:exit-code|quiet)\b", r"\A\s*Exit code 1\b"),
)
# A command the agent marked as expected to fail: an EXPECT_FAIL=1 prefix or
# a trailing "# expect-fail" comment.
EXPECT_FAIL = re.compile(r"\A\s*EXPECT_FAIL=1\s|#\s*expect(?:ed)?[- ]fail\s*\Z")
# The user declined the call: a decision, not a malformed command.
USER_REJECTED = re.compile(r"doesn't want to proceed|user rejected", re.I)
OPERATOR_CHARS = ";&|\n"

# Check-run and workflow-run conclusions that mean the check failed.
FAILED_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}

# Read only the end of a long transcript: the newest tool result is all we need.
TAIL_BYTES = 400_000

COMMON = (
    "Record the general rule in its global home in this turn (ai-config for agent rules, "
    "psw for prose rules, the repo's own instructions for repo-only rules), "
    "and name what you recorded in your reply. See run-ums-proactively.md."
)
BOTH_PLACES = (
    " Persist it in the same turn in BOTH the project memory store AND ai-config and/or the "
    "project repo (Ezra, 2026-11-09, ai-config#5162): every 'ums', every correction of you, "
    "and every correction you make to yourself."
)
UMS_WORD = re.compile(r"(?<![\w/:.-])ums(?![\w-])", re.I)
MESSAGES = {
    "coordinator-note": (
        "[hook: remind-ums-on-trigger-events] The coordinator session's note steers or corrects "
        "this thread. A correction given to one thread is a rule for all of them. " + COMMON
        + BOTH_PLACES
    ),
    "ums-word": (
        "[hook: remind-ums-on-trigger-events] The user wrote 'ums'. Run the pass now, before "
        "anything else." + BOTH_PLACES
    ),
    "needless-question": (
        "[hook: remind-ums-on-trigger-events] The user's reply is a grant ({quote!r}): the thread "
        "asked something it could have decided. Act on the answer, then record the decision rule "
        "that would have made the question unnecessary. " + COMMON
    ),
    "compaction": (
        "[hook: remind-ums-on-trigger-events] The context was just compacted. Learnings held only "
        "in the compacted context may be gone or reduced to a summary line. Run `ums` now over "
        "what the summary still shows (corrections, workarounds, convention failures) before "
        "continuing."
    ),
    "tool-error": (
        "[hook: remind-ums-on-trigger-events] The previous {tool} call returned an error "
        "({error!r}). Ezra, 2026-11-13: any command that produces an error owes a UMS pass. "
        "Once the revised call works, record what caused the error and the form that works, "
        "so the next session writes it right the first time. " + COMMON
    ),
    "ci-failure": (
        "[hook: remind-ums-on-trigger-events] The previous result shows a failed CI check ({checks}). "
        "The goal is that every CI workflow passes, or skips where appropriate, on the first push "
        "(ai-config#1100). Once you know the cause, record why the first push missed it and what "
        "local check would have caught it. " + COMMON
    ),
    "revert": (
        "[hook: remind-ums-on-trigger-events] This command reverts or redoes work. Once it runs, "
        "ask what decision or check would have prevented the first attempt, and record that. "
        + COMMON
    ),
}


def first_time(kind, text):
    key = hashlib.sha256(f"{kind}:{text}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ums-trigger-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("1")
    except OSError:
        pass
    return True


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return ""


def newest_batch(transcript_path):
    """[(tool_use_id, tool name, input, result text, is_error)] for the newest batch of results.

    Parallel calls return several results, so the newest batch is every result
    whose call belongs to the last group of calls that has any result yet. A
    call still pending (the one this hook is running for) starts a group with
    no results and is skipped.
    """
    with open(transcript_path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - TAIL_BYTES))
        lines = fh.read().decode("utf-8", errors="replace").splitlines()
    uses = {}
    group_of = {}
    group = 0
    seen_result = False
    results = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = (entry.get("message") or {}).get("content") if isinstance(entry, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                if seen_result:
                    group += 1
                    seen_result = False
                uses[block.get("id")] = (block.get("name"), block.get("input"))
                group_of[block.get("id")] = group
            elif block.get("type") == "tool_result":
                seen_result = True
                results.append(block)
    # A result whose call fell before the tail has no group, so it cannot be
    # placed in time; leave it out rather than count an old error as new.
    results = [r for r in results if r.get("tool_use_id") in group_of]
    if not results:
        return []
    newest = max(group_of[r.get("tool_use_id")] for r in results)
    batch = []
    for res in results:
        use_id = res.get("tool_use_id")
        if group_of[use_id] != newest:
            continue
        name, inp = uses.get(use_id, ("a tool", None))
        batch.append((use_id, name, inp, _text(res.get("content")), bool(res.get("is_error"))))
    return batch


def json_values(text):
    """Every JSON object or array that starts a line of text, decoded.

    A tool result can carry stderr after its JSON, a line before it, one value
    per line (gh --jq '.[]'), or pages printed back to back (gh api --paginate
    without --slurp), so the whole text is not one JSON value. Prose that only
    quotes JSON mid-line yields nothing.
    """
    decoder = json.JSONDecoder()
    values = []
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i < n and text[i] in "{[":
            try:
                value, i = decoder.raw_decode(text, i)
                values.append(value)
                continue
            except ValueError:
                pass
        newline = text.find("\n", i)
        if newline < 0:
            break
        i = newline + 1
    return values


def _run_order(run):
    """Sort key putting the newest run of a name last (created or started time, then run number, then id)."""
    stamp = run.get("created_at") or run.get("started_at") or run.get("completed_at") or ""
    number = run.get("run_number") if isinstance(run.get("run_number"), int) else 0
    ident = run.get("id") if isinstance(run.get("id"), int) else 0
    return (str(stamp), number, ident)


def failed_checks(text):
    """Names of the check runs, jobs or workflow runs whose NEWEST run failed, in a JSON tool result.

    The shape is the one pull_request_read get_check_runs, actions_get and
    gh api return: an object with "name", "status" and "conclusion" (checked on
    ai-config#5631). A run history lists old runs too, so only the newest run
    of each name counts: a failure already followed by a pass does not fire.
    A job's "steps" are not walked, since a failed step is reported by its job.
    """
    newest = {}
    stack = json_values(text)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            name = node.get("name")
            if "conclusion" in node and "status" in node and isinstance(name, str) and name:
                if name not in newest or _run_order(node) >= _run_order(newest[name]):
                    newest[name] = node
            stack.extend(v for k, v in node.items() if k != "steps")
        elif isinstance(node, list):
            stack.extend(node)
    return [name for name, run in newest.items() if run.get("conclusion") in FAILED_CONCLUSIONS]


def last_stage(command):
    """The last non-empty stage of a shell command, split on unquoted operators (2>&1 lexes as ">&", no break).

    On unbalanced quotes shlex raises, and the whole command is the stage.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=OPERATOR_CHARS + "<>")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return command.strip()
    stages = [[]]
    for tok in tokens:
        if set(tok) <= set(OPERATOR_CHARS):
            stages.append([])
        else:
            stages[-1].append(tok)
    nonempty = [stage for stage in stages if stage]
    return " ".join(nonempty[-1]) if nonempty else ""


def is_expected(inp, error):
    """True when an error result is not a mistake (EXPECTED_ERRORS, EXPECT_FAIL, a user rejection)."""
    if USER_REJECTED.search(error):
        return True
    command = str(inp.get("command") or "") if isinstance(inp, dict) else json.dumps(inp or "")
    if EXPECT_FAIL.search(command):
        return True
    stage = last_stage(command)
    return any(re.search(cmd_re, stage) and re.search(err_re, error) for cmd_re, err_re in EXPECTED_ERRORS)


def ci_failure_reminder(path, batch):
    """The ci-failure reminder for the newest batch of results, or None. Error results are skipped."""
    names = []
    for _use_id, _name, _inp, text, is_error in batch:
        if is_error:
            continue
        names.extend(failed_checks(text))
    names = sorted(set(names))
    if not names or not first_time("ci-failure", f"{path}:{names}"):
        return None
    return MESSAGES["ci-failure"].format(checks=", ".join(names)[:200])


def tool_error_reminder(path, batch):
    """The tool-error reminders for the newest batch of results, or None."""
    notes = []
    for use_id, name, inp, error, is_error in batch:
        if not is_error:
            continue
        if is_expected(inp, error) or not first_time("tool-error", f"{path}:{use_id}"):
            continue
        # "Exit code N" alone says nothing about the cause, so quote the next line too.
        shown = [ln.strip() for ln in error.splitlines() if ln.strip()][:2] or ["error"]
        if not shown[0].startswith("Exit code"):
            shown = shown[:1]
        notes.append(MESSAGES["tool-error"].format(tool=name, error=": ".join(shown)[:200]))
    return "\n\n".join(notes) or None


def coordinator_note(prompt):
    for attrs, body in RELAY.findall(prompt):
        if 'reason="spawn"' in attrs:
            continue
        note = NOTE.search(body)
        if note and note.group(1).strip():
            return note.group(1).strip()
    return None


def main() -> int:
    # A prompt or a relayed coordinator note can hold curly quotes, which a
    # cp1252 console can neither read from a UTF-8 payload nor write for a
    # UTF-8 reader (ai-config#5462). Read stdin and write stdout as UTF-8
    # whatever the console says.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        event = payload.get("hook_event_name")
        if event == "SessionStart":
            if payload.get("source") == "compact" and first_time("compaction", str(payload.get("session_id"))):
                print(MESSAGES["compaction"])
            return 0
        if event == "PreToolUse":
            inp = payload.get("tool_input")
            cmd = str(inp.get("command") or "") if isinstance(inp, dict) else ""
            notes = []
            if REVERT.search(cmd) and first_time("revert", cmd):
                notes.append(MESSAGES["revert"])
            path = payload.get("transcript_path")
            if isinstance(path, str) and os.path.isfile(path):
                # One read of the transcript tail feeds both reminders.
                batch = newest_batch(path)
                for note in (tool_error_reminder(path, batch), ci_failure_reminder(path, batch)):
                    if note:
                        notes.append(note)
            if notes:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "\n\n".join(notes),
                }}))
            return 0
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            return 0
        note = coordinator_note(prompt)
        if note and first_time("coordinator-note", note):
            print(MESSAGES["coordinator-note"])
        elif GRANT.match(prompt) and first_time("needless-question", prompt + str(payload.get("transcript_path"))):
            print(MESSAGES["needless-question"].format(quote=prompt.strip()))
        elif UMS_WORD.search(prompt) and first_time("ums-word", prompt):
            print(MESSAGES["ums-word"])
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
