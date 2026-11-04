#!/usr/bin/env python3
"""PreToolUse guard: an agent never sends an email for Ezra.

User directive, 2026-11-04: "never send emails for me". An agent may draft an
email (a Gmail draft, a file, a message in the thread); the user sends it.

## What it decides

DENY, with no override, when the call would send email:

  - Bash: a command word (first word of any `;`, `&&`, `||`, `|` or newline
    segment) that is a mail sender (`sendmail`, `mail`, `mailx`, `mutt`,
    `msmtp`, `ssmtp`, `swaks`, `mailsend`, `s-nail`, `neomutt`), or
    `git send-email`, or a network client (`curl`, `openssl`, `nc`...) aimed at an
    `smtp://` URL or port 25/465/587, or an `import smtplib` / `smtplib.SMTP`.
  - An MCP tool whose name sends mail: a Gmail/mail-server tool whose action
    is `send` (`send_email`, `send_message`, `send_draft`, `sendEmail`...).
    Drafting tools (`create_draft`, `draft_email`) are untouched.

Everything else is silent. The rule is the user's words, unbroadened and
untightened: it says "send", so drafting stays allowed.

Run with `--dry-run '<payload json>'` to see the verdict without acting.
"""
import json
import re
import sys

MAIL_COMMANDS = {
    "sendmail", "mail", "mailx", "bsd-mailx", "mutt", "neomutt", "msmtp",
    "ssmtp", "swaks", "mailsend", "s-nail", "nail", "mpack", "heirloom-mailx",
}
SEGMENT_SPLIT = re.compile(r"\|\||&&|[;|&\n]")
WRAPPERS = {"sudo", "env", "command", "exec", "nohup", "time", "xargs", "nice"}
# An smtp URL counts only as the target of a network client, and smtplib only
# when imported or called, so `grep smtplib hooks/` and `echo smtp://x` pass.
NET_COMMANDS = {"curl", "wget", "openssl", "nc", "ncat", "telnet", "socat"}
SMTP_URL = re.compile(r"smtps?://|[: ](25|465|587)\b", re.IGNORECASE)
SMTPLIB_USE = re.compile(r"\b(import|from)\s+smtplib\b|\bsmtplib\.SMTP", re.IGNORECASE)
MCP_SEND = re.compile(
    r"^mcp__.*(mail|gmail|outlook|smtp|inbox).*(send|reply|forward)"
    r"|^mcp__.*(send|reply|forward).*(mail|gmail)"
    r"|^mcp__.*gmail.*__send",
    re.IGNORECASE)


def _read_payload():
    args = sys.argv[1:]
    dry = "--dry-run" in args or "--simulate" in args
    if dry:
        positional = [a for a in args if not a.startswith("-")]
        if positional and positional[0].strip().startswith("{"):
            try:
                return json.loads(positional[0]), True
            except Exception:
                pass
        if positional:
            return {"tool_name": "Bash", "tool_input": {"command": positional[0]}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), dry
    except Exception as exc:
        print(f"no-send-email: unreadable hook input ({exc})", file=sys.stderr)
        return {}, dry


def bash_sends_email(command):
    """The offending fragment of a shell command, or None."""
    use = SMTPLIB_USE.search(command)
    if use:
        return use.group(0)
    for seg in SEGMENT_SPLIT.split(command):
        words = seg.split()
        while words and (words[0] in WRAPPERS or "=" in words[0].split("/")[-1]
                         and not words[0].startswith(("/", "."))):
            words = words[1:]
        if not words:
            continue
        first = words[0].rsplit("/", 1)[-1]
        if first in MAIL_COMMANDS:
            return first
        if first in NET_COMMANDS and SMTP_URL.search(seg):
            return f"{first} to an smtp target"
        if first == "git" and "send-email" in words[1:3]:
            return "git send-email"
    return None


def decide(payload):
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    hit = None
    if tool == "Bash":
        cmd = inp.get("command")
        hit = bash_sends_email(cmd) if isinstance(cmd, str) else None
    elif tool.startswith("mcp__") and MCP_SEND.search(tool):
        hit = tool
    if not hit:
        return None
    return (
        "MECHANISTIC PROHIBITION: Ezra's standing rule, 2026-11-04: "
        "\"never send emails for me\".\n\n"
        f"    This call: {hit}.\n\n"
        "Draft the email instead (a draft in the mail account, a file, or a "
        "message in the thread) and leave the sending to the user. There is "
        "no override.")


def main():
    payload, dry = _read_payload()
    if not payload:
        return 0
    text = decide(payload)
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if text:
        out["hookSpecificOutput"]["permissionDecision"] = "deny"
        out["hookSpecificOutput"]["permissionDecisionReason"] = text
        print(json.dumps(out))
    elif dry:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
