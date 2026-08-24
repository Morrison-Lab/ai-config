#!/usr/bin/env python3
"""Compare a PR body's stated figures against the current head and git tree.

Verifies that verification numbers stated in a PR description match the reality
of the current HEAD commit:
1. `derived at <sha>` matches the PR's HEAD commit SHA.
2. Stated diff lines (`+N/-M`, `N added lines examined`) match `git diff --numstat`.
3. Stated file sizes (`N,NNN bytes`) match the file byte sizes at HEAD.
4. Tool denominators (links count, context fragments) match current head measurements.

Per `shared/workflow/fail-fast.md`, this always prints the count of figures it
examined so an empty or unparseable body is distinguishable from a body whose
figures matched (vacuous-zero detection).

Exit codes:
0: All examined figures match the current HEAD.
1: Mismatch found (stale SHA, wrong diff line count, wrong file size, etc.).
2: Usage / invocation error, or repository / PR could not be resolved.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import strip_fences  # noqa: E402

USAGE_EXIT = 2
MISMATCH_EXIT = 1
CLEAN_EXIT = 0


def die(message: str) -> None:
    """Print an error message to stderr and exit with usage code 2."""
    print(message, file=sys.stderr)
    raise SystemExit(USAGE_EXIT)


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> str:
    """Run a shell command and return stdout, or die with code 2 on error."""
    if cwd is not None and not Path(cwd).exists():
        raise RuntimeError(f"Working directory does not exist: {cwd}")
    try:
        # `encoding` is load-bearing on Windows; see the long note in
        # `check-pr-fully-clean.py`'s `run_cmd`. In short: the locale codec
        # there is cp1252, which turns most non-ASCII into silent mojibake and
        # hard-fails on five bytes, the hard failure leaving `stdout` as None
        # with `returncode` still 0. This script reads PR bodies, which are the
        # most emoji-dense payload GitHub serves, so it is more exposed than
        # most rather than less.
        res = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError:
        die(
            f"`{cmd[0]}` is not installed or not on PATH.\n"
            "This script requires git (and gh when querying pull requests)."
        )
    if res.returncode != 0:
        # See the long note in `check-pr-fully-clean.py`'s `run_cmd`. A non-zero
        # exit with readable stderr is a fact about the command; a non-zero exit
        # whose stderr could not be decoded is an environment failure, and only
        # `die` (SystemExit, so it escapes the broad `except Exception` in
        # `verify_pr_body_figures`) keeps it from being reported as UNVERIFIED
        # and exiting 0.
        if res.stderr is None:
            die(
                f"Command failed ({' '.join(cmd)}) and its stderr could not be "
                "read or decoded, so the reason is unavailable. This is an "
                "environment failure, not a finding about the PR."
            )
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {res.stderr.strip()}")
    if res.stdout is None:
        die(
            f"Command produced no capturable stdout ({' '.join(cmd)}); "
            "its output could not be read or decoded. This is an environment "
            "failure, not a finding about the PR."
        )
    return res.stdout.strip()


@dataclasses.dataclass
class StatedFigures:
    """Figures extracted from a PR body."""
    derived_at_sha: Optional[str] = None
    diff_additions: Optional[int] = None
    diff_deletions: Optional[int] = None
    added_lines_examined: Optional[int] = None
    prose_lines_examined: Optional[int] = None
    file_sizes: Dict[str, int] = dataclasses.field(default_factory=dict)
    links_count: Optional[int] = None
    links_files_count: Optional[int] = None
    context_fragments: Optional[int] = None
    linted_files: Optional[int] = None


@dataclasses.dataclass
class FigureResult:
    """Verification outcome for a single stated figure."""
    name: str
    stated: Any
    actual: Any
    status: str  # "MATCH", "MISMATCH", "UNVERIFIED"
    detail: str = ""


# Regex patterns for figures
DERIVED_SHA_RE = re.compile(
    r"(?i)(?:re-)?derived at [`'\"]?([0-9a-f]{7,40})[`'\"]?"
)
DIFF_STAT_RE = re.compile(
    r"\+(\d+)\s*/\s*-(\d+)"
)
ADDED_LINES_RE = re.compile(
    r"(?i)(?:\*\*)?(\d+)(?:\*\*)?\s+added lines examined"
)
PROSE_LINES_RE = re.compile(
    r"(?i)(?:\*\*)?(\d+)(?:\*\*)?\s+prose lines examined"
)
LINKS_RE = re.compile(
    r"(?i)(?:\*\*)?(\d+)(?:\*\*)?\s+links across\s+(?:\*\*)?(\d+)(?:\*\*)?\s+files"
)
FRAGMENTS_RE = re.compile(
    r"(?i)(?:\*\*)?(\d+)(?:\*\*)?\s+fragments examined"
)
LINTED_FILES_RE = re.compile(
    r"(?i)(?:\*\*)?(\d+)(?:\*\*)?\s+files linted"
)
# Matches markdown table rows like: | `path/to/file.ext` | [before bytes] | **NN,NNN** bytes |
FILE_SIZE_ROW_RE = re.compile(
    r"^\|\s*[`'\"]?([A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+)[`'\"]?\s*\|(?P<cols>.*)\|\s*$"
)
BYTES_CELL_RE = re.compile(
    r"(?:\*\*)?([0-9,]+)(?:\*\*)?\s*bytes"
)


def extract_verification_section(body: str) -> str:
    """Extract the verification section from PR body, excluding corrections logs."""
    # Find ## Verification heading
    m = re.search(r"(?im)^##?\s+Verification\b", body)
    if not m:
        return body

    start_pos = m.end()
    rest = body[start_pos:]

    # Cut off at ## Corrections or ### Corrections if present
    corr_m = re.search(r"(?im)^###?\s+Corrections\b", rest)
    if corr_m:
        rest = rest[:corr_m.start()]
    else:
        # Cut off at next top-level heading ^## [A-Za-z]
        next_heading = re.search(r"(?im)^##\s+[A-Za-z]", rest)
        if next_heading:
            rest = rest[:next_heading.start()]

    return rest


def parse_body_figures(body: str) -> StatedFigures:
    """Parse all verifiable figures out of a PR body."""
    figures = StatedFigures()
    if not body:
        return figures

    verif_text = extract_verification_section(body)

    # 1. Stated SHA
    sha_match = DERIVED_SHA_RE.search(verif_text)
    if sha_match:
        figures.derived_at_sha = sha_match.group(1)

    # 2. Diff stats: +N/-M
    # Prefer diff stats from verification section, fallback to whole body
    diff_m = DIFF_STAT_RE.search(verif_text) or DIFF_STAT_RE.search(body)
    if diff_m:
        figures.diff_additions = int(diff_m.group(1))
        figures.diff_deletions = int(diff_m.group(2))

    # 3. Added lines examined
    added_m = ADDED_LINES_RE.search(verif_text) or ADDED_LINES_RE.search(body)
    if added_m:
        figures.added_lines_examined = int(added_m.group(1))

    # 4. Prose lines examined
    prose_m = PROSE_LINES_RE.search(verif_text) or PROSE_LINES_RE.search(body)
    if prose_m:
        figures.prose_lines_examined = int(prose_m.group(1))

    # 5. Links across files
    links_m = LINKS_RE.search(verif_text) or LINKS_RE.search(body)
    if links_m:
        figures.links_count = int(links_m.group(1))
        figures.links_files_count = int(links_m.group(2))

    # 6. Context fragments examined
    frag_m = FRAGMENTS_RE.search(verif_text) or FRAGMENTS_RE.search(body)
    if frag_m:
        figures.context_fragments = int(frag_m.group(1))

    # 7. Files linted
    lint_m = LINTED_FILES_RE.search(verif_text) or LINTED_FILES_RE.search(body)
    if lint_m:
        figures.linted_files = int(lint_m.group(1))

    # 8. File size table rows
    for line in verif_text.splitlines():
        line = line.strip()
        row_m = FILE_SIZE_ROW_RE.match(line)
        if not row_m:
            continue
        path_str = row_m.group(1)
        cols = row_m.group("cols")
        # Split remaining columns by |
        col_parts = [c.strip() for c in cols.split("|") if c.strip()]
        if not col_parts:
            continue
        # The last column with bytes is the "after" byte count
        for col in reversed(col_parts):
            bytes_m = BYTES_CELL_RE.search(col)
            if bytes_m:
                size_num = int(bytes_m.group(1).replace(",", ""))
                figures.file_sizes[path_str] = size_num
                break

    return figures


def get_git_diff_numstat(
    repo_root: Path, base: str, head: str
) -> Tuple[int, int, int, Dict[str, Tuple[int, int]]]:
    """Derive additions, deletions, changed file count, and per-file stats from git."""
    # Find merge base if needed
    try:
        merge_base = run_cmd(["git", "merge-base", base, head], cwd=repo_root)
        diff_range = f"{merge_base}...{head}"
    except Exception:
        diff_range = f"{base}...{head}"

    out = run_cmd(["git", "diff", "--numstat", diff_range], cwd=repo_root)
    total_adds = 0
    total_dels = 0
    file_count = 0
    per_file: Dict[str, Tuple[int, int]] = {}

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            add_str, del_str, file_path = parts[0], parts[1], parts[2]
            if add_str == "-" or del_str == "-":
                # Binary file
                file_count += 1
                continue
            adds = int(add_str)
            dels = int(del_str)
            total_adds += adds
            total_dels += dels
            file_count += 1
            per_file[file_path] = (adds, dels)

    return total_adds, total_dels, file_count, per_file


def get_git_file_size(repo_root: Path, head: str, file_path: str) -> Optional[int]:
    """Get the exact byte size of a file at the given commit object."""
    try:
        out = run_cmd(["git", "cat-file", "-s", f"{head}:{file_path}"], cwd=repo_root)
        return int(out)
    except Exception:
        # If object is not found in git database, try reading from disk if HEAD matches
        local_file = repo_root / file_path
        if local_file.is_file():
            return local_file.stat().st_size
        return None


def get_link_counts(repo_root: Path) -> Optional[Tuple[int, int]]:
    """Count markdown links across files in repo_root matching check-links.py scope."""
    try:
        link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        inline_re = re.compile(r"`[^`]*`")
        scan_globs = [
            "skills/**/*.md",
            "codex-skills/**/*.md",
            "commands/**/*.md",
            "docs/**/*.md",
            "memories/**/*.md",
            "references/**/*.md",
            "shared/**/*.md",
            "*.md",
        ]
        skip_prefixes = ("http://", "https://", "mailto:", "tel:", "#")
        files_checked = 0
        total_links = 0
        seen_files = set()

        for g in scan_globs:
            for md in repo_root.glob(g):
                if not md.is_file() or md in seen_files:
                    continue
                seen_files.add(md)
                text = md.read_text(encoding="utf-8")
                text = strip_fences(text)
                text = inline_re.sub("", text)
                files_checked += 1
                for m in link_re.finditer(text):
                    tgt = m.group(1).strip()
                    if tgt.startswith("<") and tgt.endswith(">"):
                        tgt = tgt[1:-1].strip()
                    tgt = tgt.split(" ", 1)[0]
                    if not tgt or tgt.startswith(skip_prefixes) or "://" in tgt:
                        continue
                    if "<" in tgt or ">" in tgt:
                        continue
                    total_links += 1

        return total_links, files_checked
    except Exception:
        return None


def get_context_fragment_count(repo_root: Path) -> Optional[int]:
    """Count fragments examined by check-context-closure."""
    try:
        fragments = list((repo_root / "shared").rglob("*.md"))
        fragments.extend((repo_root / "memories").rglob("*.md"))
        return len([f for f in fragments if f.is_file()])
    except Exception:
        return None


def verify_pr_body_figures(
    stated: StatedFigures,
    repo_root: Path,
    base: str,
    head: str,
    verify_live_tools: bool = False,
) -> List[FigureResult]:
    """Verify extracted PR body figures against git diff and object database."""
    results: List[FigureResult] = []

    # 1. Derived at SHA check
    if stated.derived_at_sha is not None:
        stated_sha = stated.derived_at_sha.lower()
        head_sha = head.lower()
        is_match = head_sha.startswith(stated_sha) or stated_sha.startswith(
            head_sha[: len(stated_sha)]
        )
        status = "MATCH" if is_match else "MISMATCH"
        detail = (
            f"Stated derivation SHA `{stated.derived_at_sha}` matches head `{head[:8]}`"
            if is_match
            else f"Stated derivation SHA `{stated.derived_at_sha}` does not match current head `{head[:8]}`"
        )
        results.append(
            FigureResult(
                name="derived_at_sha",
                stated=stated.derived_at_sha,
                actual=head[: len(stated.derived_at_sha)],
                status=status,
                detail=detail,
            )
        )

    # 2. Git diff stats check
    try:
        actual_adds, actual_dels, actual_files, _ = get_git_diff_numstat(
            repo_root, base, head
        )

        if stated.diff_additions is not None and stated.diff_deletions is not None:
            is_match = (
                stated.diff_additions == actual_adds
                and stated.diff_deletions == actual_dels
            )
            status = "MATCH" if is_match else "MISMATCH"
            stated_str = f"+{stated.diff_additions}/-{stated.diff_deletions}"
            actual_str = f"+{actual_adds}/-{actual_dels}"
            detail = (
                f"Stated diff stats {stated_str} match git diff {actual_str}"
                if is_match
                else f"Stated diff stats {stated_str} mismatch git diff {actual_str}"
            )
            results.append(
                FigureResult(
                    name="diff_add_del",
                    stated=stated_str,
                    actual=actual_str,
                    status=status,
                    detail=detail,
                )
            )

        if stated.added_lines_examined is not None:
            is_match = stated.added_lines_examined == actual_adds
            status = "MATCH" if is_match else "MISMATCH"
            detail = (
                f"Stated added lines ({stated.added_lines_examined}) match diff additions ({actual_adds})"
                if is_match
                else f"Stated added lines ({stated.added_lines_examined}) mismatch diff additions ({actual_adds})"
            )
            results.append(
                FigureResult(
                    name="added_lines_examined",
                    stated=stated.added_lines_examined,
                    actual=actual_adds,
                    status=status,
                    detail=detail,
                )
            )

    except Exception as e:
        if stated.diff_additions is not None:
            results.append(
                FigureResult(
                    name="diff_stat",
                    stated=f"+{stated.diff_additions}/-{stated.diff_deletions}",
                    actual=None,
                    status="UNVERIFIED",
                    detail=f"Could not compute git diff ({e})",
                )
            )

    # 3. File sizes check
    for file_path, stated_size in stated.file_sizes.items():
        actual_size = get_git_file_size(repo_root, head, file_path)
        if actual_size is not None:
            is_match = stated_size == actual_size
            status = "MATCH" if is_match else "MISMATCH"
            detail = (
                f"`{file_path}` size {stated_size:,} bytes matches head"
                if is_match
                else f"`{file_path}` stated {stated_size:,} bytes != head size {actual_size:,} bytes"
            )
            results.append(
                FigureResult(
                    name=f"file_size:{file_path}",
                    stated=stated_size,
                    actual=actual_size,
                    status=status,
                    detail=detail,
                )
            )
        else:
            results.append(
                FigureResult(
                    name=f"file_size:{file_path}",
                    stated=stated_size,
                    actual=None,
                    status="MISMATCH",
                    detail=f"`{file_path}` not found in git tree at head {head[:8]}",
                )
            )

    # 4. Live tools verification (optional / if enabled)
    if verify_live_tools:
        if stated.links_count is not None and stated.links_files_count is not None:
            link_stats = get_link_counts(repo_root)
            if link_stats is not None:
                actual_links, actual_files = link_stats
                is_match = (
                    stated.links_count == actual_links
                    and stated.links_files_count == actual_files
                )
                status = "MATCH" if is_match else "MISMATCH"
                detail = (
                    f"Links ({stated.links_count}/{stated.links_files_count} files) match"
                    if is_match
                    else f"Links stated ({stated.links_count}/{stated.links_files_count}) mismatch actual ({actual_links}/{actual_files})"
                )
                results.append(
                    FigureResult(
                        name="links_count",
                        stated=f"{stated.links_count} links across {stated.links_files_count} files",
                        actual=f"{actual_links} links across {actual_files} files",
                        status=status,
                        detail=detail,
                    )
                )

        if stated.context_fragments is not None:
            frag_count = get_context_fragment_count(repo_root)
            if frag_count is not None:
                is_match = stated.context_fragments == frag_count
                status = "MATCH" if is_match else "MISMATCH"
                detail = (
                    f"Context fragments ({stated.context_fragments}) match"
                    if is_match
                    else f"Context fragments stated ({stated.context_fragments}) mismatch actual ({frag_count})"
                )
                results.append(
                    FigureResult(
                        name="context_fragments",
                        stated=stated.context_fragments,
                        actual=frag_count,
                        status=status,
                        detail=detail,
                    )
                )

    return results


def resolve_pr_info(
    pr_target: Optional[str], repo: Optional[str] = None
) -> Tuple[str, str, str, str]:
    """Resolve PR body, headRefOid, baseRefName, and PR number via gh CLI."""
    cmd = ["gh", "pr", "view"]
    if pr_target:
        cmd.append(pr_target)
    if repo:
        cmd.extend(["-R", repo])
    cmd.extend(["--json", "number,body,headRefOid,baseRefName"])

    out_json = run_cmd(cmd)
    data = json.loads(out_json)
    pr_number = str(data.get("number", ""))
    body = data.get("body", "") or ""
    head_sha = data.get("headRefOid", "") or ""
    base_ref = data.get("baseRefName", "") or "main"
    return pr_number, body, head_sha, base_ref


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify figures in a PR body against current git HEAD and diff."
    )
    parser.add_argument(
        "pr",
        nargs="?",
        default=None,
        help="PR number, URL, or branch name (defaults to current branch's PR)",
    )
    parser.add_argument(
        "-R",
        "--repo",
        default=None,
        help="Target GitHub repository as OWNER/REPO",
    )
    parser.add_argument(
        "--head",
        default=None,
        help="Explicit HEAD commit SHA to verify against",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Explicit base commit/branch to diff against (e.g. origin/main)",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="Raw PR body text to verify instead of fetching via gh",
    )
    parser.add_argument(
        "--body-file",
        default=None,
        help="Path to file containing PR body text to verify",
    )
    parser.add_argument(
        "--verify-live-tools",
        action="store_true",
        help="Also re-derive live link and context closure counts against disk",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON results",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only output summary line and exit code",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    pr_number = ""
    body = ""
    head_sha = args.head
    base_ref = args.base

    # Resolve body and git refs
    if args.body_file:
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
        except Exception as e:
            die(f"Could not read body file {args.body_file}: {e}")
    elif args.body is not None:
        body = args.body
    else:
        try:
            pr_number, body, gh_head, gh_base = resolve_pr_info(args.pr, args.repo)
            if not head_sha:
                head_sha = gh_head
            if not base_ref:
                base_ref = gh_base
        except Exception as e:
            die(f"Could not resolve PR details: {e}")

    if not head_sha:
        try:
            head_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root)
        except Exception as e:
            die(f"Could not determine HEAD SHA: {e}")

    if not base_ref:
        base_ref = "origin/main"

    stated = parse_body_figures(body)
    results = verify_pr_body_figures(
        stated,
        repo_root,
        base_ref,
        head_sha,
        verify_live_tools=args.verify_live_tools,
    )

    examined_count = len(results)
    matches = [r for r in results if r.status == "MATCH"]
    mismatches = [r for r in results if r.status == "MISMATCH"]
    unverified = [r for r in results if r.status == "UNVERIFIED"]

    if args.json:
        out_data = {
            "pr": pr_number,
            "head": head_sha,
            "base": base_ref,
            "examined_count": examined_count,
            "matches_count": len(matches),
            "mismatches_count": len(mismatches),
            "unverified_count": len(unverified),
            "results": [dataclasses.asdict(r) for r in results],
            "clean": len(mismatches) == 0,
        }
        print(json.dumps(out_data, indent=2))
        return MISMATCH_EXIT if mismatches else CLEAN_EXIT

    # Prose output
    target_desc = f"PR #{pr_number}" if pr_number else "PR body"
    print(f"Verifying figures for {target_desc} at HEAD {head_sha[:8]}...")

    if not args.quiet:
        for r in results:
            glyph = "✓" if r.status == "MATCH" else ("✗" if r.status == "MISMATCH" else "?")
            print(f"  {glyph} [{r.status}] {r.name}: {r.detail}")

    # Summary per fail-fast.md
    if examined_count == 0:
        print(
            f"NOTE: Examined 0 figures in {target_desc}. No verification table or parseable figures found."
        )
    else:
        print(
            f"Summary: Examined {examined_count} figures --- {len(matches)} matched, {len(mismatches)} mismatched, {len(unverified)} unverified."
        )

    if mismatches:
        print(f"FAIL: {len(mismatches)} figure(s) in {target_desc} mismatch current HEAD {head_sha[:8]}.")
        return MISMATCH_EXIT

    return CLEAN_EXIT


if __name__ == "__main__":
    sys.exit(main())
