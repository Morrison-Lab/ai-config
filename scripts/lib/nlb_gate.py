"""Load CI's check-new-line-breaks checker and emit lines it would accept.

The local reformatter (`scripts/semantic-line-breaks.py`) and CI's
`new-line-breaks` job used to be two implementations of one convention.
They drifted: a semicolon is not a sentence boundary, so the reformatter
joined a clause pair onto one line and CI rejected it (ai-config#2085).

Agreement here is by construction, not by matching predicates by hand:

- `.github/workflows/validate.yml` pins
  `Morrison-Lab/gha/check-new-line-breaks@<sha>`.
- `scripts/vendor/gha-check-new-line-breaks.py` is that script at that SHA.
- `scripts/vendor/gha-check-new-line-breaks.pin` records that SHA and
  the sha256 of the vendored bytes.
- Loading refuses to proceed if either disagrees with `validate.yml` or
  with the file on disk.

Bump the action pin, then run `python3 scripts/sync-nlb-checker.py`.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
VENDOR_PY = SCRIPTS_DIR / "vendor" / "gha-check-new-line-breaks.py"
VENDOR_PIN = SCRIPTS_DIR / "vendor" / "gha-check-new-line-breaks.pin"
VALIDATE_YML = REPO_ROOT / ".github" / "workflows" / "validate.yml"

# The composite action this repo pins. A comment in validate.yml names an
# older SHA; the capture is a full 40-char object id on a `uses:` line so
# that comment cannot match.
_USES_RE = re.compile(
    r"(?m)^\s+uses:\s+Morrison-Lab/gha/check-new-line-breaks@([0-9a-f]{40})\b"
)

_CHECKER: ModuleType | None = None


class NLBPinError(RuntimeError):
    """The vendored checker is not the script CI runs."""


class NLBSplitError(RuntimeError):
    """The gate flagged a line this loader could not split."""


def parse_ci_nlb_sha(validate_yml: Path | None = None) -> str:
    """Return the 40-char SHA `validate.yml` pins for the NLB action."""
    path = VALIDATE_YML if validate_yml is None else validate_yml
    text = path.read_text(encoding="utf-8")
    matches = _USES_RE.findall(text)
    if not matches:
        raise NLBPinError(
            f"{path}: no `uses: Morrison-Lab/gha/check-new-line-breaks@<40-char-sha>` line"
        )
    unique = set(matches)
    if len(unique) > 1:
        raise NLBPinError(
            f"{path}: multiple NLB action SHAs pinned: {sorted(unique)}"
        )
    return matches[0]


def read_vendor_pin(pin_path: Path | None = None) -> str:
    """Return the git SHA recorded next to the vendored checker.

    The pin file is two lines: the 40-char object id, then the sha256 of
    the vendored script at that id. `assert_pin_matches_ci` checks both.
    """
    path = VENDOR_PIN if pin_path is None else pin_path
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines or not re.fullmatch(r"[0-9a-f]{40}", lines[0]):
        raise NLBPinError(f"{path}: expected a 40-char SHA on line 1, got {lines[:1]!r}")
    return lines[0]


def read_vendor_sha256(pin_path: Path | None = None) -> str:
    """Return the content hash recorded next to the vendored checker."""
    path = VENDOR_PIN if pin_path is None else pin_path
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) < 2 or not re.fullmatch(r"[0-9a-f]{64}", lines[1]):
        raise NLBPinError(
            f"{path}: expected a 64-char sha256 on line 2, got {lines[1:2]!r}"
        )
    return lines[1]


def write_vendor_pin(git_sha: str, content_sha256: str, pin_path: Path | None = None) -> None:
    """Write the two-line pin file (`<git-sha>\\n<sha256>\\n`)."""
    path = VENDOR_PIN if pin_path is None else pin_path
    path.write_text(f"{git_sha}\n{content_sha256}\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    """Return the sha256 hex digest of `path`'s bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_pin_matches_ci(
    validate_yml: Path | None = None,
    pin_path: Path | None = None,
    vendor_py: Path | None = None,
) -> str:
    """Fail if the vendor copy is not the script CI runs.

    Two checks, both required:

    - the pin's git SHA equals the `uses:` SHA in `validate.yml`
    - the pin's sha256 equals the vendored file's bytes

    The first catches a bumped action pin with a stale vendor copy.
    The second catches a hand-edit of the vendored file that would
    otherwise be a silent second implementation.
    """
    ci = parse_ci_nlb_sha(validate_yml)
    pin = read_vendor_pin(pin_path)
    if ci != pin:
        raise NLBPinError(
            f"vendored NLB checker pin {pin} does not match validate.yml "
            f"pin {ci}. Run `python3 scripts/sync-nlb-checker.py` after "
            "bumping the action pin."
        )
    expected = read_vendor_sha256(pin_path)
    vendor = VENDOR_PY if vendor_py is None else vendor_py
    actual = file_sha256(vendor)
    if actual != expected:
        raise NLBPinError(
            f"{vendor}: sha256 {actual} does not match pin {expected}. "
            "Do not hand-edit the vendored checker; run "
            "`python3 scripts/sync-nlb-checker.py`."
        )
    return ci


def load_nlb_checker(
    path: Path | None = None,
    *,
    check_pin: bool = True,
) -> ModuleType:
    """Import `check-new-line-breaks.py` at the SHA CI pins.

    `NLB_CHECKER_PATH` overrides the vendored file (tests). The pin check
    is skipped under that override, because a stub is not the CI script
    and should not have to pretend to be.
    """
    global _CHECKER
    override = os.environ.get("NLB_CHECKER_PATH", "").strip()
    if path is None and override:
        path = Path(override)
        check_pin = False
    if path is None:
        if _CHECKER is not None:
            return _CHECKER
        path = VENDOR_PY
        if check_pin:
            assert_pin_matches_ci()
    if not path.is_file():
        raise NLBPinError(f"NLB checker not found: {path}")
    spec = importlib.util.spec_from_file_location("gha_check_new_line_breaks", path)
    if spec is None or spec.loader is None:
        raise NLBPinError(f"could not load NLB checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gha_check_new_line_breaks"] = module
    spec.loader.exec_module(module)
    if path == VENDOR_PY and override == "":
        _CHECKER = module
    return module


def _mask_non_prose(text: str, checker: ModuleType) -> str:
    """Blank out markup the gate's `strip_inline_markup` removes, keeping offsets."""

    def blank(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    text = checker._CODE_SPAN_RE.sub(blank, text)
    text = checker._LINK_TARGET_RE.sub(blank, text)
    for pattern in (
        checker._AUTOLINK_RE,
        checker._BARE_URL_RE,
        checker._ENTITY_RE,
    ):
        text = pattern.sub(blank, text)
    return text


def split_clauses(text: str, checker: ModuleType | None = None) -> list[str]:
    """Split `text` after each interior prose semicolon.

    Semicolons inside constructs `strip_inline_markup` removes (code spans,
    URLs, entities, link targets) are ignored, matching the gate.
    The semicolon stays on the line it ends, which is where a SemBr break
    belongs.
    """
    if checker is None:
        checker = load_nlb_checker()
    masked = _mask_non_prose(text, checker)
    split_at = [
        i
        for i, ch in enumerate(masked)
        if ch == ";" and 0 < i < len(masked) - 1
    ]
    if not split_at:
        return [text]
    pieces: list[str] = []
    start = 0
    for i in split_at:
        piece = text[start : i + 1].strip()
        if piece:
            pieces.append(piece)
        start = i + 1
    tail = text[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces or [text]


def emit_gate_clean(content: str, checker: ModuleType | None = None) -> list[str]:
    """Return one or more lines `classify_line` accepts.

    Sentence splits come from the gate's `split_sentences`. Clause splits
    come from `split_clauses` after the gate's `classify_line` returns
    `clause`. Recurses until every piece is clean, or raises if a flag
    remains with no split.
    """
    if checker is None:
        checker = load_nlb_checker()
    content = content.strip()
    if not content:
        return []
    reason = checker.classify_line(content)
    if reason is None:
        return [content]
    if reason == "sentence":
        pieces = checker.split_sentences(content)
        if len(pieces) <= 1:
            raise NLBSplitError(
                "check-new-line-breaks classified a sentence break but "
                f"split_sentences returned {pieces!r} for {content!r}"
            )
        out: list[str] = []
        for piece in pieces:
            out.extend(emit_gate_clean(piece, checker))
        return out
    if reason == "clause":
        pieces = split_clauses(content, checker)
        if len(pieces) <= 1:
            raise NLBSplitError(
                "check-new-line-breaks classified a clause break but "
                f"no semicolon split was found: {content!r}"
            )
        out = []
        for piece in pieces:
            out.extend(emit_gate_clean(piece, checker))
        return out
    raise NLBSplitError(f"unknown classify_line reason {reason!r} for {content!r}")
