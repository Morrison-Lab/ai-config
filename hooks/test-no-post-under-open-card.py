#!/usr/bin/env python3
"""Tests for hooks/no-post-under-open-card.py.

Run: python3 hooks/test-no-post-under-open-card.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-post-under-open-card.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
CARD = "cmsg_014QLd5McmoUEgMPRiXeVnjSLFcQnywzYL4m414aW669zh"
OTHER_CARD = "cmsg_014QLd5McmoUEgMPRiXeVnjS17WLrNgbtAiRN4mvHRLrDR"
passes = failures = 0


def transcript(*lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    f.write("".join(lines))
    f.close()
    return f.name


def tool_use(name, tool_input, use_id="toolu_card"):
    block = {"type": "tool_use", "id": use_id, "name": name, "input": tool_input}
    return json.dumps({"type": "assistant", "message": {"content": [block]}}) + "\n"


def tool_result(text, use_id="toolu_card", is_error=False):
    block = {"type": "tool_result", "tool_use_id": use_id, "content": text}
    if is_error:
        block["is_error"] = True
    return json.dumps({"type": "user", "message": {"content": [block]}}) + "\n"


def wake(text, as_block=True):
    content = [{"type": "text", "text": text}] if as_block else text
    return json.dumps({"type": "user", "message": {"content": content}}) + "\n"


def card_posted(card=CARD, use_id="toolu_card"):
    return (tool_use("mcp__hearthbot__request_decision", {"question": "Pick?"}, use_id)
            + tool_result(json.dumps({"message_id": card, "note": "Card posted in this thread."}), use_id))


OPEN = transcript(card_posted())
ANSWERED = transcript(card_posted(), wake(f"<system-note>decision_id={CARD}</system-note>"))
ANSWERED_STR = transcript(card_posted(), wake(f"decision_id={CARD}", as_block=False))
ANSWERED_QUEUE = transcript(card_posted(), json.dumps(
    {"type": "queue-operation", "operation": "enqueue",
     "content": f"<wake reason=\"decision-chosen\"><system-note>decision_id={CARD}</system-note></wake>"}) + "\n")
ASSISTANT_QUOTE = transcript(card_posted(), json.dumps(
    {"type": "assistant", "message": {"content": [{"type": "text", "text": f"decision_id={CARD}"}]}}) + "\n")
WITHDRAWN = transcript(card_posted(),
                       tool_use("mcp__hearthbot__close_decision", {"message_id": CARD}, "toolu_close"))
FAILED = transcript(tool_use("mcp__hearthbot__request_decision", {"question": "Pick?"}),
                    tool_result("error: refused", is_error=True))
QUOTED_ONLY = transcript(tool_use("mcp__hearthbot__post_message", {"text": f'"message_id":"{CARD}"'}, "toolu_p"),
                         tool_result("ok", "toolu_p"))
TWO_ONE_OPEN = transcript(card_posted(CARD, "toolu_a"), wake(f"decision_id={CARD}"),
                          card_posted(OTHER_CARD, "toolu_b"))
NONE = transcript(wake("hello"))


def check(label, cond):
    global passes, failures
    if cond:
        passes += 1
    else:
        failures += 1
        print(f"FAIL: {label}")


def payload(path, tool=POST, tool_input=None):
    return {"tool_name": tool, "tool_input": tool_input or {"text": "update"}, "transcript_path": path}


check("open card denies a post", hook.denial(payload(OPEN)) is not None)
check("denial names the card", CARD in (hook.denial(payload(OPEN)) or ""))
check("open card denies a checklist update",
      hook.denial(payload(OPEN, "mcp__hearthbot__update_progress_checklist")) is not None)
check("open card denies a second card",
      hook.denial(payload(OPEN, "mcp__hearthbot__request_decision")) is not None)
check("open card denies an edit", hook.denial(payload(OPEN, "mcp__hearthbot__edit_message")) is not None)
check("close_decision is never blocked",
      hook.denial(payload(OPEN, "mcp__hearthbot__close_decision")) is None)
check("no_reply_needed is never blocked",
      hook.denial(payload(OPEN, "mcp__hearthbot__no_reply_needed")) is None)
check("a react is never blocked", hook.denial(payload(OPEN, "mcp__hearthbot__react")) is None)
check("non-hearthbot tools pass", hook.denial(payload(OPEN, "Bash")) is None)
check("answered card (text block wake) passes", hook.denial(payload(ANSWERED)) is None)
check("answered card (string wake) passes", hook.denial(payload(ANSWERED_STR)) is None)
check("answered card (queue-operation wake) passes", hook.denial(payload(ANSWERED_QUEUE)) is None)
check("the assistant quoting a decision id does not close the card",
      hook.denial(payload(ASSISTANT_QUOTE)) is not None)
check("withdrawn card passes", hook.denial(payload(WITHDRAWN)) is None)
check("failed request_decision opens nothing", hook.denial(payload(FAILED)) is None)
check("a quoted id in another tool's result opens nothing", hook.denial(payload(QUOTED_ONLY)) is None)
check("the later still-open card is named",
      OTHER_CARD in (hook.denial(payload(TWO_ONE_OPEN)) or ""))
check("no card passes", hook.denial(payload(NONE)) is None)
check("missing transcript fails open", hook.denial(payload("/nonexistent/x.jsonl")) is None)
check("non-dict payload fails open", hook.denial(["x"]) is None)

os.environ[hook.OVERRIDE] = "1"
check("override passes", hook.denial(payload(OPEN)) is None)
del os.environ[hook.OVERRIDE]


def run(stdin):
    return subprocess.run([sys.executable, SCRIPT], input=stdin, capture_output=True, text=True)


out = run(json.dumps(payload(OPEN)))
check("cli exits 0", out.returncode == 0)
check("cli emits deny", '"permissionDecision": "deny"' in out.stdout)
out = run(json.dumps(payload(ANSWERED)))
check("cli silent when clean", out.stdout.strip() == "")
out = run("not json")
check("cli fails open on bad stdin", out.returncode == 0 and out.stdout.strip() == "")

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
