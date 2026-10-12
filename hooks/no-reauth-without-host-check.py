#!/usr/bin/env python3
"""Stop-hook guard: telling the user to re-authenticate without checking the host.

## The incident

`glab api` was run from a folder that is not a git checkout, so glab fell back
to its default host (gitlab.com) instead of the self-hosted GitLab and replied
"Unauthenticated". The agent told the user the token had expired and had them
re-run `glab auth login`. The token was fine: `curl -H "PRIVATE-TOKEN: ..."
https://<host>/api/v4/user` returned 200. An authentication failure is evidence
about the host the CLI actually contacted, not about the credential
(ai-config#4387). The same applies to `gh` with `GH_HOST` or an enterprise host.

## What this warns about

The final assistant message asks the user to run `glab auth login` /
`gh auth login`, to re-authenticate, to log in again, or says a token or
credential expired / was revoked -- AND no tool call since the user's last
prompt checked the token against the intended host:

  * `curl ... https://<host>/api/v4/user` (or `/user`, or
    `/personal_access_tokens/self`),
  * `glab api --hostname <host> user`, or
  * `gh api --hostname <host> user`
    (a `GITLAB_HOST=` / `GH_HOST=` assignment on the same command counts for
    the host).

## Quoting

Fenced blocks and inline code spans are ignored, so a message that discusses
the phrase is not read as saying it -- with one exception. An instruction is
very often written as "run `glab auth login`", with the command in backticks,
and ignoring code spans would blind the guard to the exact message it exists
for. A code span or fenced block whose whole content is an auth-login command
is therefore kept as a marker, and only the imperative form in front of it
("run", "re-run", "try", "use") counts.

Known limit, accepted: the check only needs a host to be NAMED, so a
`curl https://gitlab.com/api/v4/user` counts even when the intended host is
another; the guard cannot know which host was intended.

Known limit, accepted: the credential-expiry reading needs the user's own
credential as its subject ("your token", "the token you ..."), so an expiry
statement phrased otherwise is not read; "is invalid" counts only at the end
of its sentence ("Your token is invalid."), "log in again" only with a
forge or token word in its sentence; and a login command followed by
"in the README / docs / CI / example" is read as describing, not asking.

## Why this warns rather than blocks

Sometimes re-authentication really is needed and the check was made some
other way (a browser, a different tool). The hook cannot tell, so it only adds
a system message, once per distinct message. Fails OPEN on any trouble.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "scripts", "lib")
try:
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from fences import CODE_SPAN_RE, FENCE_LINE, strip_code
    from transcript_meta import is_hook_feedback, is_skill_load_meta
except Exception as _exc:  # broken install; fail open and say so
    print(f"no-reauth-without-host-check: cannot load scripts/lib "
          f"({_exc}); not evaluating", file=sys.stderr)
    strip_code = None

AUTH_CMD = r"(?:glab|gh)\s+auth\s+login\b[^\n`]*"
RX_AUTH_CMD_ONLY = re.compile(r"^\s*\$?\s*" + AUTH_CMD + r"\s*$", re.I)
MARKER = "AUTHCMD"
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)

RX_CLAIM = re.compile(
    r"(?P<imper>\b(?:re-?run|run|execute|try|use)\W{0,3}(?:" + MARKER +
    r"|(?:glab|gh)\s+auth\s+login\b(?!\s+--with-token))"
    r"(?!\s+(?:in|inside|within|from|for|on)\s+(?:the\s+|our\s+|this\s+|a\s+)?"
    r"(?:readme|example|docs?|documentation|ci|pipelines?|tests?|scripts?|fixtures?)\b))"
    r"|(?:\b(?:please |you(?:'ll| will)? (?:need|have) to |you need to |"
    r"you must |can you |could you |will you |go ahead and |just )"
    r"re-?authenticat\w*)"
    r"|(?:\bre-?authenticat(?:e|ion)\b[^.\n]{0,40}\b(?:required|needed|necessary)\b)"
    r"|(?P<relogin>\b(?:log|sign) ?in again\b)"
    r"|(?P<expiry>\b(?:your\s+(?:[\w-]+\s+){0,3}(?:token|credentials?|pat)"
    r"|the\s+(?:[\w-]+\s+){0,2}(?:token|credentials?|pat)\s+you)\b"
    r"[^.\n]{0,30}\b(?:expired|(?:been|was|were|got|is|are) revoked|gone stale|is invalid\b(?=\s*(?:[.!?;]|$)))\b)",
    re.I,
)
# The expiry arm is about the USER'S OWN credentials ("your GitLab token",
# "the token you gave me"): "the login page expired", "the CI token was
# revoked" and a fixture's "token expired" describe something else.
# Text before a bare/backticked login command that makes it a request to the
# user: nothing, an opener clause ("To fix this,"), polite words, or a modal
# addressed to "you". "Tests run gh auth login" and "warns when you run ..."
# describe rather than ask.
RX_ADDRESSED_PREFIX = re.compile(
    r"^\s*(?:[^,:;]{0,60}[,:;]\s*)?(?:(?:please|now|then|just|first|next|also|and|so)\s){0,3}"
    r"(?:you\s+(?:can|could|should|will\s+need\s+to|need\s+to|must|have\s+to)\s+"
    r"|(?:can|could|will)\s+you\s+|go\s+ahead\s+and\s+)?$", re.I)
# "log in again" is about the forge only with forge context in its sentence:
# "log in again to the portal" or a dashboard's session timeout is not.
RX_LOGIN_CONTEXT = re.compile(
    r"\b(?:glab|gh|gitlab|github|token|credentials?|pat)\b", re.I)
# A claim that is negated or conditional ("has not expired", "if the token
# expired") is not an assertion that it did.
RX_NEGATED_BEFORE = re.compile(
    r"(?:\bnot|n['\N{RIGHT SINGLE QUOTATION MARK}]t|\bnever|\bno longer|\bif|\bwhether|\bunless|"
    r"\bin case|\bcheck(?:ing)? (?:if|whether))\s+(?:\w+\s+){0,4}$", re.I)
# A sentence that OPENS with a conditional ("If glab says X, run ...").
RX_CONDITIONAL_OPENING = re.compile(r"^\s*(?:if|unless|whether|should|in case)\b", re.I)
# A sentence ends at a newline or at terminal punctuation followed by
# whitespace, so the dots inside a hostname (gitlab.com) do not end one.
RX_SENTENCE_END = re.compile(r"\n|[.!?]+(?=\s)")
RX_NEGATED_INSIDE = re.compile(r"\b(?:not|never|n['\N{RIGHT SINGLE QUOTATION MARK}]t)\s+(?:\w+\s+)?(?:expired|revoked)", re.I)

RX_HOST_ASSIGN = re.compile(r"\b(?:GITLAB_HOST|GH_HOST)=\S+")
RX_CURL_USER = re.compile(
    r"https?://[^\s'\"]+/(?:api/v\d+/)?"
    r"(?:user|personal_access_tokens/self)(?![\w/-])", re.I)
RX_SEGMENT_SPLIT = re.compile(r"[;&|\n]+")


def _segment_verifies(seg):
    """glab/gh api, scoped to a host, whose positional endpoint is `user`."""
    m = re.search(r"\b(?:glab|gh)\s+api\b(.*)", seg)
    if not m:
        return False
    if not ("--hostname" in seg or RX_HOST_ASSIGN.search(seg)):
        return False
    return bool(re.search(
        r"(?:^|\s)['\"]?/?(?:api/v\d+/)?user['\"]?(?=\s|$)", m.group(1)))


WRAPPERS = {"sudo", "command", "time", "env", "nohup"}
RX_ASSIGN_TOKEN = re.compile(r"^[A-Za-z_]\w*=[^(]*$")
RX_HEAD_PREFIX = re.compile(r"^(?:[A-Za-z_]\w*=)?(?:\$\(|\(|`)?")


def _is_curl_segment(seg):
    """True when `curl` is the command word of SEG (not an argument of echo etc.)."""
    tokens = seg.split()
    while tokens and (RX_ASSIGN_TOKEN.match(tokens[0]) or tokens[0] in WRAPPERS):
        tokens.pop(0)
    if not tokens:
        return False
    head = RX_HEAD_PREFIX.sub("", tokens[0])
    return os.path.basename(head) == "curl"


def command_verifies_host(command):
    """True when COMMAND checks a token against a named host."""
    for seg in RX_SEGMENT_SPLIT.split(command):
        if _is_curl_segment(seg) and RX_CURL_USER.search(seg):
            return True
        if _segment_verifies(seg):
            return True
    return False


def _closes_fence(line, run):
    s = line.strip()
    return bool(s) and set(s) == {run[0]} and len(s) >= len(run)


def mark_auth_commands(text):
    """Replace code spans / fences that are just an auth-login command with MARKER."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        m = FENCE_LINE.match(lines[i].rstrip("\r"))
        if m:
            run = m.group("run")
            j = i + 1
            body = []
            while j < len(lines) and not _closes_fence(lines[j], run):
                body.append(lines[j])
                j += 1
            if body and all(RX_AUTH_CMD_ONLY.match(b) or not b.strip() for b in body) \
                    and any(b.strip() for b in body):
                out.append(MARKER)
            else:
                out.append("\n".join(lines[i:j + 1]))
            i = j + 1
            continue
        out.append(lines[i])
        i += 1
    joined = "\n".join(out)

    def _span(m):
        inner = m.group(0).strip("`")
        return MARKER if RX_AUTH_CMD_ONLY.match(inner) else m.group(0)

    return CODE_SPAN_RE.sub(_span, joined)


def _sentence_of(prose, start, end):
    """The sentence of PROSE containing the span [start, end)."""
    s_start = max(
        (b.end() for b in RX_SENTENCE_END.finditer(prose, 0, start)), default=0)
    after = RX_SENTENCE_END.search(prose, end)
    return prose[s_start:after.start() if after else len(prose)]


def find_claim(text):
    """The first reauthentication claim in TEXT (code-aware), or None."""
    prose = strip_code(mark_auth_commands(text))
    for m in RX_CLAIM.finditer(prose):
        sent_start = max(
            (b.end() for b in RX_SENTENCE_END.finditer(prose, 0, m.start())),
            default=0)
        prefix = prose[sent_start:m.start()]
        if (RX_NEGATED_BEFORE.search(prefix) or RX_CONDITIONAL_OPENING.search(prefix)
                or RX_NEGATED_INSIDE.search(m.group(0))):
            continue
        if m.group("imper") and not RX_ADDRESSED_PREFIX.search(prefix):
            continue
        if m.group("relogin") and not RX_LOGIN_CONTEXT.search(
                _sentence_of(prose, m.start(), m.end())):
            continue
        return m
    return None


def _blocks(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in (content or []) if isinstance(b, dict)]


def scan(path):
    """(final_message_text, verified_since_last_prompt)."""
    text = ""
    verified = False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type")
            if role == "user":
                if is_skill_load_meta(m) or is_hook_feedback(m):
                    continue
                if any(b.get("type") == "text" and b.get("text", "").strip()
                       for b in _blocks(m)):
                    verified = False  # a new real prompt starts a new turn
                    text = ""  # and an earlier turn's message is not this turn's
            elif role == "assistant":
                for b in _blocks(m):
                    btype = b.get("type")
                    if btype == "text" and b.get("text", "").strip():
                        text = b["text"]
                    elif btype == "tool_use":
                        inp = b.get("input") or {}
                        if REPLY_TOOL_RX.search(b.get("name") or ""):
                            payload = inp.get("text")
                            if isinstance(payload, str) and payload.strip():
                                text = payload
                        command = inp.get("command")
                        if isinstance(command, str) and command_verifies_host(command):
                            verified = True
    return text, verified


def main() -> int:
    if strip_code is None:
        return 0
    try:
        payload = json.load(sys.stdin)
        transcript = payload.get("transcript_path") or ""
        if not transcript:
            print("no-reauth-without-host-check: no transcript_path in hook "
                  "input; not evaluating", file=sys.stderr)
            return 0
        text, verified = scan(transcript)
    except Exception as exc:  # fail open, but say so
        print(f"no-reauth-without-host-check: cannot read transcript "
              f"({exc}); not evaluating", file=sys.stderr)
        return 0

    if not text or verified:
        return 0
    hit = find_claim(text)
    if hit is None:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-reauth-host-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w", encoding="utf-8"):
            pass
    except Exception:
        pass

    shown = hit.group(0).replace(MARKER, "glab/gh auth login").strip()
    print(json.dumps({
        "systemMessage": (
            f"Re-authentication claim without a host check: your message says "
            f"\"{shown}\", and nothing since the user's last prompt verified "
            "the token against the intended host. A CLI's \"Unauthenticated\" "
            "describes the host it contacted: glab outside a checkout falls "
            "back to gitlab.com, gh to github.com (ai-config#4387). Verify "
            "first: `curl -H \"PRIVATE-TOKEN: $T\" https://<host>/api/v4/user`, "
            "`glab api --hostname <host> user`, or `gh api --hostname <host> "
            "user`, then retract or restate the claim."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
