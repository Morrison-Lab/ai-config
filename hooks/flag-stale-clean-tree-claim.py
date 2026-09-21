#!/usr/bin/env python3
"""Stop-hook guard: warn on clean-working-tree claims after path-writing git commands.

Running git commands that write or stage paths -- such as:
    git checkout <ref> -- <path>
    git checkout <ref> <path>
    git restore <path> / git restore --source=<ref> <path>
    git stash pop / git stash apply
    git apply <patch>
    git cherry-pick -n / git revert -n

writes or stages changes in the working directory and index. If a session runs
one of these commands and subsequently declares a "clean working tree", "nothing
uncommitted", or a "clean stopping point" without an intervening `git status`
or `git diff` reading, the claim is stale and risks leaving uncommitted or
staged files behind (ai-config#3821).

WARNS, never blocks: a clean-tree assertion may be accurate (e.g. if the checkout
restored identical bytes), and the corrective action is a single `git status`.

Fails OPEN on any parse or import trouble, and fires at most once per distinct
reply message (sentinel keyed by content hash).
"""
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(HERE)

# Try importing fences.strip_code to ignore code blocks and backticks.
try:
    lib_dir = os.path.join(REPO_ROOT, "scripts", "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from fences import strip_code  # type: ignore
except Exception:
    strip_code = None

if strip_code is None:
    def strip_code(text: str) -> str:
        # Fallback: strip fenced blocks and inline code spans
        t = re.sub(r"```[\s\S]*?```", " ", text)
        t = re.sub(r"`[^`\n]+`", " ", t)
        return t

# Clean working tree assertion phrases
ASSERT_PATTERNS = [
    r"\bworking\s+(?:tree|directory)\s+(?:is\s+)?clean\b",
    r"\bclean\s+working\s+(?:tree|directory)\b",
    r"\bnothing\s+(?:uncommitted|to\s+commit)\b",
    r"\bclean\s+stopping\s+point\b",
    r"\bclean\s+stop\b",
    r"\bno\s+uncommitted\s+changes\b",
]
RX_ASSERT = re.compile("|".join(ASSERT_PATTERNS), re.I)

# Negation words that qualify or deny a clean working tree claim in the same clause
RX_NEGATION = re.compile(
    r"\b(?:not|never|no|isn't|aren't|wasn't|weren't|cannot|unable|hardly)\b|n['\u2019]t\b",
    re.I,
)

# Clause separators
RX_CLAUSE_BREAK = re.compile(
    r"[.!?;]|\n|--|[\u2013\u2014]|\b(?:but|however|though|although|while|whereas)\b",
    re.I,
)

# Status/diff readings that refresh knowledge of the working tree
RX_STATUS_QUERY = re.compile(
    r"\bgit\s+(?:-[^\s]+\s+[^\s]+\s+)*(?:status|diff)\b",
    re.I,
)


def is_path_writing_git_cmd(cmd: str) -> bool:
    """Return True if cmd is a git command that writes/stages paths in index or tree."""
    if not cmd:
        return False
    m = re.search(
        r"\bgit\s+(?:-[^\s]+\s+[^\s]+\s+)*(checkout|restore|stash|apply|cherry-pick|revert|merge)\b(.*)",
        cmd,
        re.I,
    )
    if not m:
        return False

    subcmd = m.group(1).lower()
    rest = m.group(2).strip()

    if subcmd in ("restore", "apply"):
        return True
    if subcmd == "stash":
        return bool(re.search(r"\b(?:apply|pop)\b", rest, re.I))
    if subcmd in ("cherry-pick", "revert", "merge"):
        return bool(re.search(r"(?:^|\s)(?:-[^\s]*n|--no-commit)\b", rest, re.I))
    if subcmd == "checkout":
        # Branch creation/switch flags (-b, -B) do not write arbitrary paths from a ref
        if re.search(r"(?:^|\s)-[bB]\b", rest):
            return False
        # If '--' is present, pathspecs follow
        if re.search(r"(?:^|\s)--(?:$|\s)", rest):
            return True
        # Positional arguments (ignoring options like -q, --quiet, -f, --force, --detach)
        tokens = [t for t in rest.split() if not t.startswith("-")]
        # Two or more positional tokens (e.g. `git checkout origin/main website/`) is a ref + path checkout
        if len(tokens) >= 2:
            return True
        return False

    return False


def find_unnegated_claim(text: str):
    """Find an unnegated assertion of a clean working tree in visible prose."""
    prose = strip_code(text)
    # Check each sentence/line
    for raw_line in prose.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Check clauses
        clauses = RX_CLAUSE_BREAK.split(line)
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            m = RX_ASSERT.search(clause)
            if not m:
                continue
            # Check for negation before the match inside this clause
            prefix = clause[:m.start()]
            if RX_NEGATION.search(prefix):
                continue
            # Match is valid and unnegated
            return m
    return None


def scan_transcript(path: str):
    """Scan transcript for path-writing commands, status queries, and final text."""
    last_path_write_idx = -1
    last_path_write_cmd = ""
    last_status_read_idx = -1
    text = ""
    i = 0

    if not path or not os.path.exists(path):
        return last_path_write_idx, last_path_write_cmd, last_status_read_idx, text

    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                m = json.loads(line)
            except Exception:
                continue

            role = m.get("type") or m.get("role")
            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []

            # Antigravity tool calls
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL" or "tool_calls" in m:
                for tc in m.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        args = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                        cmd = str(args.get("CommandLine") or args.get("command") or args.get("cmd") or args.get("script") or "")
                        if is_path_writing_git_cmd(cmd):
                            last_path_write_idx = i
                            last_path_write_cmd = cmd
                        if RX_STATUS_QUERY.search(cmd):
                            last_status_read_idx = i

            # Antigravity text content
            if m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                raw_content = m.get("content")
                if isinstance(raw_content, str) and raw_content.strip():
                    text = raw_content

            # Claude Code blocks
            if isinstance(blocks, list):
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        inp = b.get("input") or {}
                        cmd = str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or "")
                        if is_path_writing_git_cmd(cmd):
                            last_path_write_idx = i
                            last_path_write_cmd = cmd
                        if RX_STATUS_QUERY.search(cmd):
                            last_status_read_idx = i
                    elif b.get("type") == "text" and role == "assistant":
                        if b.get("text", "").strip():
                            text = b["text"]
            elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                text = blocks

    return last_path_write_idx, last_path_write_cmd, last_status_read_idx, text


def already_warned(text: str) -> bool:
    """Return True if a warning was already emitted for this exact message text."""
    try:
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        sentinel = os.path.join(tempfile.gettempdir(), f"stale-clean-tree-{h}.sentinel")
        if os.path.exists(sentinel):
            return True
        with open(sentinel, "w", encoding="utf-8") as f:
            f.write("1")
    except Exception:
        pass
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    try:
        last_write_idx, last_write_cmd, last_status_idx, text = scan_transcript(path)
    except Exception:
        return 0

    if not text:
        return 0

    # No path-writing command ran, or status was checked after the last path write
    if last_write_idx < 0 or last_status_idx > last_write_idx:
        return 0

    hit = find_unnegated_claim(text)
    if not hit:
        return 0

    if already_warned(text):
        return 0

    claim = hit.group(0).strip()
    cmd_snippet = last_write_cmd.strip().split("\n")[0]
    if len(cmd_snippet) > 60:
        cmd_snippet = cmd_snippet[:57] + "..."

    warning = (
        f"Your message asserts a clean working tree -- \"{claim}\" -- but a "
        f"path-writing git command (`{cmd_snippet}`) ran after the last "
        "`git status` or `git diff` reading in this transcript.\n\n"
        "Commands like `git checkout <ref> -- <path>`, `git restore`, `git stash pop`, "
        "and `git apply` modify or stage files in the working directory and index. "
        "Run `git status` or `git diff` to verify that no unintended changes remain "
        "staged or uncommitted before declaring a clean stopping point (ai-config#3821)."
    )

    print(json.dumps({"systemMessage": warning}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
