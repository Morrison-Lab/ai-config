"""The text of each verified decision-card answer in a transcript (ai-config#5839).

Ezra, 2026-11-18: "you're asking for too much work from me". Threads asked him to type
"sweep" or "open the PR in <repo>" right after he had tapped a decision card that chose
exactly that, because the PR hooks read only typed words. A card tap is his answer to the
card's question, with the standing of a reply he wrote, so the hooks that gate an act on
the user's words count it as his word for the act the card named.

A tap counts only when the platform vouches for it:

- the cloud wake for a tap: `<wake reason="decision-chosen">` whose principal trigger
  message reads `Chose "<option>" on the decision card asking "<question>"`, beside the
  platform's note that it verified the tap came from the member's own client; or
- a coordinator relay's `<cited author="user">` entry with that same body, which the
  server copies from the member's message (a relay's `<note>` never counts).

When the transcript also holds the `request_decision` call that posted the card (matched by
the `message_id` its result returned and the wake's `decision_id`), the chosen option's
consequence line is added, since that line is usually where the card names the act.

An option that declines (No, Not now, Skip, Stop, Later, File it, Wait, Hold, Cancel) yields
nothing: choosing it is not a request for the act. This module never feeds a merge grant:
the mwc gates read typed words only, by design.
"""
import html
import json
import re

# A tap wake is top-level: one quoted inside another wake (a PR comment in an external-event wake) is not
# one. The harness may put a line before it ("A message arrived in the bound thread while you were working:").
TAP_WAKE = re.compile(r'(?:\A|\n)\s*<wake\b[^>]*\breason="decision-chosen"[^>]*>(.*?)</wake>', re.S)
PRINCIPAL = re.compile(
    r'<message\b(?=[^>]*\bfrom="human")(?=[^>]*\btrust="principal")'
    r'(?=[^>]*\btrigger="true")[^>]*>(.*?)</message>', re.S)
VERIFIED = re.compile(r"platform verified the tap came from that member", re.I)
DECISION_ID = re.compile(r"<system-note>\s*decision_id=([\w-]+)\s*</system-note>")
OPTION_INDEX = re.compile(r"<system-note>\s*option_index=(\d+)\s*</system-note>")
RELAY = re.compile(r"<coordinator-relay\b.*?</coordinator-relay>", re.S)
NOTE = re.compile(r"<note\b[^>]*>.*?</note>", re.S)
CITED = re.compile(r'<cited\b(?=[^>]*\bauthor="user")[^>]*>(.*?)</cited>', re.S)
CHOSE = re.compile(r'\A\s*Chose "(.+?)" on the decision card asking "(.+)"\s*\Z', re.S)
DECLINE = re.compile(
    r"\A\W*(?:no\b|not\b|none\b|don'?t\b|do\s+not\b|skip|stop|later\b|wait|hold|cancel|"
    r"leave\b|keep\s+(?:it\s+)?as\b|file\b|defer)", re.I)
REQUEST_DECISION = re.compile(r"request_decision\Z")


def _chose(body):
    """(option, question) from a card-answer body, or None."""
    m = CHOSE.match(html.unescape(body))
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def answers_in_prompt(prompt):
    """[(option, question, decision_id or None, option_index or None)] in one prompt's text."""
    found = []
    for wake in TAP_WAKE.finditer(prompt or ""):
        before = prompt[:wake.start()]
        if len(re.findall(r"<wake\b", before)) != len(re.findall(r"</wake>", before)):
            continue  # nested inside another wake
        inner = wake.group(1)
        if not VERIFIED.search(inner):
            continue
        did, idx = DECISION_ID.search(inner), OPTION_INDEX.search(inner)
        for body in PRINCIPAL.findall(inner):
            pair = _chose(body)
            if pair:
                found.append((*pair, did and did.group(1), idx and int(idx.group(1))))
    for relay in RELAY.finditer(prompt or ""):
        for body in CITED.findall(NOTE.sub(" ", relay.group(0))):
            pair = _chose(body)
            if pair:
                found.append((*pair, None, None))
    return found


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(b.get("content")) if b.get("type") == "tool_result" else str(b.get("text") or "")
                         for b in content if isinstance(b, dict))
    return ""


def _prompt(content):
    """A user record's prompt text; "" for a record holding a tool result, which the agent can fill."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list) or any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return ""
    return "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def card_text(option, question, consequence=""):
    """The words a tap stands for, or "" when the option declines."""
    if DECLINE.match(option):
        return ""
    return " ".join(p for p in (option + ".", question, consequence) if p).strip()


def answers_in_record(rec, cards):
    """Card-answer texts in one transcript record; `cards` maps a card's message_id to its input."""
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
    out = []
    for option, question, did, idx in answers_in_prompt(_prompt(msg.get("content"))):
        consequence = ""
        opts = (cards.get(did) or {}).get("options") if did else None
        if isinstance(opts, list) and idx is not None and idx < len(opts) and isinstance(opts[idx], dict):
            if str(opts[idx].get("label") or "").strip() == option:
                consequence = str(opts[idx].get("consequence") or "")
        text = card_text(option, question, consequence)
        if text:
            out.append(text)
    return out


def track_cards(rec, pending, cards):
    """Record request_decision calls (`pending`: tool_use id -> input) and, from their results,
    the message_id each card was posted as (`cards`: message_id -> input)."""
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_use" and REQUEST_DECISION.search(str(b.get("name") or "")):
            pending[b.get("id")] = b.get("input") if isinstance(b.get("input"), dict) else {}
        elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
            m = re.search(r'"message_id"\s*:\s*"([\w-]+)"', _text(b.get("content")))
            if m:
                cards[m.group(1)] = pending.pop(b.get("tool_use_id"))


def transcript_answers(path):
    """Every verified card-answer text in the transcript at `path`, oldest first."""
    pending, cards, out = {}, {}, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            track_cards(rec, pending, cards)
            if rec.get("type") == "user" and not rec.get("isMeta"):
                out += answers_in_record(rec, cards)
    return out
