#!/usr/bin/env python3
"""Check that quoted section-title references still name a real heading.

check-links.py verifies that a relative markdown link *resolves* --- the
target file exists.  It cannot see a narrower kind of breakage: prose that
links to a file AND quotes a section title from it, e.g.

    recorded in [`claude-review-dispatch.md`](claude-review-dispatch.md)'s
    "`ai-config` never auto-reviews a PR on push"

The link resolves even after the target's heading is renamed, so the quoted
title silently goes stale and check-links.py stays clean forever.  This
script extracts every such quoted reference, resolves the linked file, and
checks whether the quote still names a real heading (or an informal bold
anchor -- see below) there.

Three reference shapes were found by grepping the corpus for how this idiom
is actually written (roughly 130 apostrophe-form hits, ~40 comma-form hits,
and 2 quoted-link-text hits at survey time); all three are checked:

  Form A  (apostrophe, universal):
      [text](target)'s "Quoted Title"
  Form A2 (comma, scoped -- see the FORM_A2 handling in find_references):
      See [text](target.cases.md), "Quoted Title"
  Form B  (quoted link text, universal):
      ["Quoted Title"](target)

A quote often does not spell out its target in full -- semantic line breaks
mean a long heading or bold lead gets truncated at whichever clause boundary
the citing prose needed, which can be the front ("A cancelled dispatch that
fired a" for a heading that continues "...failure webhook against the
superseded SHA"), the middle, or (after a colon) effectively the tail
("partial is worse than absent" for "## In a guard you ship: partial is
worse than absent").  So a quote is accepted if, after tolerant
normalization (backticks stripped, whitespace collapsed, case-folded), it is
a SUBSTRING of a real ATX heading, a paragraph-leading bold span
(`**Like this.**`), or a list item's own bold lead (`- **Like this:**`) in
the target file -- this corpus uses both bold conventions as informal
section anchors in the same idiom, and treating only `#`-headings as valid
targets makes those legitimate references false positives.

TEXT MATCHING ALONE IS NOT ENOUGH.  A quote that never named a heading in
the first place (an author paraphrasing a rule and putting quotes around the
paraphrase, e.g. "propose the fix, don't just name the issue" citing prose
that actually reads "...propose a fix...") is textually indistinguishable
from a quote that DID name a heading and was renamed away.  No amount of
matching cleverness resolves that -- it needs better evidence, not a better
pattern.  So when a quote does not match the target's CURRENT headings or
bold leads, this script does not conclude it is stale from that alone: it
walks the target's git history (following renames and content-preserving
splits via `git log --follow`) and asks whether the quote ever matched a
heading or bold lead in any earlier revision.  It is reported as a finding
ONLY if the historical search finds it -- i.e. only when the evidence
actually supports "this used to be true and now is not," never merely
"I cannot currently confirm this."  See HistoryIndex below for the mechanics,
the similarity threshold this repo's own split commits needed, and the
performance approach (git cat-file --batch, not one `git show` per
revision).

Two things this script cannot verify, by design:
  - A same-file reference with NO accompanying markdown link (pure prose,
    e.g. `claude-review-dispatch.md`'s own self-reference to "the end of
    this file") is out of scope entirely: requirement 2 of this checker's
    brief is to resolve the target via the accompanying link, and there is
    none to resolve.  THIS IS A KNOWN BLIND SPOT, not a covered case that
    happens to pass -- a clean run says nothing about link-less same-file
    references, and at least one real stale instance of exactly this shape
    has been found and fixed by hand rather than by this script.
  - Anything whose history cannot be read at all (not a git repository, git
    not installed, or a shallow clone whose fetch depth does not reach the
    revision that would prove the point) is reported separately as
    UNVERIFIED, never silently treated as clean -- see the shallow-clone
    handling below, which mirrors check-stale-records.py's
    `age_informative: false`.

Clean-room; convention noted in CREDITS.md.

Exit codes (see shared/workflow/fully-clean.md's three-way convention):
    0 -- clean: no CONFIRMED stale quoted references found (an unverified
         count, if any, is reported but does not by itself fail the check --
         same as check-stale-records.py's shallow-clone caveat, which is
         advisory rather than blocking)
    1 -- at least one confirmed stale quoted reference found
    2 -- usage or environment error
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import CODE_SPAN_RE, strip_fences  # noqa: E402

USAGE_EXIT = 2

ROOT = Path(__file__).resolve().parent.parent

SCAN_GLOBS = [
    "skills/**/*.md",
    "codex-skills/**/*.md",
    "commands/**/*.md",
    "docs/**/*.md",
    "memories/**/*.md",
    "references/**/*.md",
    "shared/**/*.md",
    "*.md",
]

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")

MAX_QUOTE_LEN = 400

# Form A: [text](target)'s "Quoted Title"  -- the possessive-apostrophe idiom.
FORM_A = re.compile(
    r"\[[^\]]*\]\((?P<target>[^)]+)\)'s\s+"
    r'"(?P<quote>[^"]{1,%d})"' % MAX_QUOTE_LEN
)

# Form A2: [text](target), "Quoted Title"  -- the comma idiom.  find_references
# below scopes a match to a target ending in ".cases.md", or to text
# immediately preceded by "See ", since an unscoped comma-plus-quote is
# common ordinary prose ("Per [x](y.md), \"some phrase\" means ...") that was
# never meant as a title citation at all.
FORM_A2 = re.compile(
    r"\[[^\]]*\]\((?P<target>[^)]+)\),\s+"
    r'"(?P<quote>[^"]{1,%d})"' % MAX_QUOTE_LEN
)

# Form B: ["Quoted Title"](target)  -- the quote IS the link text.
FORM_B = re.compile(
    r'\["(?P<quote>[^"]{1,%d})"\]\((?P<target>[^)]+)\)' % MAX_QUOTE_LEN
)

HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
# A paragraph-leading bold span: "**Like this sentence.**" possibly wrapped
# across a semantic line break, so DOTALL and a length cap rather than a
# single-line match.
BOLD_LEAD = re.compile(r"^\*\*(.{1,%d}?)\*\*" % MAX_QUOTE_LEN, re.M | re.S)
# A list-item's own bold lead: "- **Do:** ..." / "  - **403 caveat** ...".
# This corpus's Do/Don't and named-finding bullets consistently open with a
# bold clause right after the list marker; that clause is a structural
# anchor in the same idiom as a heading, but BOLD_LEAD (anchored to column 0)
# never sees it because a list marker and its indent come first.
LIST_BOLD_LEAD = re.compile(
    r"^[ \t]*[-*][ \t]+\*\*(.{1,%d}?)\*\*" % MAX_QUOTE_LEN, re.M | re.S
)

MIN_QUOTE_LEN = 4  # normalized characters; guards against a trivial substring

# --- git history parameters --------------------------------------------------
#
# git log --follow's rename/copy detection defaults to 50% content similarity
# (git's own -M default), which does NOT catch a content-preserving SPLIT: a
# heading moved out of a large file into a smaller new one dilutes the
# similarity ratio even though the moved content is identical.  The real case
# this layer exists for -- memories/claude-bot-workflows.md split into itself
# and memories/claude-review-dispatch.md in #1725 -- was measured directly:
# -M25% and above finds nothing (1 commit, the split itself); -M15% and below
# correctly follows back through the pre-split history (217 commits,
# including the four revisions that carried the real heading).  15% is used
# as the default: permissive enough to catch this repo's actual split
# pattern, at the accepted cost that a very low threshold can occasionally
# link two otherwise-unrelated files that happen to share a content fragment
# -- which is a low-probability coincidence here, since it would also need a
# heading string collision to produce a false "genuine" verdict, not just a
# spurious rename link.
FOLLOW_SIMILARITY = 15  # percent, git's -M<n>% for --follow rename detection

# Safety cap on how many revisions of one target's followed history get
# fetched.  Defensive rather than tuned to this repo: a file with a very long
# edit history (thousands of commits) should not make one target dominate a
# whole run.  git log lists newest-first, and the known real case's relevant
# revisions land within the first ~10 commits after the rename, so a cap this
# size is very unlikely to cut off a genuine match in practice -- but it CAN,
# for an old enough rename, and that limitation is reported (see
# HistoryIndex.capped_targets) rather than left silent.
MAX_HISTORY_REVISIONS = 500


def is_external(target: str) -> bool:
    return target.startswith(SKIP_PREFIXES) or "://" in target


def normalize(text: str) -> str:
    """Fold a quote or heading/bold-lead down to a comparable core string.

    Strips backticks (headings routinely wrap a code term in them, and a
    quote may or may not echo the backticks), and collapses all whitespace
    (a quote or heading can wrap across a semantic line break) to single
    spaces.  Comparison is a SUBSTRING test (see quote_matches below), so no
    punctuation trimming happens here: a quote is a verbatim truncation of
    the real text, not a reworded copy, and trimming could shift a boundary
    that was never actually ambiguous.
    """
    text = text.replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def quote_matches(quote: str, candidates) -> bool:
    """True if the normalized quote is a substring of any candidate.

    A quote is not always a PREFIX of the real text: semantic line breaks
    mean a long heading or bold lead gets truncated at whichever clause
    boundary the citing prose needed, which can be the front ("A cancelled
    dispatch that fired a" for a heading that continues), the middle, or
    (after a colon) effectively the tail ("partial is worse than absent" for
    "## In a guard you ship: partial is worse than absent").  A substring
    test covers all three without over-matching, since MIN_QUOTE_LEN still
    rules out a trivial two-or-three-character quote matching everything.
    """
    norm_quote = normalize(quote)
    if len(norm_quote) < MIN_QUOTE_LEN:
        return False
    return any(norm_quote in c for c in candidates)


def strip_fenced_blocks(text: str) -> str:
    """Blank fenced code blocks only, preserving line count.

    Fenced blocks are the one place a literal illustration of this repo's
    quote-reference idiom could appear and must not trip the checker.
    Inline code spans are deliberately NOT stripped here (contrast
    check-links.py, which strips both): a quoted title routinely echoes a
    backtick-wrapped term from the heading itself (e.g. "`ai-config` never
    auto-reviews..."), so blanking every inline span would destroy real
    quote content, not just code examples.  strip_fences() also preserves
    line count (blanks whole lines), which line-number reporting needs.
    """
    return strip_fences(text)


def in_single_code_span(text: str, start: int, end: int) -> bool:
    """True if [start, end) falls entirely inside one inline code span.

    The narrow case inline-code stripping exists for: a match that is
    itself a literal illustration of the pattern, written inside backticks
    rather than as real prose (e.g. a doc explaining the idiom by showing
    `[text](file.md)'s "Title"` as a one-line example).  Uses fences.py's
    own CODE_SPAN_RE rather than a second hand-rolled backtick matcher.
    """
    for m in CODE_SPAN_RE.finditer(text):
        if m.start() <= start and end <= m.end():
            return True
        if m.start() > end:
            break
    return False


def extract_headings(text: str) -> list[str]:
    return [normalize(h) for h in HEADING.findall(text)]


def extract_bold_leads(text: str) -> list[str]:
    return [normalize(b) for b in BOLD_LEAD.findall(text)] + [
        normalize(b) for b in LIST_BOLD_LEAD.findall(text)
    ]


def extract_anchors(text: str) -> set[str]:
    """Every normalized heading and bold-lead in one revision's text."""
    body = strip_fenced_blocks(text)
    return set(extract_headings(body)) | set(extract_bold_leads(body))


def resolve_target(referring_file: Path, target: str) -> Path | None:
    """Resolve a link target to a file path, or None if not a plain repo-relative file link."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split(" ", 1)[0]
    if not target or is_external(target):
        return None
    if "<" in target or ">" in target:
        return None
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:
        return None
    if "/" not in path_part and "." not in path_part:
        return None
    return (referring_file.parent / path_part).resolve()


class Reference:
    def __init__(
        self, referring_file: Path, line_no: int, quote: str, target: str,
        form: str,
    ):
        self.referring_file = referring_file
        self.line_no = line_no
        self.quote = quote
        self.target = target
        self.form = form


def line_number_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def find_references(md: Path, raw_text: str) -> list[Reference]:
    text = strip_fenced_blocks(raw_text)
    refs: list[Reference] = []

    for m in FORM_A.finditer(text):
        if in_single_code_span(text, m.start(), m.end()):
            continue
        refs.append(
            Reference(md, line_number_of(text, m.start()), m.group("quote"),
                       m.group("target"), "A")
        )

    for m in FORM_A2.finditer(text):
        if in_single_code_span(text, m.start(), m.end()):
            continue
        target = m.group("target").strip()
        preceding = text[max(0, m.start() - 5):m.start()]
        cases_target = re.split(r"[#?]", target, maxsplit=1)[0].endswith(
            ".cases.md"
        )
        see_prefix = preceding.endswith("See ")
        if not (cases_target or see_prefix):
            continue
        refs.append(
            Reference(md, line_number_of(text, m.start()), m.group("quote"),
                       target, "A2")
        )

    for m in FORM_B.finditer(text):
        if in_single_code_span(text, m.start(), m.end()):
            continue
        refs.append(
            Reference(md, line_number_of(text, m.start()), m.group("quote"),
                       m.group("target"), "B")
        )

    return refs


def scan_files(root: Path, globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    for glob in globs:
        for md in root.glob(glob):
            if md.is_file():
                seen.add(md.resolve())
    return sorted(seen)


# --- git history layer --------------------------------------------------------


def _run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd)] + args, capture_output=True, text=True
    )


def follow_history_pairs(
    toplevel: Path, rel_path: str, max_revisions: int = MAX_HISTORY_REVISIONS,
) -> list[tuple[str, str]] | None:
    """(commit, path-at-that-commit) pairs for rel_path's followed history.

    Newest first (git log's default order).  Uses one `git log --follow`
    call (not one call per commit): the commit list AND the per-commit path
    (which changes across a detected rename) both come out of this single
    invocation via --name-only, parsed from the "COMMIT <hash>" marker line
    this function's own --format inserts.  Returns None on any git error
    (caller treats that as "history unavailable" for this target, not as
    "history is empty").
    """
    result = _run_git(
        toplevel,
        [
            "log", "--follow", f"-M{FOLLOW_SIMILARITY}%",
            "--format=COMMIT %H", "--name-only",
            "--max-count", str(max_revisions),
            "--", rel_path,
        ],
    )
    if result.returncode != 0:
        return None
    pairs: list[tuple[str, str]] = []
    commit: str | None = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("COMMIT "):
            commit = line[len("COMMIT "):]
        elif commit is not None:
            pairs.append((commit, line))
            commit = None
    return pairs


def batch_fetch_blobs(toplevel: Path, specs: list[str]) -> dict[str, str]:
    """Fetch many '<commit>:<path>' blobs in ONE `git cat-file --batch` call.

    One `git show <commit>:<path>` subprocess per revision was measured at
    ~31ms each (process-spawn overhead dominates) -- 217 revisions of a
    single real target took 6.8s that way.  `git cat-file --batch` keeps one
    persistent process and streams every blob back over its own stdout,
    measured at 0.09s for the same 217 revisions: a ~75x speedup, and the
    reason no per-revision subprocess call exists anywhere in this module.
    Missing objects (the object does not exist, e.g. a bad spec) are simply
    absent from the returned dict rather than raising.
    """
    if not specs:
        return {}
    proc = subprocess.Popen(
        ["git", "-C", str(toplevel), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    data, _ = proc.communicate(("\n".join(specs) + "\n").encode())

    results: dict[str, str] = {}
    pos = 0
    for spec in specs:
        nl = data.find(b"\n", pos)
        if nl == -1:
            break
        header = data[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        parts = header.split()
        if not parts or parts[-1] == "missing":
            continue
        if len(parts) < 3:
            continue
        try:
            size = int(parts[2])
        except ValueError:
            continue
        content = data[pos:pos + size]
        pos += size + 1  # skip the trailing newline git appends after content
        try:
            results[spec] = content.decode("utf-8")
        except UnicodeDecodeError:
            results[spec] = content.decode("utf-8", "replace")
    return results


class HistoryIndex:
    """Per-run cache of "every heading/bold-lead this target ever had."

    Computed once per unique target file (not once per quote pointing at
    it), and only for targets whose CURRENT state already failed to match --
    a target every quote already matches against current state never needs
    its history walked at all.
    """

    def __init__(self, root: Path):
        toplevel_result = _run_git(root, ["rev-parse", "--show-toplevel"])
        if toplevel_result.returncode != 0:
            self.available = False
            self.shallow = False
            self.toplevel: Path | None = None
        else:
            self.available = True
            self.toplevel = Path(toplevel_result.stdout.strip()).resolve()
            shallow_result = _run_git(
                self.toplevel, ["rev-parse", "--is-shallow-repository"]
            )
            self.shallow = (
                shallow_result.returncode == 0
                and shallow_result.stdout.strip() == "true"
            )
        self._cache: dict[str, set[str] | None] = {}
        self.targets_examined = 0
        self.revisions_examined = 0
        self.elapsed = 0.0
        self.capped_targets: list[str] = []

    def rel_path_for(self, target_path: Path) -> str | None:
        if self.toplevel is None:
            return None
        try:
            return str(target_path.resolve().relative_to(self.toplevel))
        except ValueError:
            return None

    def union_for(self, target_path: Path) -> set[str] | None:
        """Every normalized heading/bold-lead ever present at target_path.

        None means "could not be determined" (not a git repo, or the git
        call for this specific target failed) -- callers must treat that as
        unverified, never as an empty (and therefore non-matching) result.
        """
        if not self.available:
            return None
        rel_path = self.rel_path_for(target_path)
        if rel_path is None:
            return None
        if rel_path in self._cache:
            return self._cache[rel_path]

        t0 = time.time()
        pairs = follow_history_pairs(self.toplevel, rel_path)
        result: set[str] | None
        if pairs is None:
            result = None
        else:
            if len(pairs) >= MAX_HISTORY_REVISIONS:
                self.capped_targets.append(rel_path)
            specs = [f"{h}:{p}" for h, p in pairs]
            blobs = batch_fetch_blobs(self.toplevel, specs)
            union: set[str] = set()
            for spec in specs:
                content = blobs.get(spec)
                if content is not None:
                    union |= extract_anchors(content)
            result = union
            self.revisions_examined += len(pairs)
        self.targets_examined += 1
        self.elapsed += time.time() - t0
        self._cache[rel_path] = result
        return result


def check_repo(root: Path, globs: list[str]) -> dict:
    """Scan `root` and return the full report as data.

    Keys: findings (confirmed stale references), unverified (candidates
    whose history could not be checked), examined (reference count),
    scanned (file count), history_available, shallow_clone,
    history_elapsed_seconds, history_targets_examined,
    history_revisions_examined, history_capped_targets.
    """
    files = scan_files(root, globs)
    texts: dict[Path, str] = {}
    for md in files:
        try:
            texts[md] = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            texts[md] = ""

    heading_cache: dict[Path, list[str]] = {}
    bold_cache: dict[Path, list[str]] = {}

    def targets_for(target_path: Path) -> tuple[list[str], list[str]] | None:
        if target_path not in texts:
            if not target_path.exists() or not target_path.is_file():
                return None
            try:
                texts[target_path] = target_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None
        if target_path not in heading_cache:
            body = strip_fenced_blocks(texts[target_path])
            heading_cache[target_path] = extract_headings(body)
            bold_cache[target_path] = extract_bold_leads(body)
        return heading_cache[target_path], bold_cache[target_path]

    history = HistoryIndex(root)

    findings: list[dict] = []
    unverified: list[dict] = []
    examined = 0

    for md in files:
        for ref in find_references(md, texts[md]):
            target_path = resolve_target(md, ref.target)
            if target_path is None:
                continue
            resolved = targets_for(target_path)
            if resolved is None:
                # Missing-file breakage is check-links.py's job, not ours;
                # skip rather than double-report.
                continue
            headings, bold_leads = resolved
            examined += 1
            if quote_matches(ref.quote, headings) or quote_matches(
                ref.quote, bold_leads
            ):
                continue  # matches the target's CURRENT state -- clean

            record = {
                "referring_file": md,
                "line": ref.line_no,
                "quote": ref.quote,
                "target": ref.target,
                "target_path": target_path,
                "form": ref.form,
            }

            # Does not match current state.  A quote that never named a
            # heading at all is textually identical to one that did and was
            # renamed away, so consult history before concluding anything.
            union = history.union_for(target_path)
            if union is None:
                unverified.append(record)
                continue
            if quote_matches(ref.quote, union):
                findings.append(record)
            elif history.shallow:
                # A shallow clone's followed history can be truncated before
                # it reaches the commit that would have confirmed this, so
                # "not found within what we could read" is not the same
                # claim as "not found" -- see HistoryIndex and
                # format_report's shallow-clone note.  Only a POSITIVE match
                # is trustworthy from a shallow clone; a negative one is not.
                unverified.append(record)
            # else: full history was available and never matched either --
            # a paraphrase/free citation, not evidence of staleness; dropped
            # silently rather than reported.

    return {
        "findings": findings,
        "unverified": unverified,
        "examined": examined,
        "scanned": len(files),
        "history_available": history.available,
        "shallow_clone": history.shallow,
        "history_elapsed_seconds": history.elapsed,
        "history_targets_examined": history.targets_examined,
        "history_revisions_examined": history.revisions_examined,
        "history_capped_targets": history.capped_targets,
    }


def format_report(root: Path, report: dict) -> str:
    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(root))
        except ValueError:
            return str(p)

    findings = report["findings"]
    unverified = report["unverified"]

    lines = [
        f"Examined {report['examined']} quoted section-title reference(s) "
        f"across {report['scanned']} markdown files."
    ]

    if not report["history_available"]:
        lines.append(
            "NOTE: this is not a git repository (or `git` is not on PATH) -- "
            "history-based verification could not run at all.  Every "
            "reference that did not match the target's CURRENT heading/bold "
            "state is reported as UNVERIFIED below rather than silently "
            "dropped or silently flagged."
        )
    elif report["shallow_clone"]:
        lines.append(
            "NOTE: shallow clone.  `git log` cannot see past the fetch "
            "depth, so a reference whose confirming revision lies beyond it "
            "reads as never-a-heading and is reported as UNVERIFIED rather "
            "than confirmed clean or confirmed stale (mirrors "
            "check-stale-records.py's age_informative: false).  Re-run "
            "against a full clone (`git fetch --unshallow`) before trusting "
            "an empty findings list."
        )

    if report["history_capped_targets"]:
        lines.append(
            f"NOTE: {len(report['history_capped_targets'])} target(s) hit "
            f"the {MAX_HISTORY_REVISIONS}-revision history cap; a rename or "
            f"heading older than that cap could be missed: "
            + ", ".join(report["history_capped_targets"])
        )

    lines.append(
        f"History check: {report['history_targets_examined']} unique "
        f"target(s) walked, {report['history_revisions_examined']} "
        f"revision(s) read, {report['history_elapsed_seconds']:.2f}s."
    )

    if not findings and not unverified:
        lines.append("\nno stale section-title references")
        return "\n".join(lines)

    if findings:
        lines.append(
            f"\n{len(findings)} CONFIRMED stale section-title reference(s) "
            f"(quote matched a heading/bold-lead in an earlier revision, but "
            f"not the current one):"
        )
        for f in findings:
            lines.append(
                f"  - {rel(f['referring_file'])}:{f['line']} quotes "
                f'"{f["quote"]}" -> {f["target"]} '
                f"({rel(f['target_path'])})"
            )

    if unverified:
        lines.append(
            f"\n{len(unverified)} UNVERIFIED reference(s) (did not match "
            f"current state, and history could not be checked -- NOT "
            f"confirmed stale, NOT confirmed clean):"
        )
        for f in unverified:
            lines.append(
                f"  - {rel(f['referring_file'])}:{f['line']} quotes "
                f'"{f["quote"]}" -> {f["target"]} '
                f"({rel(f['target_path'])})"
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=ROOT,
        help="repository root to scan (default: this repo)",
    )
    parser.add_argument(
        "--glob", action="append", dest="globs",
        help="scan glob, repeatable (default: this repo's markdown trees)",
    )
    # argparse itself already exits 0 on --help and 2 on a usage error,
    # which lines up with this script's own usage-exit convention.
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: --root {root} is not a directory", file=sys.stderr)
        return USAGE_EXIT

    globs = args.globs or SCAN_GLOBS
    report = check_repo(root, globs)
    print(format_report(root, report))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
