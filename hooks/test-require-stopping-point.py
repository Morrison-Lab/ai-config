import json
import os
import subprocess
import sys
import tempfile

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(__file__), "require-stopping-point.py")
)


def _has_warning(stdout: str) -> bool:
    if not stdout.strip():
        return False
    data = json.loads(stdout)
    assert not (data.get("decision") == "block" or "reason" in data), (
        f"Hook emitted blocking decision or reason: {stdout}"
    )
    return "systemMessage" in data and bool(data.get("systemMessage"))


def run(text, tmpdir=None, raw_lines=None, key_name="transcript_path"):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if raw_lines is not None:
            for l in raw_lines:
                f.write(l + "\n")
        else:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "text", "text": text}]},
                    }
                )
                + "\n"
            )
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({key_name: path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


def run_direct_payload(payload, env=None, tmpdir=None):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    base_env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    if env:
        base_env.update(env)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=base_env,
    )
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


def reply_transcript(reply_text, narration_text=None):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        blocks = []
        if narration_text:
            blocks.append({"type": "text", "text": narration_text})
        blocks.append(
            {
                "type": "tool_use",
                "name": "mcp__hearthbot__reply",
                "input": {"text": reply_text},
            }
        )
        f.write(
            json.dumps({"type": "assistant", "message": {"content": blocks}})
            + "\n"
        )
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


cases = [
    ("Completed the checks.", True),
    ("Completed the checks.\n\n**Stopping Point**: Clean stopping point reached.", True),
    ("Completed the checks.\n\n**Stopping Point**: Clean stopping point reached --- session done.", False),
    ("Completed the task.\n\n- **Stopping Point**: Clean stopping point reached --- session done.", False),
    ("Indented list:\n  - **Stopping Point**: Clean stopping point reached --- session done.", False),
    ("Colon inside bold:\n**Stopping Point:** Clean stopping point reached --- session done.", False),
    ("### Stopping Point: Clean stopping point reached --- session done.", False),
    ("**Stopping Point**: Not a clean stopping point / work remains queued: finish X.", True),
    ("**Stopping Point**: Not a clean stopping point / work remains queued: session not done; finish X.", False),
    ("**Stopping Point**: Not clean --- CI is still running.", True),
    ("**Stopping Point**: Not clean --- session not done; CI is still running.", False),
    ("**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending.", False),
    ("**Stopping Point**: Not a clean stopping point / work remains queued: session not done; PR #123 is waiting on CI.", False),
    ("**Stopping Point**: Clean stopping point reached.\n\nThe session is done; UMS was run and all follow-ups are filed.", False),
    ("**Stopping Point**: Not a clean stopping point / work remains queued:\n\nSession not done; PR #4136 is waiting on CI.", False),
    ("**Stopping Point**: Clean stopping point reached.\n\n## Next Steps\nSession done.", True),
    ("**Stopping Point**: Clean stopping point reached.\n\n- Next item: session done.", True),
    ("**Stopping Point**: Clean stopping point reached.\n\n* Next item: session done.", True),
    ("**Stopping Point**: Clean stopping point reached.\n\n+ Next item: session done.", True),
    ("**Stopping Point**: Clean stopping point reached.\n\n1. Next item: session done.", True),
    ("This PR adds a hook that requires text like `**Stopping Point**: Clean stopping point reached --- session done` in every final reply.", True),
    ("Discussion of rule:\n```\n**Stopping Point**: Clean stopping point reached --- session done\n```\nStill working on task.", True),
    ("Discussion of rule:\n```markdown\n**Stopping Point**: Clean stopping point reached --- session done\n```\nDone with task.\n\n**Stopping Point**: Clean stopping point reached --- session done.", False),
    ("**Stopping Point**: Cleanup pending, more work needed.", True),
    ("To open a fence type ``` on its own line.\n\n**Stopping Point**: Clean stopping point reached --- session done\n\n```\ncode\n```", False),
    ("Don't write a bare declaration like this:\n```\n**Stopping Point**: Clean stopping point reached --- session done\n```\nI have not actually finished; more work remains.\n\nAlso, here's a separate unrelated snippet I was about to show:\n```\n", True),
    ("```\n**Stopping Point**: Clean stopping point reached --- session done\n```\n```\n", True),
    # ai-config#3748: unterminated fence must not swallow subsequent declaration
    ("Snippet below:\n```python\nprint(1)\n\n**Stopping Point**: Clean stopping point reached --- session done.", False),
    # ai-config#3748: 4-backtick fence wrapping 3-backtick fence
    ("Code sample:\n````markdown\n```\n**Stopping Point**: Clean stopping point reached --- session done\n```\n````\nStill working.", True),
]

failed = 0
for text, expected in cases:
    got = run(text)
    status = "PASS" if got == expected else "FAIL"
    print(status, repr(text.splitlines()[0]))
    if got != expected:
        failed += 1

# Test per-line transcript error resilience (blank/malformed lines before assistant reply)
raw = [
    "",
    "malformed json {",
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Completed the checks. No declaration here."}]}}),
]
got_resilient = run("", raw_lines=raw)
if not got_resilient:
    print("FAIL per-line transcript resilience (did not block when declaration was missing)")
    failed += 1
else:
    print("PASS per-line transcript resilience on malformed lines")

# Test fail-safe / sentinel retry on identical text
tmp = tempfile.mkdtemp()
blocked_first = run("Missing stopping point.", tmpdir=tmp)
blocked_second = run("Missing stopping point.", tmpdir=tmp)
if not (blocked_first is True and blocked_second is False):
    print("FAIL sentinel retry behavior")
    failed += 1
else:
    print("PASS sentinel retry allows next attempt")

# Alternative transcript payload keys
for key in ("transcriptPath", "transcript", "history_file"):
    got = run("Missing declaration.", key_name=key)
    if got:
        print(f"PASS payload key '{key}' resolves transcript correctly")
    else:
        print(f"FAIL payload key '{key}' failed to trigger block")
        failed += 1

# Reply-tool visibility tests (ai-config#3798 / #3804)
CLEAN_DECL = "**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending."
MISSING_DECL = "Completed the task successfully without a stopping point."

if reply_transcript(CLEAN_DECL):
    print("FAIL: reply-tool payload with clean stopping point blocked")
    failed += 1
else:
    print("PASS: reply-tool payload with clean stopping point passes")

if not reply_transcript(MISSING_DECL):
    print("FAIL: reply-tool payload missing stopping point did not block")
    failed += 1
else:
    print("PASS: reply-tool payload missing stopping point blocks")

if reply_transcript(CLEAN_DECL, narration_text=MISSING_DECL):
    print("FAIL: clean reply-tool payload blocked when narration lacked stopping point")
    failed += 1
else:
    print("PASS: delivered clean reply-tool wins over narration missing stopping point")

if not reply_transcript(MISSING_DECL, narration_text=CLEAN_DECL):
    print("FAIL: reply-tool missing stopping point did not block when narration had clean declaration")
    failed += 1
else:
    print("PASS: undelivered narration with stopping point does not save missing reply-tool declaration")

# Direct payload tests
direct_cases = [
    ({"reply": CLEAN_DECL}, False, "direct reply field with clean stopping point passes"),
    ({"reply": MISSING_DECL}, True, "direct reply field missing stopping point blocks"),
    ({"last_assistant_message": CLEAN_DECL}, False, "direct last_assistant_message field passes"),
    ({"last_assistant_message": MISSING_DECL}, True, "direct last_assistant_message field missing blocks"),
    (
        {"message": {"content": [{"type": "text", "text": CLEAN_DECL}]}},
        False,
        "direct message object with text passes",
    ),
    (
        {"message": {"content": [{"type": "text", "text": MISSING_DECL}]}},
        True,
        "direct message object with missing text blocks",
    ),
    (
        {
            "message": {
                "content": [
                    {"type": "text", "text": MISSING_DECL},
                    {"type": "tool_use", "name": "mcp__hearthbot__reply", "input": {"text": CLEAN_DECL}},
                ]
            }
        },
        False,
        "direct message narration missing + clean reply-tool passes",
    ),
    (
        {
            "message": {
                "content": [
                    {"type": "text", "text": CLEAN_DECL},
                    {"type": "tool_use", "name": "mcp__hearthbot__reply", "input": {"text": MISSING_DECL}},
                ]
            }
        },
        True,
        "direct message narration clean + missing reply-tool blocks",
    ),
]

for payload, expected, label in direct_cases:
    got = run_direct_payload(payload)
    if got == expected:
        print(f"PASS {label}")
    else:
        print(f"FAIL {label} (expected block={expected}, got {got})")
        failed += 1

def multi_turn_transcript(turn1_reply, turn2_text):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "do turn 1"}}) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "mcp__hearthbot__reply",
                "input": {"text": turn1_reply},
            }]},
        }) + "\n")
        f.write(json.dumps({"type": "user", "message": {"content": "do turn 2"}}) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": turn2_text}]},
        }) + "\n")
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)

# Multi-turn test: turn 1 reply-tool state must not leak into turn 2 plain-text
if not multi_turn_transcript(CLEAN_DECL, MISSING_DECL):
    print("FAIL: turn 2 plain-text missing stopping point did not warn after turn 1 used reply-tool")
    failed += 1
else:
    print("PASS: turn 2 plain-text missing stopping point warns after turn 1 reply-tool")

if multi_turn_transcript(MISSING_DECL, CLEAN_DECL):
    print("FAIL: turn 2 plain-text clean stopping point warned because turn 1 reply-tool lacked declaration")
    failed += 1
else:
    print("PASS: turn 2 plain-text clean stopping point passes despite turn 1 reply-tool lacking declaration")


def tool_result_transcript(reply_text):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "do task"}}) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "mcp__hearthbot__reply",
                "input": {"text": reply_text},
            }]},
        }) + "\n")
        f.write(json.dumps({
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "delivered"}]},
        }) + "\n")
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


if not tool_result_transcript(MISSING_DECL):
    print("FAIL: reply-tool followed by tool_result did not warn when declaration was missing")
    failed += 1
else:
    print("PASS: reply-tool followed by tool_result warns when declaration is missing")

if tool_result_transcript(CLEAN_DECL):
    print("FAIL: reply-tool followed by tool_result warned despite clean declaration")
    failed += 1
else:
    print("PASS: reply-tool followed by tool_result passes when declaration is present")


def meta_mid_turn_transcript(reply_text):
    """A loaded skill body arrives mid-turn as a `type: "user"` entry with
    `isMeta: true`, AFTER the reply-tool already delivered the final content
    and with no further reply-tool call afterward. It must not be treated as
    a new user turn -- doing so wipes the delivered reply the same way a real
    turn 2 legitimately would (ai-config#3860)."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "do task"}}) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "mcp__hearthbot__reply",
                "input": {"text": reply_text},
            }]},
        }) + "\n")
        f.write(json.dumps({
            "type": "user",
            "isMeta": True,
            "sourceToolUseID": "toolu_x",
            "message": {
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": "Base directory for this skill: ...\\skills\\mwc\n"
                            "... https://github.com/Morrison-Lab/ai-config/issues/3021 ...",
                }],
            },
        }) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "name": "Bash", "input": {"command": "echo hi"},
            }]},
        }) + "\n")
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


if meta_mid_turn_transcript(CLEAN_DECL):
    print(
        "FAIL: reply-tool delivery with a clean declaration warned after a "
        "mid-turn skill load (isMeta) (ai-config#3860)"
    )
    failed += 1
else:
    print(
        "PASS: reply-tool delivery with a clean declaration survives a "
        "mid-turn skill load (isMeta)"
    )

# The discriminating case: a MISSING declaration must still be caught after
# a mid-turn skill load. If the isMeta entry is (wrongly) treated as a new
# user turn, it wipes `saw_reply_tool`/`last_reply`, the trailing tool-only
# assistant entry sets nothing, and `extract_text_from_payload` returns "" --
# which the hook reads as "nothing to check" rather than "no declaration",
# so the miss silently produces NO warning instead of the warning it should.
if not meta_mid_turn_transcript(MISSING_DECL):
    print(
        "FAIL: reply-tool delivery missing its declaration did not warn "
        "after a mid-turn skill load (isMeta) -- the load silently erased "
        "the missing-declaration signal (ai-config#3860)"
    )
    failed += 1
else:
    print(
        "PASS: reply-tool delivery missing its declaration still warns "
        "after a mid-turn skill load (isMeta)"
    )


def scheduled_continuation_transcript(reply_text):
    """A scheduled check-in continuation (ScheduleWakeup/cron fire, via a
    queue enqueue/dequeue pair) ALSO arrives as `isMeta: true`, but with no
    `sourceToolUseID`. Unlike a loaded skill's body it IS a genuine new
    turn, so it MUST reset the accumulated reply -- an old turn's
    (missing-declaration) reply-tool content must not leak past it into a
    later turn that said nothing at all (ai-config#3860 coordinator review
    finding). See scripts/lib/transcript_meta.py for the transcript
    survey."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "do task"}}) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "name": "mcp__hearthbot__reply",
                "input": {"text": reply_text},
            }]},
        }) + "\n")
        f.write(json.dumps({
            "type": "user",
            "isMeta": True,
            "promptId": "p1",
            "promptSource": "sdk",
            "message": {
                "role": "user",
                "content": "Scheduled check-in: continue the task.",
            },
        }) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use", "name": "Bash", "input": {"command": "echo hi"},
            }]},
        }) + "\n")
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


if scheduled_continuation_transcript(MISSING_DECL):
    print(
        "FAIL: an old turn's missing-declaration reply-tool content leaked "
        "past a scheduled check-in continuation (isMeta, no "
        "sourceToolUseID) into a later turn that said nothing at all "
        "(ai-config#3860)"
    )
    failed += 1
else:
    print(
        "PASS: a scheduled check-in continuation (isMeta, no "
        "sourceToolUseID) opens a new turn, expiring an old turn's "
        "missing-declaration reply exactly as a real user message would"
    )

# Streamed chunks test cases (ai-config#2500)
def streamed_chunks_transcript(chunks, msg_id="msg_1"):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "do task"}}) + "\n")
        for chunk in chunks:
            f.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "id": msg_id,
                            "content": [{"type": "text", "text": chunk}],
                        },
                    }
                )
                + "\n"
            )
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=env,
    )
    os.unlink(path)
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return _has_warning(res.stdout)


# Test 1: Declaration split across chunk boundary (#2500)
split_chunks = [
    "Here is the final summary of the work done.\n\n**Stopping Point**: Clean stopping point reached --- ",
    "session done; UMS executed; no follow-up items pending.",
]
if streamed_chunks_transcript(split_chunks):
    print("FAIL: streamed chunks with declaration split across chunk boundary warned (#2500)")
    failed += 1
else:
    print("PASS: streamed chunks with declaration split across chunk boundary passes (#2500)")

# Test 2: Streamed chunks with cumulative updates
cumulative_chunks = [
    "Completed task.",
    "Completed task.\n\n**Stopping Point**: Clean stopping point reached --- session done.",
]
if streamed_chunks_transcript(cumulative_chunks):
    print("FAIL: streamed chunks with cumulative update warned (#2500)")
    failed += 1
else:
    print("PASS: streamed chunks with cumulative update passes (#2500)")

# Test 3: Declaration in first chunk, trailing prose in second chunk
trailing_chunks = [
    "Completed task.\n\n**Stopping Point**: Clean stopping point reached --- session done.\n",
    "\nHave a great day!",
]
if streamed_chunks_transcript(trailing_chunks):
    print("FAIL: declaration in first chunk with trailing chunk warned (#2500)")
    failed += 1
else:
    print("PASS: declaration in first chunk with trailing chunk passes (#2500)")

# Test 4: Streamed chunks missing declaration entirely
missing_chunks = [
    "Here is the answer to your question.\n",
    "Nothing is left for you to do.",
]
if not streamed_chunks_transcript(missing_chunks):
    print("FAIL: streamed chunks missing declaration did not warn (#2500)")
    failed += 1
else:
    print("PASS: streamed chunks missing declaration warns (#2500)")

# Conversational question-answering final replies (ai-config#4308)
qa_reply_without_decl = (
    "The branch was already auto-deleted on merge.\n"
    "We encountered proxy denials earlier.\n\n"
    "Nothing is left for you to do."
)
if not run(qa_reply_without_decl):
    print("FAIL: conversational question-answering reply without stopping point did not warn (#4308)")
    failed += 1
else:
    print("PASS: conversational question-answering reply without stopping point warns (#4308)")

qa_reply_with_decl = (
    "The branch was already auto-deleted on merge.\n"
    "We encountered proxy denials earlier.\n\n"
    "Nothing is left for you to do.\n\n"
    "**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending."
)
if run(qa_reply_with_decl):
    print("FAIL: conversational question-answering reply with clean stopping point warned (#4308)")
    failed += 1
else:
    print("PASS: conversational question-answering reply with clean stopping point passes (#4308)")

# Regression test: Different message.id sequence (msg_prior with declaration, msg_final without declaration)
diff_msg_id_transcript = [
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_prior",
            "content": [{"type": "text", "text": "Task complete.\n\n**Stopping Point**: Clean stopping point reached --- session done."}],
        },
    }),
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_final",
            "content": [{"type": "text", "text": "By the way, here is some follow-up info."}],
        },
    }),
]
if not run("", raw_lines=diff_msg_id_transcript):
    print("FAIL: different message.id sequence without stopping point did not warn")
    failed += 1
else:
    print("PASS: different message.id sequence without stopping point warns")

diff_msg_id_clean_transcript = [
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_prior",
            "content": [{"type": "text", "text": "Task complete."}],
        },
    }),
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_final",
            "content": [{"type": "text", "text": "Final response.\n\n**Stopping Point**: Clean stopping point reached --- session done."}],
        },
    }),
]
if run("", raw_lines=diff_msg_id_clean_transcript):
    print("FAIL: different message.id sequence with stopping point warned")
    failed += 1
else:
    print("PASS: different message.id sequence with stopping point passes")

# Regression test: Gemini / Antigravity transcript with tool_calls boundary
gemini_tool_boundary_transcript = [
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "Initial step.\n\n**Stopping Point**: Clean stopping point reached --- session done.",
        "tool_calls": [{"name": "run_command", "args": {"CommandLine": "dir"}}],
    }),
    json.dumps({
        "type": "USER_INPUT",
        "source": "USER_EXPLICIT",
        "content": [{"type": "tool_result", "content": "file1.txt\nfile2.txt"}],
    }),
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "Here is the directory listing: file1.txt, file2.txt.",
    }),
]
if not run("", raw_lines=gemini_tool_boundary_transcript):
    print("FAIL: Antigravity transcript with tool_calls boundary without stopping point did not warn")
    failed += 1
else:
    print("PASS: Antigravity transcript with tool_calls boundary without stopping point warns")

gemini_tool_boundary_clean_transcript = [
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "Initial step.",
        "tool_calls": [{"name": "run_command", "args": {"CommandLine": "dir"}}],
    }),
    json.dumps({
        "type": "USER_INPUT",
        "source": "USER_EXPLICIT",
        "content": [{"type": "tool_result", "content": "file1.txt\nfile2.txt"}],
    }),
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "Here is the listing.\n\n**Stopping Point**: Clean stopping point reached --- session done.",
    }),
]
if run("", raw_lines=gemini_tool_boundary_clean_transcript):
    print("FAIL: Antigravity transcript with tool_calls boundary with clean stopping point warned")
    failed += 1
else:
    print("PASS: Antigravity transcript with tool_calls boundary with clean stopping point passes")

# Regression test: Back-to-back MODEL events with no tool_calls (reviewer finding)
back_to_back_model_warn_transcript = [
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "First response.\n\n**Stopping Point**: Clean stopping point reached --- session done.",
    }),
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "Second response without stopping point declaration.",
    }),
]
if not run("", raw_lines=back_to_back_model_warn_transcript):
    print("FAIL: back-to-back MODEL events without stopping point did not warn")
    failed += 1
else:
    print("PASS: back-to-back MODEL events without stopping point warns")

back_to_back_model_clean_transcript = [
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "First response without declaration.",
    }),
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "content": "Second response.\n\n**Stopping Point**: Clean stopping point reached --- session done.",
    }),
]
if run("", raw_lines=back_to_back_model_clean_transcript):
    print("FAIL: back-to-back MODEL events with clean stopping point warned")
    failed += 1
else:
    print("PASS: back-to-back MODEL events with clean stopping point passes")

# Regression test: Back-to-back assistant events without IDs
back_to_back_assistant_no_id_transcript = [
    json.dumps({
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "First response.\n\n**Stopping Point**: Clean stopping point reached --- session done."}],
        },
    }),
    json.dumps({
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "Second response without stopping point declaration."}],
        },
    }),
]
if not run("", raw_lines=back_to_back_assistant_no_id_transcript):
    print("FAIL: back-to-back assistant events without IDs and without stopping point did not warn")
    failed += 1
else:
    print("PASS: back-to-back assistant events without IDs and without stopping point warns")

# Test: Scope sentinel deduplication to session and turn
shared_sentinel_tmpdir = tempfile.mkdtemp()
sess_turn_payload_1 = {
    "reply": "No stopping point declaration here.",
    "session_id": "sess_1",
    "turn_id": "turn_1",
}
sess_turn_payload_retry = {
    "reply": "No stopping point declaration here.",
    "session_id": "sess_1",
    "turn_id": "turn_1",
}
sess_turn_payload_next_turn = {
    "reply": "No stopping point declaration here.",
    "session_id": "sess_1",
    "turn_id": "turn_2",
}
sess_turn_payload_next_sess = {
    "reply": "No stopping point declaration here.",
    "session_id": "sess_2",
    "turn_id": "turn_1",
}

if not run_direct_payload(sess_turn_payload_1, tmpdir=shared_sentinel_tmpdir):
    print("FAIL: first invocation with session/turn did not warn")
    failed += 1
else:
    print("PASS: first invocation with session/turn warns")

if run_direct_payload(sess_turn_payload_retry, tmpdir=shared_sentinel_tmpdir):
    print("FAIL: same-turn retry was not deduplicated")
    failed += 1
else:
    print("PASS: same-turn retry is deduplicated")

if not run_direct_payload(sess_turn_payload_next_turn, tmpdir=shared_sentinel_tmpdir):
    print("FAIL: identical missing-declaration in later turn was silently ignored")
    failed += 1
else:
    print("PASS: identical missing-declaration in later turn warns")

if not run_direct_payload(sess_turn_payload_next_sess, tmpdir=shared_sentinel_tmpdir):
    print("FAIL: identical missing-declaration in another session was silently ignored")
    failed += 1
else:
    print("PASS: identical missing-declaration in another session warns")

# Test: Harness-mode exceptions
if run_direct_payload({"reply": "No stopping point declaration here.", "harness_mode": True}):
    print("FAIL: harness_mode payload warned")
    failed += 1
else:
    print("PASS: harness_mode payload passes without warning")

if run_direct_payload({"reply": "No stopping point declaration here.", "non_interactive": True}):
    print("FAIL: non_interactive payload warned")
    failed += 1
else:
    print("PASS: non_interactive payload passes without warning")

if run_direct_payload({"reply": "No stopping point declaration here."}, env={"HARNESS_MODE": "1"}):
    print("FAIL: HARNESS_MODE env warned")
    failed += 1
else:
    print("PASS: HARNESS_MODE env passes without warning")

if run_direct_payload({"reply": "No stopping point declaration here."}, env={"CLAUDE_NON_INTERACTIVE": "1"}):
    print("FAIL: CLAUDE_NON_INTERACTIVE env warned")
    failed += 1
else:
    print("PASS: CLAUDE_NON_INTERACTIVE env passes without warning")

# Test: Whitespace preservation during chunk reconstruction (assistant branch)
whitespace_assistant_transcript = [
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_ws",
            "content": "**Stopping Point**: Clean stopping point reached --- session",
        },
    }),
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_ws",
            "content": " ",
        },
    }),
    json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_ws",
            "content": "done.",
        },
    }),
]
if run("", raw_lines=whitespace_assistant_transcript):
    print("FAIL: assistant string chunks with whitespace-only chunk warned")
    failed += 1
else:
    print("PASS: assistant string chunks with whitespace-only chunk passes")

# Test: Whitespace preservation in MODEL/PLANNER_RESPONSE reconstruction
whitespace_model_transcript = [
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "id": "model_ws",
        "content": "**Stopping Point**: Clean stopping point reached --- session",
    }),
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "id": "model_ws",
        "content": " ",
    }),
    json.dumps({
        "type": "PLANNER_RESPONSE",
        "source": "MODEL",
        "id": "model_ws",
        "content": "done.",
    }),
]
if run("", raw_lines=whitespace_model_transcript):
    print("FAIL: MODEL string chunks with whitespace-only chunk warned")
    failed += 1
else:
    print("PASS: MODEL string chunks with whitespace-only chunk passes")

raise SystemExit(bool(failed))

