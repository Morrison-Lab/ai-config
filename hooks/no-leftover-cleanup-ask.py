#!/usr/bin/env python3
"""PreToolUse: delete your own install leftovers instead of handing them to the user.

ai-config#5843. Ezra, 2026-11-18: "cai: always clean up after yourself after
installs etc". After installing ONLYOFFICE on a lab machine, a session left the
426 MB AppImage download in ~/.local/opt/onlyoffice-dl and told Ezra he could
delete it. The agent removes its own temporary downloads, installers,
extracted archives and scratch directories after an install or other setup
task, without asking, and reports what it removed.

Blocks (deny) a user-visible reply tool call (mcp__hearthbot__reply,
post_message, update_message, edit_message) whose sentence both names such a
leftover (download, installer, AppImage, archive, tarball, .zip, .dmg, .deb,
scratch or temp directory, ...) and hands its removal to the user:

  * "you can / could / may delete (remove, rm, trash, clean up) ...";
  * "feel free to delete ...", "delete it whenever you like";
  * "... is safe to delete", "... can be deleted / removed";
  * "I left / kept the download in ...".

A sentence that names a secret, credential or key is exempt, and so is one
that says the agent already removed the leftover ("I deleted the installer").
No hook can see a leftover the agent stays silent about, so that half of the
rule is prose (shared/workflow/standing-habits-from-ezra.md).
ALLOW_LEFTOVER_HANDOFF=1 overrides, for a file the user must decide on
(something the agent did not create). Fails open on parse trouble.
"""
import json
import os
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

LEFTOVER = re.compile(
    r"\b(?:downloads?|downloaded|installers?|appimages?|archives?|tarballs?|zips?"
    r"|extracted|unpacked|scratch|temp(?:orary)?|tmp|leftovers?|setup files?|build dir(?:ectory)?)\b"
    r"|-dl\b"
    r"|\.(?:zip|tar|tgz|gz|xz|bz2|7z|dmg|pkg|deb|rpm|msi|exe|whl|appimage)\b",
    re.I)

DEL = r"(?:delete|remove|rm|trash|clean(?:\s+it|\s+them)?\s+up|discard|get rid of)"
HANDOFF = re.compile(
    r"\b(?:you|Ezra)\s+(?:can|could|may|might want to|should|need to)\s+(?:now\s+|safely\s+|also\s+)?" + DEL + r"\b"
    r"|\bfeel free to\s+" + DEL + r"\b"
    r"|\b" + DEL + r"\s+(?:it|them|that|those)\s+(?:whenever|if you|when you|at your)\b"
    r"|\b(?:is|are)\s+(?:now\s+)?safe\s+to\s+" + DEL + r"\b"
    r"|\bcan\s+(?:now\s+|safely\s+)?be\s+(?:deleted|removed|trashed|discarded|cleaned up)\b"
    r"|\bI\s+(?:left|kept)\b",
    re.I)

DONE = re.compile(
    r"\bI(?:'ve| have)?\s+(?:already\s+)?(?:deleted|removed|cleaned up|trashed|discarded)\b"
    r"|\b(?:was|were|has been|have been)\s+(?:deleted|removed|cleaned up)\b",
    re.I)
SECRET = re.compile(r"\b(?:secrets?|tokens?|passwords?|credentials?|keys?|keychain)\b", re.I)

SENTENCE_BREAK = re.compile(r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<=[.!?])\s+|\n+", re.I)

REASON = (
    "[hook: no-leftover-cleanup-ask] This message hands the user the removal of an install or setup leftover: "
    "\"{sentence}\". Delete your own temporary downloads, installers, extracted archives and scratch directories "
    "yourself, without asking, then report what you removed and how much space it freed (Ezra, 2026-11-18: "
    "\"always clean up after yourself after installs etc\"; ai-config#5843). If the file is not yours to delete, "
    "say whose it is; ALLOW_LEFTOVER_HANDOFF=1 overrides."
)


def offending_sentence(text: str):
    for sentence in SENTENCE_BREAK.split(text):
        if not (LEFTOVER.search(sentence) and HANDOFF.search(sentence)):
            continue
        if SECRET.search(sentence):
            continue
        if DONE.search(sentence) and not re.search(r"\b(?:you|Ezra)\s+(?:can|could|may|should)\b", sentence, re.I):
            continue
        return sentence.strip()
    return None


def main() -> int:
    if os.environ.get("ALLOW_LEFTOVER_HANDOFF") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    sentence = offending_sentence(text)
    if sentence is None:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(sentence=sentence[:200]),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
