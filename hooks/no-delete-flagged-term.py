#!/usr/bin/env python3
"""PreToolUse guard: an edit deletes a technical term that check-term-links flags.

The user's standing rule (Ezra, 2026-11-20): "never remove technical terms
that get flagged as unlinked; always link them to a definition instead,
writing one if necessary". It was broken on lds#3017, where "finite" was
dropped from an exercise to quiet gha's `check-term-links`. Deleting the
word passes the check and loses the precision the term carried, so the
check's own green verdict cannot catch it; only the edit can.

For a Write, Edit or MultiEdit of a `.qmd` or `.md` file in a repository
whose workflows call gha's `check-term-links`, this hook:

1. simulates the file after the edit and diffs it line by line against the
   file on disk;
2. runs gha's `check-term-links.py` (at the ref the caller workflow pins,
   from the cache `no-push-with-failing-notes-checks.py` keeps) over the
   lines the edit replaces, with the caller's inputs and the prerequisite
   sites' terms when their caches exist;
3. denies the edit when a term the check flags there (`unlinked-first-use`
   or `no-definition`) appears in the replaced lines, the file holds fewer
   uses of it afterwards, and the replacement is a rewording of the old
   text (difflib ratio at least `REWORD_RATIO`) rather than a rewrite.

A pure deletion of lines and a wholesale rewrite pass, since neither is
dropping a word to quiet the check. A term moved elsewhere in the file
passes, since its count does not fall.

Fails open, with the reason on stderr, when the repository has no
check-term-links caller, gha cannot be fetched, or the check errors.
Clearable with `ALLOW_DELETE_FLAGGED_TERM=1` in the environment for a
deletion the user asked for in words. Tracked as ai-config#6009.
"""
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from sibling import load_sibling
except ImportError as _exc:
    print(f"no-delete-flagged-term: cannot load scripts/lib/sibling.py ({_exc}); "
          "not evaluating", file=sys.stderr)
    load_sibling = None

SUFFIXES = (".qmd", ".md")
RULES = ("unlinked-first-use", "no-definition")
REWORD_RATIO = 0.5
TIMEOUT = 30
BYPASS_VAR = "ALLOW_DELETE_FLAGGED_TERM"
FINDING = re.compile(r"^\s+(?P<path>.+?):(?P<line>\d+): \[(?P<rule>[\w-]+)\] (?P<msg>.*)$")
QUOTED = re.compile(r"'([^']+)'")


def _notes_checks():
    if load_sibling is None:
        return None
    return load_sibling(__file__, "no-push-with-failing-notes-checks.py",
                        "no_push_with_failing_notes_checks")


def after_text(tool: str, ti: dict, before: str) -> str | None:
    """The file's text once the edit applies, or None when it cannot apply."""
    if tool == "Write":
        return ti.get("content")
    edits = ti.get("edits") if tool == "MultiEdit" else [ti]
    text = before
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if not old or old not in text:
            return None
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def replaced_blocks(before: str, after: str):
    """(old line numbers, old text, new text) for each replaced run of lines."""
    a, b = before.splitlines(), after.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "replace":
            yield range(i1 + 1, i2 + 1), "\n".join(a[i1:i2]), "\n".join(b[j1:j2])


def count(term: str, text: str) -> int:
    return len(re.findall(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", text, re.IGNORECASE))


def flagged(git_root: str, rel: str, lines: set, notes) -> list[tuple[int, str]] | None:
    """(line, term) for each check-term-links finding on `lines` of `rel`; None on failure."""
    calls = [c for c in notes.find_calls(git_root) if c["name"] == "check-term-links"
             and c.get("kind") != "bundled"]
    if not calls:
        return None
    call = calls[0]
    gha = notes.ensure_gha(call["ref"])
    if not gha:
        print("no-delete-flagged-term: no gha checkout; not evaluating", file=sys.stderr)
        return None
    spec = notes.CHECKS["check-term-links"]
    env = {k: v for k, v in os.environ.items() if not k.startswith(spec["prefix"])}
    for k, v in call["inputs"].items():
        if spec["inputs"].get(k):
            env[spec["prefix"] + spec["inputs"][k]] = v
    env["TERM_LINKS_FAIL"] = "false"
    dirs = []
    for slug in notes.terms_from(git_root, call):
        cached = os.path.join(notes.TERMS_CACHE, slug.replace("/", "__"))
        if os.path.isdir(cached):
            dirs.append(cached)
    if dirs:
        env["TERM_LINKS_TERMS_DIRS"] = " ".join(dirs)
    hunk = [f"diff --git a/{rel} b/{rel}", f"--- a/{rel}", f"+++ b/{rel}"]
    for n in sorted(lines):
        hunk += [f"@@ -0,0 +{n},1 @@", "+x"]
    with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False, encoding="utf-8") as fh:
        fh.write("\n".join(hunk) + "\n")
        env["TERM_LINKS_DIFF_FILE"] = fh.name
    try:
        proc = subprocess.run([sys.executable, os.path.join(gha, spec["script"])],
                              capture_output=True, text=True, cwd=git_root, env=env,
                              timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"no-delete-flagged-term: check-term-links did not run ({exc})", file=sys.stderr)
        return None
    finally:
        os.unlink(env["TERM_LINKS_DIFF_FILE"])
    found = []
    for line in proc.stdout.splitlines():
        m = FINDING.match(line)
        if not m or m.group("rule") not in RULES or m.group("path") != rel:
            continue
        q = QUOTED.search(m.group("msg"))
        if q:
            found.append((int(m.group("line")), q.group(1)))
    return found


def removed_terms(before: str, after: str, git_root: str, rel: str, notes) -> list[str]:
    blocks = [blk for blk in replaced_blocks(before, after)
              if blk[2].strip()
              and difflib.SequenceMatcher(None, blk[1], blk[2]).ratio() >= REWORD_RATIO]
    if not blocks:
        return []
    lines = {n for rng, _, _ in blocks for n in rng}
    hits = flagged(git_root, rel, lines, notes) or []
    out = []
    for n, term in hits:
        for rng, old, new in blocks:
            if n in rng and count(term, old) > count(term, new) \
                    and count(term, after) < count(term, before) and term not in out:
                out.append(term)
    return out


def main() -> int:
    if os.environ.get(BYPASS_VAR) == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    ti = payload.get("tool_input") or {}
    target = str(ti.get("file_path") or "")
    if not target.lower().endswith(SUFFIXES):
        return 0
    path = os.path.realpath(os.path.join(payload.get("cwd") or os.getcwd(), target))
    try:
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
    except OSError:
        return 0  # a new file deletes nothing
    after = after_text(tool, ti, before)
    if after is None:
        return 0
    notes = _notes_checks()
    if notes is None:
        return 0
    res = subprocess.run(["git", "-C", os.path.dirname(path), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return 0
    git_root = res.stdout.strip()
    rel = os.path.relpath(path, git_root).replace(os.sep, "/")
    try:
        terms = removed_terms(before, after, git_root, rel, notes)
    except Exception as exc:  # fail open, and say why
        print(f"no-delete-flagged-term: not evaluating ({exc})", file=sys.stderr)
        return 0
    if not terms:
        return 0
    named = ", ".join(f"'{t}'" for t in terms)
    reason = (
        f"This edit deletes {named} from `{os.path.basename(path)}`, and check-term-links "
        "flags that term as unlinked on the lines it rewords.\n\n"
        "Standing rule (Ezra, 2026-11-20): never remove a technical term that gets "
        "flagged as unlinked; link it to its definition instead, and write the "
        "definition if none exists (psw's defining-terms chapter, "
        "shared/writing/definition-crossrefs.md). Keep the term and link it, "
        "e.g. `[finite](sets.qmd#def-finite-set)`. If the user asked in words for "
        f"this deletion, the user can set {BYPASS_VAR}=1 for the session."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
