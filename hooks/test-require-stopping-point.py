import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


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
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout


def run_direct_payload(payload):
    tmpdir = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmpdir, TEMP=tmpdir, TMP=tmpdir)
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    assert res.returncode == 0, f"Hook exited with code {res.returncode}: {res.stderr}"
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout


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
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout


cases = [
    ("Completed the checks.", True),
    ("Completed the checks.\n\n**Stopping Point**: Clean stopping point reached.", False),
    ("Completed the task.\n\n- **Stopping Point**: Clean stopping point reached.", False),
    ("Indented list:\n  - **Stopping Point**: Clean stopping point reached.", False),
    ("Colon inside bold:\n**Stopping Point:** Clean stopping point reached.", False),
    ("### Stopping Point: Clean stopping point reached.", False),
    ("**Stopping Point**: Not a clean stopping point / work remains queued: finish X.", False),
    ("**Stopping Point**: Not clean --- CI is still running.", False),
    ("This PR adds a hook that requires text like `**Stopping Point**: Clean stopping point reached` in every final reply.", True),
    ("Discussion of rule:\n```\n**Stopping Point**: Clean stopping point reached\n```\nStill working on task.", True),
    ("Discussion of rule:\n```markdown\n**Stopping Point**: Clean stopping point reached\n```\nDone with task.\n\n**Stopping Point**: Clean stopping point reached.", False),
    ("**Stopping Point**: Cleanup pending, more work needed.", True),
    ("To open a fence type ``` on its own line.\n\n**Stopping Point**: Clean stopping point reached\n\n```\ncode\n```", False),
    ("Don't write a bare declaration like this:\n```\n**Stopping Point**: Clean stopping point reached\n```\nI have not actually finished; more work remains.\n\nAlso, here's a separate unrelated snippet I was about to show:\n```\n", True),
    ("```\n**Stopping Point**: Clean stopping point reached\n```\n```\n", True),
    # ai-config#3748: unterminated fence must not swallow subsequent declaration
    ("Snippet below:\n```python\nprint(1)\n\n**Stopping Point**: Clean stopping point reached.", False),
    # ai-config#3748: 4-backtick fence wrapping 3-backtick fence
    ("Code sample:\n````markdown\n```\n**Stopping Point**: Clean stopping point reached\n```\n````\nStill working.", True),
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
CLEAN_DECL = "**Stopping Point**: Clean stopping point reached."
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
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout

# Multi-turn test: turn 1 reply-tool state must not leak into turn 2 plain-text
if not multi_turn_transcript(CLEAN_DECL, MISSING_DECL):
    print("FAIL: turn 2 plain-text missing stopping point did not block after turn 1 used reply-tool")
    failed += 1
else:
    print("PASS: turn 2 plain-text missing stopping point blocks after turn 1 reply-tool")

if multi_turn_transcript(MISSING_DECL, CLEAN_DECL):
    print("FAIL: turn 2 plain-text clean stopping point blocked because turn 1 reply-tool lacked declaration")
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
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout


if not tool_result_transcript(MISSING_DECL):
    print("FAIL: reply-tool followed by tool_result did not block when declaration was missing")
    failed += 1
else:
    print("PASS: reply-tool followed by tool_result blocks when declaration is missing")

if tool_result_transcript(CLEAN_DECL):
    print("FAIL: reply-tool followed by tool_result blocked despite clean declaration")
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
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout


if meta_mid_turn_transcript(CLEAN_DECL):
    print(
        "FAIL: reply-tool delivery with a clean declaration blocked after a "
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
# so the miss silently produces NO block instead of the block it should.
if not meta_mid_turn_transcript(MISSING_DECL):
    print(
        "FAIL: reply-tool delivery missing its declaration did not block "
        "after a mid-turn skill load (isMeta) -- the load silently erased "
        "the missing-declaration signal (ai-config#3860)"
    )
    failed += 1
else:
    print(
        "PASS: reply-tool delivery missing its declaration still blocks "
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
    return '"decision": "block"' in res.stdout or '"decision":"block"' in res.stdout


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

raise SystemExit(bool(failed))

