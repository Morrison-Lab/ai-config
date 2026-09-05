#!/usr/bin/env python3
"""Deterministic DOI-vs-.bib title/author diff script.

Verifies that DOIs in a BibTeX (.bib) file resolve to works whose title and
authors match the .bib entry, rather than merely resolving.

A resolving DOI pointing to a different work is a signature of LLM citation
fabrication (see shared/writing/citations.md: "A resolving DOI is not a correct
DOI").

Features:
- Parses BibTeX entries (.bib) and extracts DOI, title, author, year fields.
- Optionally scopes verification to keys cited in LaTeX (.tex), Quarto (.qmd),
  RMarkdown (.rmd), or Markdown (.md) source files (following \\input/\\include).
- Resolves DOIs via Crossref (https://api.crossref.org/works/<doi>),
  falling back to OpenAlex on HTTP 429 / rate limits, and CSL-JSON for non-Crossref DOIs.
- Deterministically diffs resolved title and first author against the .bib entry
  using fuzzy matching (tolerant of punctuation, subtitles, LaTeX markup, and accents).
- Reports MATCH (valid), MISMATCH (fabrication signature / defect), NOT_RESOLVED (defect),
  UNVERIFIABLE (network failure), and NO_DOI / SKIPPED (informational).
- Emits human-readable summaries or machine-parseable JSON.

Exit codes:
  0: All checked entries with DOIs resolved and matched (or only NO_DOI / SKIPPED).
  1: One or more entries had MISMATCH or NOT_RESOLVED defects.
  2: Usage error, missing files, or network failure when network is required.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# Default Crossref API polite pool identification
DEFAULT_USER_AGENT = (
    "check-doi-bib/1.0 (https://github.com/Morrison-Lab/ai-config; mailto:ai-config@morrison-lab.org)"
)


class CheckStatus(str, Enum):
    MATCH = "MATCH"  # DOI resolves, metadata matches
    MISMATCH = "MISMATCH"  # DOI resolves, but title or author mismatch (fabrication signature)
    NOT_RESOLVED = "NOT_RESOLVED"  # DOI does not resolve (404 / invalid DOI)
    UNVERIFIABLE = "UNVERIFIABLE"  # Network error, timeout, or rate-limited without resolution
    NO_DOI = "NO_DOI"  # Entry contains no DOI field (informational)
    SKIPPED = "SKIPPED"  # Entry not cited in document (when scoped to cited keys)


@dataclass
class BibEntry:
    key: str
    entry_type: str
    doi: str | None = None
    title: str | None = None
    author: str | None = None
    year: str | None = None
    journal: str | None = None
    raw_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ResolvedMetadata:
    doi: str
    title: str | None = None
    first_author_family: str | None = None
    first_author_given: str | None = None
    all_authors: list[str] = field(default_factory=list)
    year: str | None = None
    container_title: str | None = None
    source: str = "crossref"  # crossref, openalex, csl, mock
    status: CheckStatus = CheckStatus.MATCH
    error_message: str | None = None


@dataclass
class EntryCheckResult:
    key: str
    entry_type: str
    doi: str | None
    status: CheckStatus
    bib_title: str | None = None
    resolved_title: str | None = None
    title_similarity: float = 0.0
    title_match: bool = False
    bib_first_author: str | None = None
    resolved_first_author: str | None = None
    author_similarity: float = 0.0
    author_match: bool = False
    bib_year: str | None = None
    resolved_year: str | None = None
    year_match: bool = True
    resolver_source: str | None = None
    message: str | None = None


@dataclass
class BibCheckSummary:
    total_entries: int = 0
    checked_count: int = 0
    matches: int = 0
    mismatches: int = 0
    not_resolved: int = 0
    unverifiable: int = 0
    no_doi: int = 0
    skipped: int = 0
    results: list[EntryCheckResult] = field(default_factory=list)

    @property
    def has_defects(self) -> bool:
        return self.mismatches > 0 or self.not_resolved > 0


# --- LaTeX / Text Normalization ---

_LATEX_ACCENTS = [
    (re.compile(r'\\"[aA]'), "ä"),
    (re.compile(r'\\"[eE]'), "ë"),
    (re.compile(r'\\"[iI]'), "ï"),
    (re.compile(r'\\"[oO]'), "ö"),
    (re.compile(r'\\"[uU]'), "ü"),
    (re.compile(r'\\"[yY]'), "ÿ"),
    (re.compile(r"\\'[aA]"), "á"),
    (re.compile(r"\\'[eE]"), "é"),
    (re.compile(r"\\'[iI]"), "í"),
    (re.compile(r"\\'[oO]"), "ó"),
    (re.compile(r"\\'[uU]"), "ú"),
    (re.compile(r"\\'[yY]"), "ý"),
    (re.compile(r"\\`[aA]"), "à"),
    (re.compile(r"\\`[eE]"), "è"),
    (re.compile(r"\\`[iI]"), "ì"),
    (re.compile(r"\\`[oO]"), "ò"),
    (re.compile(r"\\`[uU]"), "ù"),
    (re.compile(r"\\\^[aA]"), "â"),
    (re.compile(r"\\\^[eE]"), "ê"),
    (re.compile(r"\\\^[iI]"), "î"),
    (re.compile(r"\\\^[oO]"), "ô"),
    (re.compile(r"\\\^[uU]"), "û"),
    (re.compile(r"\\~[aA]"), "ã"),
    (re.compile(r"\\~[oO]"), "õ"),
    (re.compile(r"\\~[nN]"), "ñ"),
    (re.compile(r"\\c\{c\}"), "ç"),
    (re.compile(r"\\c\{C\}"), "Ç"),
    (re.compile(r"\\v\{s\}"), "š"),
    (re.compile(r"\\v\{S\}"), "Š"),
    (re.compile(r"\\v\{c\}"), "č"),
    (re.compile(r"\\v\{C\}"), "Č"),
    (re.compile(r"\\v\{z\}"), "ž"),
    (re.compile(r"\\v\{Z\}"), "Ž"),
    (re.compile(r"\\v\{([a-zA-Z])\}"), r"\1"),
    (re.compile(r"\\u\{([a-zA-Z])\}"), r"\1"),
    (re.compile(r"\\k\{([a-zA-Z])\}"), r"\1"),
    (re.compile(r"\\r\{([a-zA-Z])\}"), r"\1"),
    (re.compile(r"\\H\{([a-zA-Z])\}"), r"\1"),
    (re.compile(r"\\l\b\s*"), "l"),
    (re.compile(r"\\L\b\s*"), "L"),
    (re.compile(r"\\o\b\s*"), "ø"),
    (re.compile(r"\\O\b\s*"), "Ø"),
    (re.compile(r"\\aa\b\s*"), "å"),
    (re.compile(r"\\AA\b\s*"), "Å"),
    (re.compile(r"\\ae\b\s*"), "æ"),
    (re.compile(r"\\AE\b\s*"), "Æ"),
    (re.compile(r"\\oe\b\s*"), "œ"),
    (re.compile(r"\\OE\b\s*"), "Œ"),
    (re.compile(r"\\ss\b\s*"), "ß"),
]


def clean_latex(text: str | None) -> str:
    """Unescape LaTeX accents, strip macros, and normalize LaTeX markup."""
    if not text:
        return ""

    s = text.strip()

    # Apply known LaTeX accent replacements
    for pattern, replacement in _LATEX_ACCENTS:
        s = pattern.sub(replacement, s)

    # Strip command wrappers like \textbf{x}, \emph{x}, \enquote{x}, \mathrm{x}
    s = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", s)
    # Strip standalone commands like \LaTeX, \TeX
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    # Strip HTML/XML tags if any (e.g. <jats:p>, <i>, <b>)
    s = re.sub(r"<[^>]+>", " ", s)
    # Strip curly braces
    s = s.replace("{", "").replace("}", "")
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_text_for_comparison(text: str | None) -> str:
    """Normalize text into ASCII lowercase alphanumeric tokens for robust comparison."""
    if not text:
        return ""

    cleaned = clean_latex(text)
    # Decompose unicode to separate base characters and diacritics
    nfkd = unicodedata.normalize("NFKD", cleaned)
    # Remove combining marks (diacritics)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Replace non-alphanumeric with space
    alphanumeric = re.sub(r"[^a-zA-Z0-9]+", " ", no_accents).lower()
    return re.sub(r"\s+", " ", alphanumeric).strip()


def normalize_doi(doi: str | None) -> str:
    """Normalize DOI string by stripping URL prefixes, resolver URLs, and whitespace."""
    if not doi:
        return ""
    d = doi.strip()
    d = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", d, flags=re.IGNORECASE)
    d = re.sub(r"^doi:\s*", "", d, flags=re.IGNORECASE)
    return d.strip().strip("/")


def split_bibtex_authors(author_str: str) -> list[str]:
    """Split BibTeX author string by 'and' taking braces into account."""
    s = author_str.strip()
    # Strip outer redundant braces if wrapped around the entire author list
    if s.startswith("{") and s.endswith("}"):
        # Check if first brace closes only at the end
        depth = 0
        closes_at_end = False
        for idx, char in enumerate(s):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    closes_at_end = (idx == len(s) - 1)
                    break
        if closes_at_end:
            inner = s[1:-1].strip()
            # If inner contains nested braced blocks separated by 'and', use inner
            if "{" in inner and " and " in inner.lower():
                s = inner

    authors: list[str] = []
    current: list[str] = []
    depth = 0
    i = 0
    n = len(s)

    while i < n:
        char = s[i]
        if char == "{":
            depth += 1
            current.append(char)
            i += 1
        elif char == "}":
            depth = max(0, depth - 1)
            current.append(char)
            i += 1
        elif depth == 0 and s[i : i + 5].lower() == " and ":
            auth = "".join(current).strip()
            if auth:
                authors.append(auth)
            current = []
            i += 5
        else:
            current.append(char)
            i += 1

    remaining = "".join(current).strip()
    if remaining:
        authors.append(remaining)

    return authors


def extract_first_author_surname(author_field: str | None) -> str:
    """Extract the first author's surname / family name from BibTeX author field."""
    if not author_field:
        return ""

    authors = split_bibtex_authors(author_field)
    if not authors:
        return ""

    first_author = authors[0].strip()
    if not first_author:
        return ""

    # Check if first author is a braced institutional author, e.g. {World Health Organization}
    if first_author.startswith("{") and first_author.endswith("}"):
        inner = first_author[1:-1].strip()
        if "," not in inner:
            return clean_latex(inner)
        first_author = inner

    cleaned = clean_latex(first_author)
    # Check if format is "Last, First"
    if "," in cleaned:
        surname = cleaned.split(",")[0].strip()
    else:
        # Check if "van / von / de / da / del" prefixes exist
        parts = cleaned.split()
        if len(parts) >= 2 and parts[-2].lower() in ("van", "von", "de", "da", "del", "der", "du"):
            surname = f"{parts[-2]} {parts[-1]}"
        else:
            surname = parts[-1].strip() if parts else cleaned

    return surname


# --- BibTeX Parser ---


def parse_bib_entries(bib_content: str) -> list[BibEntry]:
    """Parse BibTeX entries from file content into BibEntry dataclasses.

    Handles multiline values, nested braces, quoted values, and comments.
    """
    entries: list[BibEntry] = []

    # Strip line comments starting with %
    lines = [
        re.sub(r"(?<!\\)%.*$", "", line) for line in bib_content.splitlines()
    ]
    cleaned_content = "\n".join(lines)

    # Find entries starting with @type{
    entry_pattern = re.compile(
        r"@([a-zA-Z]+)\s*[\{\(]\s*([^,\s]+)\s*,", re.MULTILINE
    )

    idx = 0
    content_len = len(cleaned_content)

    while idx < content_len:
        match = entry_pattern.search(cleaned_content, idx)
        if not match:
            break

        entry_type = match.group(1).lower()
        key = match.group(2).strip()

        # Skip non-entry blocks like @comment or @preamble
        if entry_type in ("comment", "preamble", "string"):
            idx = match.end()
            continue

        # Find the closing matching brace for this entry
        brace_level = 1
        pos = match.end()
        field_start = pos

        while pos < content_len and brace_level > 0:
            char = cleaned_content[pos]
            if char == "{" or char == "(":
                brace_level += 1
            elif char == "}" or char == ")":
                brace_level -= 1
            pos += 1

        entry_body = cleaned_content[field_start : pos - 1]
        idx = pos

        # Parse fields within entry_body
        raw_fields = _parse_bib_fields(entry_body)

        doi = raw_fields.get("doi")
        title = raw_fields.get("title")
        author = raw_fields.get("author")
        year = raw_fields.get("year") or raw_fields.get("date")
        if year:
            # Extract 4-digit year if date string
            year_match = re.search(r"\b(19\d\d|20\d\d)\b", year)
            if year_match:
                year = year_match.group(1)

        journal = raw_fields.get("journal") or raw_fields.get("booktitle")

        entries.append(
            BibEntry(
                key=key,
                entry_type=entry_type,
                doi=normalize_doi(doi) if doi else None,
                title=clean_latex(title) if title else None,
                author=clean_latex(author) if author else None,
                year=year.strip() if year else None,
                journal=clean_latex(journal) if journal else None,
                raw_fields=raw_fields,
            )
        )

    return entries


def _parse_bib_fields(body: str) -> dict[str, str]:
    """Parse field = value pairs from a BibTeX entry body."""
    fields: dict[str, str] = {}
    pos = 0
    body_len = len(body)

    while pos < body_len:
        # Find field name
        field_match = re.search(r"([a-zA-Z0-9_\-]+)\s*=", body[pos:])
        if not field_match:
            break

        field_name = field_match.group(1).lower()
        val_start = pos + field_match.end()

        # Skip leading whitespace
        while val_start < body_len and body[val_start].isspace():
            val_start += 1

        if val_start >= body_len:
            break

        first_char = body[val_start]
        val_end = val_start

        if first_char == "{":
            brace_level = 1
            val_end = val_start + 1
            while val_end < body_len and brace_level > 0:
                if body[val_end] == "{":
                    brace_level += 1
                elif body[val_end] == "}":
                    brace_level -= 1
                val_end += 1
            val = body[val_start + 1 : val_end - 1]
        elif first_char == '"':
            val_end = val_start + 1
            while val_end < body_len:
                if body[val_end] == '"' and body[val_end - 1] != "\\":
                    val_end += 1
                    break
                val_end += 1
            val = body[val_start + 1 : val_end - 1]
        else:
            # Unquoted value (number or string macro), read until comma or newline
            while val_end < body_len and body[val_end] not in (",", "\n", "\r"):
                val_end += 1
            val = body[val_start:val_end].strip()

        fields[field_name] = val.strip()
        pos = val_end
        # Skip trailing comma if present
        while pos < body_len and (body[pos].isspace() or body[pos] == ","):
            pos += 1

    return fields


# --- Citation Extraction for Project Scoping ---

_CITE_PATTERNS = [
    # LaTeX citation commands: \cite{a}, \citep{a,b}, \autocite{c}, etc.
    re.compile(
        r"\\(?:auto|paren|text|foot|no)?cite[a-zA-Z*]*\{([^}]+)\}",
        re.MULTILINE,
    ),
    # Quarto / Pandoc markdown citations: [@key1; @key2] or @key1
    re.compile(r"\[\s*@([a-zA-Z0-9_:.#$%&-]+)", re.MULTILINE),
    re.compile(r";\s*@([a-zA-Z0-9_:.#$%&-]+)", re.MULTILINE),
    re.compile(r"(?:^|[\s(])@([a-zA-Z0-9_:.#$%&-]+)", re.MULTILINE),
]


def extract_cited_keys(project_root_or_file: Path) -> set[str]:
    """Scan source files (.tex, .qmd, .rmd, .md) to extract cited keys."""
    cited_keys: set[str] = set()

    if project_root_or_file.is_file():
        files_to_scan = [project_root_or_file]
    elif project_root_or_file.is_dir():
        files_to_scan = []
        for ext in ("*.tex", "*.qmd", "*.rmd", "*.md", "*.ltx"):
            files_to_scan.extend(project_root_or_file.glob(f"**/{ext}"))
    else:
        return cited_keys

    seen_files: set[Path] = set()

    for file_path in files_to_scan:
        if file_path in seen_files or not file_path.is_file():
            continue
        seen_files.add(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Extract citations
        for pattern in _CITE_PATTERNS:
            for match in pattern.finditer(content):
                raw_keys = match.group(1)
                for key in re.split(r"[,;]\s*", raw_keys):
                    k = key.strip().lstrip("@")
                    # Strip trailing punctuation like . , ; : ? ! ) ]
                    k = re.sub(r"[.,;:?!)\],]+$", "", k).strip()
                    if k:
                        cited_keys.add(k)

    return cited_keys


# --- DOI Metadata Resolution & Fallbacks ---


def resolve_doi_crossref(
    doi: str,
    email: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | None]:
    """Query Crossref API for DOI metadata."""
    encoded_doi = urllib.parse.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{encoded_doi}"
    if email:
        url += f"?mailto={urllib.parse.quote(email)}"

    headers = {
        "User-Agent": DEFAULT_USER_AGENT
        if not email
        else f"check-doi-bib/1.0 (mailto:{email})",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            data = json.loads(response.read().decode("utf-8"))
            return status_code, data
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def resolve_doi_openalex(
    doi: str,
    email: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | None]:
    """Query OpenAlex API as fallback for rate-limited Crossref requests."""
    encoded_doi = urllib.parse.quote(doi, safe="")
    url = f"https://api.openalex.org/works/https://doi.org/{encoded_doi}"
    if email:
        url += f"?mailto={urllib.parse.quote(email)}"

    headers = {
        "User-Agent": DEFAULT_USER_AGENT
        if not email
        else f"check-doi-bib/1.0 (mailto:{email})",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            data = json.loads(response.read().decode("utf-8"))
            return status_code, data
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def resolve_doi_csl(
    doi: str,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | None]:
    """Query DOI Content Negotiation for CSL-JSON (covers DataCite / non-Crossref DOIs)."""
    encoded_doi = urllib.parse.quote(doi, safe="")
    url = f"https://doi.org/{encoded_doi}"
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/vnd.citationstyles.csl+json, application/json",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            data = json.loads(response.read().decode("utf-8"))
            return status_code, data
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def resolve_doi(
    doi: str,
    email: str | None = None,
    timeout: float = 10.0,
) -> ResolvedMetadata:
    """Resolve DOI metadata using Crossref, with OpenAlex and CSL fallbacks."""
    clean_doi = normalize_doi(doi)
    if not clean_doi:
        return ResolvedMetadata(
            doi="",
            status=CheckStatus.NOT_RESOLVED,
            error_message="Empty or invalid DOI",
        )

    # 1. Try Crossref
    status_code, data = resolve_doi_crossref(clean_doi, email, timeout)

    if status_code == 200 and data:
        msg = data.get("message", {})
        titles = msg.get("title", [])
        title = titles[0] if titles else None
        # Append subtitle if present
        subtitles = msg.get("subtitle", [])
        if subtitles and title:
            title = f"{title}: {subtitles[0]}"

        authors_data = msg.get("author", [])
        first_author_family = None
        first_author_given = None
        all_authors: list[str] = []

        for idx, auth in enumerate(authors_data):
            fam = auth.get("family") or auth.get("name")
            given = auth.get("given")
            if idx == 0:
                first_author_family = fam
                first_author_given = given
            name_str = f"{fam}, {given}" if fam and given else (fam or given or "")
            if name_str:
                all_authors.append(name_str)

        # Extract year
        year = None
        for date_key in ("published-print", "published-online", "published", "issued", "created"):
            dp = msg.get(date_key, {}).get("date-parts")
            if dp and dp[0] and len(dp[0]) > 0:
                year = str(dp[0][0])
                break

        container_title = None
        ct = msg.get("container-title", [])
        if ct:
            container_title = ct[0]

        return ResolvedMetadata(
            doi=clean_doi,
            title=title,
            first_author_family=first_author_family,
            first_author_given=first_author_given,
            all_authors=all_authors,
            year=year,
            container_title=container_title,
            source="crossref",
            status=CheckStatus.MATCH,
        )

    # 2. Fallback to OpenAlex on HTTP 429 (rate limit) or 5xx
    if status_code in (429, 500, 502, 503, 504):
        oa_status, oa_data = resolve_doi_openalex(clean_doi, email, timeout)
        if oa_status == 200 and oa_data:
            title = oa_data.get("title") or oa_data.get("display_name")
            authorships = oa_data.get("authorships", [])
            first_fam = None
            first_given = None
            all_auths: list[str] = []

            for idx, a_entry in enumerate(authorships):
                author_obj = a_entry.get("author", {})
                disp_name = author_obj.get("display_name", "")
                if idx == 0:
                    parts = disp_name.split()
                    first_fam = parts[-1] if parts else disp_name
                    first_given = " ".join(parts[:-1]) if len(parts) > 1 else None
                if disp_name:
                    all_auths.append(disp_name)

            pub_year = oa_data.get("publication_year")
            year = str(pub_year) if pub_year else None

            return ResolvedMetadata(
                doi=clean_doi,
                title=title,
                first_author_family=first_fam,
                first_author_given=first_given,
                all_authors=all_auths,
                year=year,
                source="openalex",
                status=CheckStatus.MATCH,
            )

    # 3. Fallback to CSL-JSON for DataCite or other non-Crossref registries
    if status_code in (404, 0, 429):
        csl_status, csl_data = resolve_doi_csl(clean_doi, timeout)
        if csl_status == 200 and csl_data:
            title = csl_data.get("title")
            authors_data = csl_data.get("author", [])
            first_author_family = None
            first_author_given = None
            all_authors = []

            for idx, auth in enumerate(authors_data):
                fam = auth.get("family") or auth.get("literal") or auth.get("name")
                given = auth.get("given")
                if idx == 0:
                    first_author_family = fam
                    first_author_given = given
                name_str = f"{fam}, {given}" if fam and given else (fam or given or "")
                if name_str:
                    all_authors.append(name_str)

            issued = csl_data.get("issued", {}).get("date-parts")
            year = str(issued[0][0]) if issued and issued[0] else None

            return ResolvedMetadata(
                doi=clean_doi,
                title=title,
                first_author_family=first_author_family,
                first_author_given=first_author_given,
                all_authors=all_authors,
                year=year,
                source="csl-json",
                status=CheckStatus.MATCH,
            )

    if status_code == 404:
        return ResolvedMetadata(
            doi=clean_doi,
            status=CheckStatus.NOT_RESOLVED,
            error_message="DOI returned HTTP 404 (Not Found)",
        )

    # Unverifiable network error or persistent failure
    return ResolvedMetadata(
        doi=clean_doi,
        status=CheckStatus.UNVERIFIABLE,
        error_message=f"Resolver unreachable or failed (HTTP status {status_code})",
    )


# --- Deterministic Fuzzy Metadata Matching ---


def fuzzy_match_title(
    bib_title: str | None,
    resolved_title: str | None,
    threshold: float = 0.70,
) -> tuple[bool, float]:
    """Compare .bib title against resolved title with fuzzy matching."""
    if not bib_title or not resolved_title:
        return False, 0.0

    norm_b = normalize_text_for_comparison(bib_title)
    norm_r = normalize_text_for_comparison(resolved_title)

    if not norm_b or not norm_r:
        return False, 0.0

    if norm_b == norm_r:
        return True, 1.0

    # Sequence similarity ratio
    ratio = difflib.SequenceMatcher(None, norm_b, norm_r).ratio()

    # Token overlap and length metrics
    tokens_b = set(norm_b.split())
    tokens_r = set(norm_r.split())

    if not tokens_b or not tokens_r:
        return ratio >= threshold, ratio

    intersection = tokens_b & tokens_r
    union = tokens_b | tokens_r
    jaccard = len(intersection) / len(union) if union else 0.0

    len_min = min(len(norm_b), len(norm_r))
    len_max = max(len(norm_b), len(norm_r))
    len_ratio = len_min / len_max if len_max > 0 else 0.0

    # Match if sequence ratio exceeds threshold, or token Jaccard is high with proportional length
    # (handling word-order inversions and slight subtitle additions)
    is_match = (
        ratio >= threshold
        or (jaccard >= 0.60 and len_ratio >= 0.60)
        or (jaccard >= 0.50 and ratio >= 0.65 and len_ratio >= 0.50)
    )

    score = max(ratio, jaccard)
    return is_match, score


def fuzzy_match_author(
    bib_author_field: str | None,
    resolved_first_author_family: str | None,
    threshold: float = 0.80,
) -> tuple[bool, float]:
    """Compare .bib first author surname against resolved first author surname."""
    if not bib_author_field or not resolved_first_author_family:
        return False, 0.0

    bib_surname = extract_first_author_surname(bib_author_field)
    norm_b = normalize_text_for_comparison(bib_surname)
    norm_r = normalize_text_for_comparison(resolved_first_author_family)

    if not norm_b or not norm_r:
        return False, 0.0

    if norm_b == norm_r:
        return True, 1.0

    # Handle multi-word surnames or prefixes (e.g. "van Dijk" vs "Dijk")
    if norm_b in norm_r.split() or norm_r in norm_b.split():
        return True, 0.95

    # Sequence similarity ratio
    ratio = difflib.SequenceMatcher(None, norm_b, norm_r).ratio()
    return ratio >= threshold, ratio


def check_bib_entry(
    entry: BibEntry,
    resolver: Callable[[str], ResolvedMetadata] = resolve_doi,
    title_threshold: float = 0.70,
    author_threshold: float = 0.80,
    is_cited: bool = True,
) -> EntryCheckResult:
    """Verify a single BibEntry against DOI resolver metadata."""
    if not is_cited:
        return EntryCheckResult(
            key=entry.key,
            entry_type=entry.entry_type,
            doi=entry.doi,
            status=CheckStatus.SKIPPED,
            bib_title=entry.title,
            bib_first_author=extract_first_author_surname(entry.author),
            message="Entry omitted because key is not cited in project documents",
        )

    if not entry.doi:
        return EntryCheckResult(
            key=entry.key,
            entry_type=entry.entry_type,
            doi=None,
            status=CheckStatus.NO_DOI,
            bib_title=entry.title,
            bib_first_author=extract_first_author_surname(entry.author),
            message="No DOI field in .bib entry",
        )

    meta = resolver(entry.doi)

    if meta.status == CheckStatus.NOT_RESOLVED:
        return EntryCheckResult(
            key=entry.key,
            entry_type=entry.entry_type,
            doi=entry.doi,
            status=CheckStatus.NOT_RESOLVED,
            bib_title=entry.title,
            bib_first_author=extract_first_author_surname(entry.author),
            resolver_source=meta.source,
            message=meta.error_message or "DOI does not resolve (HTTP 404)",
        )

    if meta.status == CheckStatus.UNVERIFIABLE:
        return EntryCheckResult(
            key=entry.key,
            entry_type=entry.entry_type,
            doi=entry.doi,
            status=CheckStatus.UNVERIFIABLE,
            bib_title=entry.title,
            bib_first_author=extract_first_author_surname(entry.author),
            resolver_source=meta.source,
            message=meta.error_message or "Resolver network error / unverifiable",
        )

    # Perform metadata comparison
    title_match, title_sim = fuzzy_match_title(
        entry.title, meta.title, threshold=title_threshold
    )
    author_match, author_sim = fuzzy_match_author(
        entry.author, meta.first_author_family, threshold=author_threshold
    )

    # Year comparison (informative check)
    year_match = True
    if entry.year and meta.year:
        try:
            year_match = abs(int(entry.year) - int(meta.year)) <= 1
        except ValueError:
            year_match = True

    bib_first_author = extract_first_author_surname(entry.author)

    if title_match and author_match:
        status = CheckStatus.MATCH
        msg = f"Resolved metadata matches .bib entry (source: {meta.source})"
    else:
        reasons = []
        if not title_match:
            reasons.append(
                f"title mismatch (bib: '{entry.title}', resolved: '{meta.title}')"
            )
        if not author_match:
            reasons.append(
                f"author mismatch (bib: '{bib_first_author}', resolved: '{meta.first_author_family}')"
            )
        status = CheckStatus.MISMATCH
        msg = (
            f"FABRICATION SIGNATURE: DOI resolves to a different work; {', '.join(reasons)}"
        )

    return EntryCheckResult(
        key=entry.key,
        entry_type=entry.entry_type,
        doi=entry.doi,
        status=status,
        bib_title=entry.title,
        resolved_title=meta.title,
        title_similarity=round(title_sim, 3),
        title_match=title_match,
        bib_first_author=bib_first_author,
        resolved_first_author=meta.first_author_family,
        author_similarity=round(author_sim, 3),
        author_match=author_match,
        bib_year=entry.year,
        resolved_year=meta.year,
        year_match=year_match,
        resolver_source=meta.source,
        message=msg,
    )


def check_bib(
    bib_content: str,
    resolver: Callable[[str], ResolvedMetadata] = resolve_doi,
    cited_keys: set[str] | None = None,
    title_threshold: float = 0.70,
    author_threshold: float = 0.80,
) -> BibCheckSummary:
    """Run DOI-vs-.bib verification over all entries in BibTeX content."""
    entries = parse_bib_entries(bib_content)
    summary = BibCheckSummary(total_entries=len(entries))

    for entry in entries:
        is_cited = True if cited_keys is None else (entry.key in cited_keys)
        res = check_bib_entry(
            entry,
            resolver=resolver,
            title_threshold=title_threshold,
            author_threshold=author_threshold,
            is_cited=is_cited,
        )
        summary.results.append(res)

        if res.status == CheckStatus.SKIPPED:
            summary.skipped += 1
        else:
            summary.checked_count += 1
            if res.status == CheckStatus.MATCH:
                summary.matches += 1
            elif res.status == CheckStatus.MISMATCH:
                summary.mismatches += 1
            elif res.status == CheckStatus.NOT_RESOLVED:
                summary.not_resolved += 1
            elif res.status == CheckStatus.UNVERIFIABLE:
                summary.unverifiable += 1
            elif res.status == CheckStatus.NO_DOI:
                summary.no_doi += 1

    return summary


# --- CLI & Reporting ---


def format_summary_text(summary: BibCheckSummary, quiet: bool = False) -> str:
    """Format check results into a human-readable report."""
    lines: list[str] = []

    if not quiet:
        lines.append("=" * 72)
        lines.append("DOI-VS-.BIB METADATA VERIFICATION REPORT")
        lines.append("=" * 72)

    for res in summary.results:
        if quiet and res.status in (
            CheckStatus.MATCH,
            CheckStatus.NO_DOI,
            CheckStatus.SKIPPED,
        ):
            continue

        symbol = {
            CheckStatus.MATCH: "✅ MATCH",
            CheckStatus.MISMATCH: "❌ MISMATCH (FABRICATION SIGNATURE)",
            CheckStatus.NOT_RESOLVED: "❌ NOT_RESOLVED",
            CheckStatus.UNVERIFIABLE: "❓ UNVERIFIABLE",
            CheckStatus.NO_DOI: "ℹ️  NO_DOI",
            CheckStatus.SKIPPED: "⏭️  SKIPPED",
        }.get(res.status, str(res.status))

        lines.append(f"[{symbol}] Entry: {res.key} ({res.entry_type})")
        if res.doi:
            lines.append(f"  DOI:      https://doi.org/{res.doi}")
        if res.bib_title:
            lines.append(f"  Bib Title:     {res.bib_title}")
        if res.resolved_title:
            lines.append(f"  Resolved Title: {res.resolved_title} (sim: {res.title_similarity:.2f})")
        if res.bib_first_author:
            lines.append(f"  Bib Author:    {res.bib_first_author}")
        if res.resolved_first_author:
            lines.append(
                f"  Resolved Auth:  {res.resolved_first_author} (sim: {res.author_similarity:.2f})"
            )
        if res.message:
            lines.append(f"  Detail:   {res.message}")
        lines.append("")

    lines.append("-" * 72)
    lines.append(
        f"Summary: Total {summary.total_entries} entries | "
        f"Checked: {summary.checked_count} | "
        f"Matches: {summary.matches} | "
        f"Mismatches: {summary.mismatches} | "
        f"Not Resolved: {summary.not_resolved} | "
        f"Unverifiable: {summary.unverifiable} | "
        f"No DOI: {summary.no_doi} | "
        f"Skipped: {summary.skipped}"
    )
    lines.append("-" * 72)

    if summary.has_defects:
        lines.append(
            "DEFECTS DETECTED: One or more entries have invalid or fabricated DOIs."
        )
    else:
        lines.append("VERDICT: Clean. All checked DOIs resolve and match entries.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Path to .bib file, LaTeX/Quarto document, or project directory",
    )
    parser.add_argument(
        "--bib",
        type=Path,
        help="Explicit path to .bib file",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Project root directory to scan for cited keys",
    )
    parser.add_argument(
        "--cited-only",
        action="store_true",
        help="Scope check to keys actually \\cite'd in project source files",
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Email address for Crossref polite pool / OpenAlex requests",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP request timeout in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--title-threshold",
        type=float,
        default=0.70,
        help="Fuzzy match threshold for title similarity (0.0 to 1.0, default: 0.70)",
    )
    parser.add_argument(
        "--author-threshold",
        type=float,
        default=0.80,
        help="Fuzzy match threshold for author surname similarity (0.0 to 1.0, default: 0.80)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of text report",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode: show only mismatches and final summary",
    )

    args = parser.parse_args(argv)

    project_root = args.root.resolve() if args.root else None

    if args.target is not None:
        target_path = Path(args.target).resolve()
    elif project_root is not None:
        target_path = project_root
    else:
        target_path = Path(".").resolve()

    bib_files: list[Path] = []

    if args.bib:
        bib_path = args.bib.resolve()
        if not bib_path.is_file():
            print(f"error: .bib file not found: {bib_path}", file=sys.stderr)
            return 2
        bib_files.append(bib_path)
    elif target_path.is_file():
        if target_path.suffix.lower() == ".bib":
            bib_files.append(target_path)
            if not project_root:
                project_root = target_path.parent
        else:
            # Source file provided, scan for .bib in same dir
            if not project_root:
                project_root = target_path.parent
            bib_files.extend(target_path.parent.glob("*.bib"))
    elif target_path.is_dir():
        if not project_root:
            project_root = target_path
        bib_files.extend(target_path.glob("**/*.bib"))
    else:
        print(f"error: target path not found: {target_path}", file=sys.stderr)
        return 2

    if not bib_files:
        print(f"error: no .bib files found in {target_path}", file=sys.stderr)
        return 2

    # Extract cited keys if --cited-only is requested
    cited_keys: set[str] | None = None
    if args.cited_only and project_root:
        cited_keys = extract_cited_keys(project_root)

    # Configure resolver callback
    def _resolver(doi: str) -> ResolvedMetadata:
        return resolve_doi(doi, email=args.email, timeout=args.timeout)

    combined_summary = BibCheckSummary()

    for bib_file in bib_files:
        try:
            content = bib_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            print(f"error: could not read {bib_file}: {exc}", file=sys.stderr)
            return 2

        file_summary = check_bib(
            content,
            resolver=_resolver,
            cited_keys=cited_keys,
            title_threshold=args.title_threshold,
            author_threshold=args.author_threshold,
        )

        combined_summary.total_entries += file_summary.total_entries
        combined_summary.checked_count += file_summary.checked_count
        combined_summary.matches += file_summary.matches
        combined_summary.mismatches += file_summary.mismatches
        combined_summary.not_resolved += file_summary.not_resolved
        combined_summary.unverifiable += file_summary.unverifiable
        combined_summary.no_doi += file_summary.no_doi
        combined_summary.skipped += file_summary.skipped
        combined_summary.results.extend(file_summary.results)

    if args.json:
        out = {
            "total_entries": combined_summary.total_entries,
            "checked_count": combined_summary.checked_count,
            "matches": combined_summary.matches,
            "mismatches": combined_summary.mismatches,
            "not_resolved": combined_summary.not_resolved,
            "unverifiable": combined_summary.unverifiable,
            "no_doi": combined_summary.no_doi,
            "skipped": combined_summary.skipped,
            "has_defects": combined_summary.has_defects,
            "results": [asdict(r) for r in combined_summary.results],
        }
        print(json.dumps(out, indent=2))
    else:
        print(format_summary_text(combined_summary, quiet=args.quiet))

    if combined_summary.has_defects:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
