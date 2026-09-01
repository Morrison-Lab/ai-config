#!/usr/bin/env python3
"""Check rendered output and markdown artifacts for broken references.

Scans rendered artifacts (HTML, markdown, text, QMD) for unresolved cross-references
and citations that failed at render time and leaked into output files:
- Unresolved cross-references: literal `?@key` (e.g. `?@fig-...`, `?@def-...`, `?@sec-...`)
- Missing citation keys: bold with trailing question mark (`<strong>key?</strong>`, `**key?**`)
- Unprocessed citation syntax: raw `[@key]` left in body text

Explicitly distinguishes and ignores valid markdown footnote references
(`[^1]`, `[^note]`) and footnote definitions (`[^1]: ...`), preventing false
warnings on valid footnote markup (ai-config#2879).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Add scripts/lib to path for shared fence stripping
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import strip_fences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Primary failure marker: Quarto unresolved cross-reference or citation
# e.g. ?@fig-scatter-plot or ?@def-coef-interp-procedure
UNRESOLVED_CROSSREF_RE = re.compile(
    r"\?@(?P<key>[A-Za-z0-9_#-]+(?:[A-Za-z0-9_#.:-]*[A-Za-z0-9_#-])?)"
)

# Secondary heuristic: missing citation key rendered bold with trailing ?
# e.g. <strong>smith2020?</strong> or **smith2020?**
BOLD_CITATION_RE = re.compile(
    r"<strong>(?P<html_key>[A-Za-z0-9_#-]+(?:[A-Za-z0-9_#.:-]*[A-Za-z0-9_#-])?)\?</strong>"
    r"|(?<!\*)\*\*(?P<md_key>[A-Za-z0-9_#-]+(?:[A-Za-z0-9_#.:-]*[A-Za-z0-9_#-])?)\?\*\*(?!\*)"
)

# Citeproc / Pandoc reference formats:
# 1. Bracketed citations: [@author2020], [-@author2020], [see @author2020, p. 10; also -@doe2021]
# Must contain at least one @key or -@key within square brackets, not matching footnotes [^...]
BRACKETED_CITATION_RE = re.compile(
    r"\[(?P<inner>[^\]\n]*?(?:(?<![A-Za-z0-9._%+/:!#$&*~?])-?@(?P<lead_key>[A-Za-z0-9_#]+(?:[A-Za-z0-9_#.:-]*[A-Za-z0-9_#-])?))[^\]\n]*?)\]"
)

# Citation keys inside bracketed citations
CITE_KEY_IN_BRACKET_RE = re.compile(
    r"(?<![A-Za-z0-9._%+/:!#$&*~?])-?@(?P<key>[A-Za-z0-9_#]+(?:[A-Za-z0-9_#.:-]*[A-Za-z0-9_#-])?)"
)

# 2. Standalone narrative / in-text citeproc citations: e.g. @author2020 or -@author2020 in prose
NARRATIVE_CITATION_RE = re.compile(
    r"(?<![A-Za-z0-9._%+/:!#$&*~?])(?P<marker>-?@(?P<key>[A-Za-z_][A-Za-z0-9_#.:-]*[A-Za-z0-9_#]|[A-Za-z_]))\b"
)

# Footnote patterns for explicit validation and ignore
FOOTNOTE_REF_RE = re.compile(r"\[\^(?P<label>[^\]]+)\](?!\:)")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^(?P<label>[^\]]+)\]\:\s+", re.MULTILINE)

# Inline code span regex
INLINE_CODE_RE = re.compile(r"`[^`]*`")


@dataclass
class ReferenceFinding:
    """A detected broken reference finding."""

    file: str
    line: int
    category: str
    marker: str
    context: str
    key: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def is_valid_footnote_reference(text: str) -> bool:
    """Return True if text matches valid markdown footnote reference syntax."""
    return bool(FOOTNOTE_REF_RE.fullmatch(text.strip()))


def is_valid_footnote_definition(text: str) -> bool:
    """Return True if text matches valid markdown footnote definition syntax."""
    return bool(FOOTNOTE_DEF_RE.match(text.strip()))


def scan_content(
    content: str,
    file_path: str = "<stdin>",
) -> list[ReferenceFinding]:
    """Scan content for broken rendered reference markers.

    Strips code blocks and inline code spans to avoid false positives on
    code examples or documentation discussing the failure markers.
    """
    findings: list[ReferenceFinding] = []

    # Strip fenced code blocks
    stripped_text = strip_fences(content)

    # Process line by line for accurate line numbering and context
    lines = stripped_text.split("\n")
    for line_idx, line in enumerate(lines, start=1):
        # Strip inline code spans on the line before searching
        clean_line = INLINE_CODE_RE.sub(" ", line)
        occupied_spans: list[tuple[int, int]] = []

        # 1. Unresolved crossrefs (?@...)
        for match in UNRESOLVED_CROSSREF_RE.finditer(clean_line):
            key = match.group("key")
            start = max(0, match.start() - 30)
            end = min(len(line), match.end() + 30)
            context = line[start:end].strip()
            occupied_spans.append((match.start(), match.end()))
            findings.append(
                ReferenceFinding(
                    file=file_path,
                    line=line_idx,
                    category="unresolved_crossref",
                    marker=match.group(0),
                    context=context,
                    key=key,
                )
            )

        # 2. Bold citation key with trailing question mark
        for match in BOLD_CITATION_RE.finditer(clean_line):
            key = match.group("html_key") or match.group("md_key")
            start = max(0, match.start() - 30)
            end = min(len(line), match.end() + 30)
            context = line[start:end].strip()
            occupied_spans.append((match.start(), match.end()))
            findings.append(
                ReferenceFinding(
                    file=file_path,
                    line=line_idx,
                    category="missing_citation",
                    marker=match.group(0),
                    context=context,
                    key=key,
                )
            )

        # 3. Bracketed Citeproc / Pandoc citations ([@key], [-@key], [see @key; @key2])
        for match in BRACKETED_CITATION_RE.finditer(clean_line):
            span = (match.start(), match.end())
            if any(s <= match.start() < e or s < match.end() <= e for s, e in occupied_spans):
                continue
            occupied_spans.append(span)

            inner_text = match.group("inner")
            bracket_marker = match.group(0)
            start = max(0, match.start() - 30)
            end = min(len(line), match.end() + 30)
            context = line[start:end].strip()

            for key_match in CITE_KEY_IN_BRACKET_RE.finditer(inner_text):
                key = key_match.group("key")
                findings.append(
                    ReferenceFinding(
                        file=file_path,
                        line=line_idx,
                        category="unprocessed_citation",
                        marker=bracket_marker,
                        context=context,
                        key=key,
                    )
                )

        # 4. Narrative / in-text Citeproc citations (@author2020, -@author2020)
        for match in NARRATIVE_CITATION_RE.finditer(clean_line):
            m_start, m_end = match.start(), match.end()
            if any(s <= m_start < e or s < m_end <= e for s, e in occupied_spans):
                continue
            occupied_spans.append((m_start, m_end))

            key = match.group("key")
            start = max(0, m_start - 30)
            end = min(len(line), m_end + 30)
            context = line[start:end].strip()
            findings.append(
                ReferenceFinding(
                    file=file_path,
                    line=line_idx,
                    category="unprocessed_citation",
                    marker=match.group("marker"),
                    context=context,
                    key=key,
                )
            )

    return findings


def scan_file(file_path: Path) -> list[ReferenceFinding]:
    """Read and scan a single file for broken references."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"warning: failed to read {file_path}: {exc}", file=sys.stderr)
        return []
    rel_path = str(file_path)
    try:
        rel_path = str(file_path.relative_to(ROOT))
    except ValueError:
        pass
    return scan_content(content, file_path=rel_path)


def scan_directory(
    dir_path: Path,
    extensions: tuple[str, ...] = (".html", ".htm", ".md", ".qmd", ".txt"),
) -> list[ReferenceFinding]:
    """Recursively scan a directory for files matching specified extensions."""
    findings: list[ReferenceFinding] = []
    if not dir_path.is_dir():
        return findings

    for ext in extensions:
        for file_path in dir_path.rglob(f"*{ext}"):
            if file_path.is_file():
                findings.extend(scan_file(file_path))

    return findings


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories to scan (defaults to standard output dirs)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output format",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any heuristic citation findings are detected",
    )

    args = parser.parse_args(argv)

    paths_to_scan: list[Path] = args.paths
    if not paths_to_scan:
        # Check standard output directories if present
        for candidate in ("_site", "_book", "docs"):
            p = ROOT / candidate
            if p.is_dir():
                paths_to_scan.append(p)

    if not paths_to_scan:
        if args.json:
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "checked_count": 0,
                        "findings": [],
                    },
                    indent=2,
                )
            )
        else:
            print("No output directories or files found to scan.")
        return 0

    all_findings: list[ReferenceFinding] = []
    for path in paths_to_scan:
        if path.is_file():
            all_findings.extend(scan_file(path))
        elif path.is_dir():
            all_findings.extend(scan_directory(path))

    if args.json:
        payload = {
            "status": "broken_references" if all_findings else "ok",
            "findings_count": len(all_findings),
            "findings": [f.to_dict() for f in all_findings],
        }
        print(json.dumps(payload, indent=2))
        return 1 if all_findings else 0

    if all_findings:
        print(f"✗ Found {len(all_findings)} broken rendered reference marker(s):")
        for finding in all_findings:
            print(
                f"  {finding.file}:{finding.line} [{finding.category}] {finding.marker} "
                f"(key: '{finding.key}') -> \"{finding.context}\""
            )
        return 1

    print("✓ No broken rendered references found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
