#!/usr/bin/env python3
"""Stop-hook guard: a missing tool is installed, and a lasting install is reported.

Ezra, 2026-11-02: "cai: no excuses; always install what you need" and "cai: tell
me to modify the cloud startup script when there's something worth adding".
Two warn-only checks on the final reply, once per distinct message:

  1. EXCUSE: work skipped because a tool is missing, and no "I installed it".
  2. STARTUP SCRIPT: the turn ran an install and the reply never mentions the script.

See shared/workflow/growth-mindset.md. Lexical, and fails OPEN.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from agent_notice import stop_notice  # noqa: E402
from sibling import load_sibling  # noqa: E402


def _sibling():
    """`flag-cop-out-offer.py` (scripts/lib/sibling.py); raises if it cannot load."""
    return load_sibling(__file__, "flag-cop-out-offer.py", "flag_cop_out_offer",
                        required=True)


# Ezra, 2026-11-04, on psw#480's reply "I haven't rendered the page, and
# `typos` isn't installed in this session": "never make an excuse like this",
# and "why not?" to "haven't rendered". The perfect tense slipped past the
# earlier past-tense forms, and a curly apostrophe must match like a straight one.
SKIPPED = (r"(?:skipp(?:ed|ing)|couldn['\u2019]?t|could not|can['\u2019]?t|cannot|unable to"
           r"|didn['\u2019]?t (?:run|render|check)|did not (?:run|render|check)"
           r"|(?:haven['\u2019]?t|have not|hasn['\u2019]?t|has not)(?: yet)?"
           r" (?:(?:run|checked)\b(?! (?:into|in|out|across)\b)"
           r"|(?:rendered|spell-checked|linted|tested|built)\b"
           r"|been able to (?:run|render|check|test|build))"
           r"|not (?:run|rendered|checked)|without (?:running|rendering))")
# "missing" and "lacks" count only beside a tool-like noun.
TOOL = (r"(?:tools?|toolchains?|packages?|interpreters?|librar(?:y|ies)"
        r"|dependenc(?:y|ies)|modules?|binary|binaries|cli|extensions?"
        r"|compilers?|runtimes?)\b")
MISSING = (r"(?:(?:isn['\u2019]?t|is not|aren['\u2019]?t|are not|wasn['\u2019]?t|not) installed"
           rf"|{TOOL}\s+(?:\S+\s+){{0,3}}?(?:lacks|lacked|missing)\b"
           rf"|(?:lacks|lacked|missing)\s+(?:\S+\s+){{0,3}}?{TOOL}"
           r"|(?:isn['\u2019]?t|is not|not) (?:available|present)"
           r"|(?:no|without) (?:\S+ ){0,3}(?:installed|interpreter))")
FIXED = re.compile(r"\b(?:i|we) (?:installed|have installed|then installed)\b"
                   r"|\binstalled (?:it|them|that)\b", re.I)
EXCUSE = re.compile(
    rf"(?:{SKIPPED}[^.\n]{{0,120}}{MISSING}|{MISSING}[^.\n]{{0,120}}{SKIPPED})",
    re.I)

NONTOOL = re.compile(
    r"\b(?:certificates?|certs?|licen[sc]es?|api[- ]?keys?|keys?|tokens?|secrets?"
    r"|credentials?|cron|crontab|systemd|units?|entr(?:y|ies)|configs?|configuration"
    r"|services?|daemons?|hooks?|webhooks?)\b", re.I)

INSTALL = re.compile(
    r"\b(?:pip3?|uv pip|uv tool|pipx|conda|mamba|npm|pnpm|yarn|cargo|gem|tlmgr"
    r"|apt(?:-get)?|apk|dnf|yum|brew|pacman)\s+(?:-\S+\s+)*(?:install|add)\b"
    r"|\binstall\.packages\s*\(|\bpak::pak\s*\(|\bpak::pkg_install\s*\("
    r"|\bremotes::install_\w+\s*\(|\bquarto install\b|\bjuliaup\b"
    r"|\bPkg\.add\s*\(|\btinytex::install", re.I)
SCRIPT = re.compile(r"\b(?:startup|start-up|setup|set-up)[ -]script\b", re.I)


def turn_installs(path):
    """Install commands the agent ran since the last real user prompt."""
    found = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                content = (m.get("message") or {}).get("content") or m.get("content")
                if m.get("type") == "user" or m.get("role") == "user":
                    is_result = isinstance(content, list) and any(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content)
                    if not is_result:
                        found = []
                    continue
                if not isinstance(content, list):
                    continue
                for b in content:
                    if (isinstance(b, dict) and b.get("type") == "tool_use"
                            and b.get("name") == "Bash"):
                        cmd = (b.get("input") or {}).get("command") or ""
                        if INSTALL.search(cmd):
                            found.append(cmd.strip().splitlines()[0][:100])
    except Exception:
        return []
    return found


def excuse(text):
    """The excusing sentence, unless the reply also says it installed the tool.

    The fix is usually the next sentence ("X was missing. I installed it and
    reran."), so FIXED is checked against the whole reply.
    """
    if FIXED.search(text):
        return None
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if EXCUSE.search(sentence) and not nontool_subject(sentence):
            return sentence.strip()[:160]
    return None


def nontool_subject(sentence):
    """True when the clause holding MISSING names a certificate, key or the like.

    Words after the clause do not count, and a tool noun in it wins."""
    m = re.search(MISSING, sentence, re.I)
    if not m:
        return False
    head = re.split(r"\b(?:because|since|as|so|but|and)\b|[,;:]", sentence[:m.start()], flags=re.I)[-1]
    clause = head + " " + m.group(0)
    return bool(NONTOOL.search(clause)) and not re.search(TOOL, clause, re.I)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        texts = _sibling().last_visible_texts(path)
    except Exception:
        return 0
    if not texts:
        return 0
    text = texts[0]
    notes = []
    hit = excuse(text)
    if hit:
        notes.append(
            f"Your reply says work was skipped because a tool is missing: "
            f"\"{hit}\". Install it (pip, uv, apt, install.packages, tinytex, ...) "
            "and run the work (Ezra, 2026-11-02: \"no excuses; always install "
            "what you need\"). If it truly cannot be installed, say what you tried.")
    installs = turn_installs(path)
    if installs and not SCRIPT.search(text):
        notes.append(
            f"This turn installed something ({installs[0]!r}). If future cloud "
            "sessions need it, tell Ezra to edit the cloud startup script and "
            "give him the FULL revised script (read the current one first); if "
            "not worth adding, say so in a clause (Ezra, 2026-11-02).")
    if not notes:
        return 0
    key = hashlib.sha256(("|".join(notes) + text).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-toolgap-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass
    print(stop_notice(payload, " ".join(notes) +
                      " See shared/workflow/growth-mindset.md.",
                      "flag-tool-gap-handling"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
