"""Test the no-reauth-without-host-check Stop guard.

Case W1 is the incident (ai-config#4387): `glab api` ran from a non-checkout,
glab fell back to gitlab.com and said "Unauthenticated", and the final message
told the user the token had expired and to re-run `glab auth login` -- with no
check of the token against the intended host.

Each case builds a small JSONL transcript. The silent cases decide whether the
guard survives: a host-scoped check since the last prompt, a message that only
discusses the phrase inside code, and a negated or conditional mention.

Every verdict call appends a fresh nonce to the final message, because the hook
fires at most once per distinct message (a sentinel in the temp dir) and the
mutation harness replays each case.

Run:  python3 hooks/test-no-reauth-without-host-check.py \\
          hooks/no-reauth-without-host-check.py
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

HOOK = os.path.realpath(sys.argv[1])
if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")
with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

FENCE = "`" * 3


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "Unauthenticated"}]}}


def hook_feedback():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": "Stop hook feedback: something unrelated"}]}}


def bash(command):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t1", "name": "Bash",
         "input": {"command": command}}]}}


def reply_tool(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t2", "name": "mcp__x__reply",
         "input": {"text": text}}]}}


def final(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text}]}}


FAILED = bash("cd ~/Documents && glab api projects/7/issues")
CLAIM = "The token has expired. Please re-run `glab auth login` and I will retry."

# (id, transcript entries, description)
SHOULD_WARN = [
    ("W1", [user("list the issues"), FAILED, final(CLAIM)],
     "the incident: failed glab api, then 'token expired / re-run glab auth login'"),
    ("W2", [user("go"), FAILED,
            final("Authentication failed. Run:\n\n" + FENCE + "\nglab auth login\n"
                  + FENCE + "\n")],
     "the login command in a fenced block after 'Run:'"),
    ("W3", [user("go"), FAILED, final("You'll need to re-authenticate before I can continue.")],
     "'you'll need to re-authenticate' with no check"),
    ("W4", [user("go"), bash("gh api repos/o/r"), final("Try `gh auth login` again.")],
     "the gh variant"),
    ("W5", [user("first"), bash("curl -s https://h.example.org/api/v4/user"),
            user("second"), FAILED, final(CLAIM)],
     "a check in a PREVIOUS turn does not cover this turn"),
    ("W6", [user("go"), bash("curl -s https://h.example.org/api/v4/projects"),
            final(CLAIM)],
     "a curl to a different endpoint is not a token check"),
    ("W7", [user("go"), bash("glab api user"), final(CLAIM)],
     "glab api user with NO host names no host: it is the failing call itself"),
    ("W8", [user("go"), FAILED, reply_tool(CLAIM)],
     "the message is a reply-tool payload, not an assistant text block"),
    ("W9", [user("go"), FAILED, final("Your credentials were revoked, it seems.")],
     "'credentials were revoked' with no check"),
    ("W11", [user("go"), FAILED, final("Please run glab auth login and tell me when done.")],
     "the login command written without backticks"),
    ("W10", [user("go"), FAILED, final("Looks like you must log in again.")],
     "'log in again' as an instruction"),
]

SHOULD_STAY_SILENT = [
    ("S1", [user("go"), FAILED,
            bash("curl -s -H 'PRIVATE-TOKEN: x' https://git.example.org/api/v4/user"),
            final(CLAIM)],
     "curl to /api/v4/user on a named host verifies the token"),
    ("S2", [user("go"), FAILED,
            bash("glab api --hostname git.example.org user"),
            final(CLAIM)],
     "glab api --hostname H user"),
    ("S3", [user("go"), bash("gh api --hostname ghe.example.org user"), final(CLAIM)],
     "gh api --hostname H user"),
    ("S4", [user("go"), bash("GITLAB_HOST=git.example.org glab api user"), final(CLAIM)],
     "a GITLAB_HOST prefix names the host"),
    ("S5", [user("go"), final("The hook fires on `You need to re-authenticate` "
                              "and on `the token has expired` messages.")],
     "the phrases only inside inline code spans"),
    ("S6", [user("go"),
            final("Example:\n\n" + FENCE + "\nPlease re-authenticate. The token expired.\n"
                  + FENCE + "\n\nThat is what the test feeds the hook.")],
     "the phrases only inside a fenced block"),
    ("S7", [user("go"), FAILED, final("The token has not expired; the host was wrong.")],
     "a negated expiry claim"),
    ("S8", [user("go"), FAILED, final("The issues list has 12 open items.")],
     "no claim at all"),
    ("S9", [user("go"), FAILED,
            final("If the token expired I would see a 401 from the right host, "
                  "but I have not seen one.")],
     "a conditional mention"),
    ("S10", [user("go"), bash("curl -s https://h.example.org/api/v4/user"),
             tool_result(), final(CLAIM)],
     "a tool_result-only user entry is not a new prompt and does not reset the check"),
    ("S11", [user("go"), bash("curl -s https://h.example.org/api/v4/user"),
             hook_feedback(), final(CLAIM)],
     "hook feedback is not a new prompt and does not reset the check"),
    ("S12", [user("go"), bash("curl -s https://h.example.org/user"),
             final(CLAIM)],
     "curl to /user (GitHub-style) verifies the token"),
    ("S15", [user("go"), FAILED, final("If glab says Unauthenticated, run `glab auth login`.")],
     "a sentence that opens with a conditional"),
    ("S16", [user("go"), bash("curl -s https://h.example.org/api/v4/user"),
             final(CLAIM), user("next"), bash("ls")],
     "an earlier verified turn's claim is not re-evaluated in a later tool-only turn"),
    ("S13", [user("go"), FAILED, final("Do not run `glab auth login` yet; the host was wrong.")],
     "a negated auth-login instruction"),
    ("S14", [user("go"), FAILED, final("The session lock expired, so I retried.")],
     "'session lock expired' is not a credential claim"),
]

BAD_TRANSCRIPTS = ["missing", "empty", "garbage"]


def write_transcript(entries, nonce):
    entries = [json.loads(json.dumps(e)) for e in entries]
    last = entries[-1]
    blocks = last["message"]["content"]
    for b in blocks:
        if b.get("type") == "text":
            b["text"] += f"\n\n[nonce {nonce}]"
        elif b.get("type") == "tool_use" and isinstance(b.get("input"), dict) \
                and "text" in b["input"]:
            b["input"]["text"] += f"\n\n[nonce {nonce}]"
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for e in entries:
            handle.write(json.dumps(e) + "\n")
    return path


def run(hook_path, transcript_path):
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps({"transcript_path": transcript_path}),
        capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout


def verdict(hook_path, entries):
    path = write_transcript(entries, uuid.uuid4().hex)
    try:
        out = run(hook_path, path)
    finally:
        os.unlink(path)
    if not out.strip():
        return "silent"
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: non-JSON stdout ({exc}): {out!r}")
    if parsed.get("decision") == "block":
        sys.exit("FATAL: warn-only guard emitted decision=block")
    return "WARN" if parsed.get("systemMessage") else "silent"


wrong = 0
print("should WARN:")
for cid, entries, desc in SHOULD_WARN:
    got = verdict(HOOK, entries)
    wrong += got != "WARN"
    print(f"  {got:<6} {cid:<4} {desc}")

print("\nshould STAY SILENT:")
for cid, entries, desc in SHOULD_STAY_SILENT:
    got = verdict(HOOK, entries)
    wrong += got != "silent"
    print(f"  {got:<6} {cid:<4} {desc}")

print("\nunreadable transcripts (must fail open silently):")
for kind in BAD_TRANSCRIPTS:
    if kind == "missing":
        path = "/nonexistent/transcript.jsonl"
    else:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as handle:
            handle.write("" if kind == "empty" else "{not json\n\x00\x01\n")
    out = run(HOOK, path)
    got = "silent" if not out.strip() else "WARN"
    wrong += got != "silent"
    print(f"  {got:<6} {kind}")

# Fires at most once per distinct message.
dup = write_transcript([user("go"), FAILED, final(CLAIM)], uuid.uuid4().hex)
first, second = run(HOOK, dup), run(HOOK, dup)
os.unlink(dup)
once = bool(first.strip()) and not second.strip()
wrong += not once
print(f"\n  {'ok  ' if once else 'WRONG'} ONCE  fires once, then stays silent on the same message")

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + len(BAD_TRANSCRIPTS)
print(f"\n{total + 1 - wrong}/{total + 1} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

EXPECTED = {cid: "WARN" for cid, *_ in SHOULD_WARN}
EXPECTED.update({cid: "silent" for cid, *_ in SHOULD_STAY_SILENT})
CASES = {cid: entries for cid, entries, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

MUTATIONS = {
    "M1_curl_check": (
        "a curl to /user no longer counts as a check",
        [('    if RX_CURL_USER.search(command):\n        return True\n',
          '')],
        {"S1", "S10", "S11", "S12"},
    ),
    "M2_scoped_api_check": (
        "glab/gh api user no longer counts as a check",
        [('    return any(_segment_verifies(s) for s in RX_SEGMENT_SPLIT.split(command))',
          '    return False')],
        {"S2", "S3", "S4"},
    ),
    "M3_host_required": (
        "an unscoped glab api user would count as a check",
        [('    if not ("--hostname" in seg or RX_HOST_ASSIGN.search(seg)):\n'
          '        return False\n', '')],
        {"W7"},
    ),
    "M4_turn_reset": (
        "a new user prompt must reset the check",
        [('                    verified = False  # a new real prompt starts a new turn',
          '                    pass')],
        {"W5"},
    ),
    "M5_negation": (
        "negated and conditional claims must be skipped",
        [('        if (RX_NEGATED_BEFORE.search(prefix) or RX_CONDITIONAL_OPENING.search(prefix)\n'
          '                or RX_NEGATED_INSIDE.search(m.group(0))):', '        if False:')],
        {"S7", "S9", "S13", "S15"},
    ),
    "M6_code_stripping": (
        "code spans and fences must be ignored",
        [('    prose = strip_code(mark_auth_commands(text))',
          '    prose = mark_auth_commands(text)')],
        {"S5", "S6"},
    ),
    "M7_keep_auth_command": (
        "an auth-login command in a code span or fence must survive stripping",
        [('    prose = strip_code(mark_auth_commands(text))',
          '    prose = strip_code(text)')],
        {"W2", "W4"},
    ),
    "M8_hook_feedback": (
        "hook feedback must not count as a new prompt",
        [('                if is_skill_load_meta(m) or is_hook_feedback(m):',
          '                if is_skill_load_meta(m):')],
        {"S11"},
    ),
    "M9_tool_result": (
        "a tool_result-only user entry must not count as a new prompt",
        [('                if any(b.get("type") == "text" and b.get("text", "").strip()\n'
          '                       for b in _blocks(m)):',
          '                if True:')],
        {"S10"},
    ),
    "M10_reply_tool": (
        "reply-tool payloads must be read as the final message",
        [('                        if REPLY_TOOL_RX.search(b.get("name") or ""):',
          '                        if False:')],
        {"W8"},
    ),
    "M11_text_reset": (
        "a new prompt must discard the earlier turn's final message",
        [('                    text = ""  # and an earlier turn\'s message is not this turn\'s', '                    pass')],
        {"S16"},
    ),
}

print("\nmutation tests (break one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is present {count} "
                     f"times in {HOOK}, expected once:\n{find}")
        mutated = mutated.replace(find, replace)
    # The copy must sit next to the hook: it resolves scripts/lib from __file__.
    fd, path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {cid for cid, entries in CASES.items()
                   if verdict(path, entries) != EXPECTED[cid]}
    finally:
        os.unlink(path)
    ok = flipped == expected_flips
    mutation_wrong += not ok
    note = ("flipped " + ", ".join(sorted(flipped)) if flipped
            else "NOTHING FLIPPED -- this clause is untested")
    if not ok:
        note += f" (expected {sorted(expected_flips)})"
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<24} {statement}\n         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under mutation")
sys.exit(1 if (wrong or mutation_wrong) else 0)
