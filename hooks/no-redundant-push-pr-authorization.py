#!/usr/bin/env python3
"""Stop-hook guard: ordinary pushes and PRs do not need another permission ask.

The standing grant in ``memories/preferences.md`` already authorizes ordinary,
non-force pushes and opening or updating PRs/MRs.  It did not prevent a repeat
authorization ask on 2026-09-22 after a redundant copy of that grant was
removed, so the composition-time boundary needs its own guard.

This is deliberately narrower than ``flag-cop-out-offer.py``.  That hook warns
on many offers because authorization cannot be inferred from prose.  Here the
action is decidable: ordinary ``git push`` and opening a pull or merge request
are covered by the standing grant.  Merge and force-push questions are excluded
because they need explicit authorization under the merge and push safeguards.

The reader is imported from ``no-offer-to-file.py`` so project-thread reply
payloads, Antigravity transcripts, and code-fence stripping stay consistent.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile


HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name):
    """Import a hyphenated hook sibling, returning ``None`` on failure."""
    try:
        spec = importlib.util.spec_from_file_location("_sibling", os.path.join(HERE, name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


_offer = _sibling("no-offer-to-file.py")
last_assistant_text = getattr(_offer, "last_assistant_text", lambda path: "")
strip_code = getattr(_offer, "strip_code", lambda text: text)

# Ask shapes which specifically seek authorization for routine push/PR work.
# ``force-push`` is excluded below, and merge is never named here.
ACTION = r"(?:push(?:\s+(?:this|the|my|a)?\s*(?:branch|changes|commit))?|(?:create|open|update)\s+(?:a|the)?\s*(?:pull\s+request|merge\s+request|pr|mr))"
PATTERNS = [
    rf"\b(?:may|can|could|should|shall|would)\s+i\s+(?:go\s+ahead\s+and\s+)?{ACTION}\b[^?.!]*\?",
    rf"\b(?:do|would)\s+you\s+(?:want|like)\s+me\s+to\s+(?:go\s+ahead\s+and\s+)?{ACTION}\b",
    rf"\b(?:need|require|await|waiting\s+for)\s+(?:your\s+)?(?:approval|authorization|permission)\s+(?:to|before)\s+(?:i\s+)?{ACTION}\b",
]
RX = re.compile("|".join(PATTERNS), re.I)
FORCE_PUSH = re.compile(r"\bforce[-\s]?push\b", re.I)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text:
        return 0
    prose = strip_code(text)
    if FORCE_PUSH.search(prose):
        return 0
    hit = RX.search(prose)
    if not hit:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".push-pr-auth-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            "Do not ask again for authorization to perform routine push or PR/MR work: "
            f"\"{hit.group(0).strip()}\". The standing grant covers ordinary, "
            "non-force pushes and opening/updating PRs or MRs. Perform the work, "
            "then report it in the past tense.\n\n"
            "This guard intentionally does not cover merges or force-pushes; those "
            "still require their separate authorization and safety checks."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
