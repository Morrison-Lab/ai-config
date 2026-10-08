#!/usr/bin/env python3
"""Report claims in a prose diff that cite something the reader cannot check.

ai-config#3660.  #3643 took eleven review rounds for a three-file prose change,
and four of them (rounds 4, 8, 10 and 11) found a claim that a script could have
checked: a line citation past the end of its file, a phrase attributed to a file
that contains it nowhere, a quote attributed to an issue whose body does not
carry it, and "already recorded above" when it was not.
`shared/workflow/learn-from-review-findings.md` says a finding with a decidable
condition is one a pre-push check should catch every time thereafter; this is
that check.

## What it checks

Only the ADDED lines of Markdown and Quarto files in `git diff <base>...HEAD`,
outside fenced code blocks, so it reports on what the change claims rather than
on what the corpus already said.

* ``path-line`` --- a `path:N` or `path:N-M` citation.  The file must exist at
  HEAD (relative to the repo root, or to the citing file's directory) and have
  at least that many lines.
* ``quote-in-file`` --- a sentence that names a file, uses a verb of quotation
  (says, reads, states, ...), and carries a double-quoted phrase.  The phrase
  must appear in that file, compared with whitespace collapsed.
* ``quote-in-issue`` --- the same shape naming `#N` instead of a file.  This
  one needs the network, so it runs only with `--issues` and reads the issue
  body through `gh api`.
* ``corpus-state`` --- a claim about what the corpus does or does not contain
  ("already recorded", "the corpus has no", "nowhere else", ...).  No script
  can decide these, so each is listed for the author to back with the query
  that derived it; a line that already names `grep` or `rg`, or links its
  evidence, is not listed.

## Advisory by construction

It exits 0 whatever it finds.  The checks are heuristics over prose, and a
false positive on a legitimate paraphrase should cost a glance rather than a
push.  It reports how many added lines it examined, so a run that examined
nothing reads differently from a run that found nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import find_fence_spans  # noqa: E402

PROSE_GLOBS = ("*.md", "*.qmd")

PATH_LINE_RE = re.compile(
    r"(?<![\w/.-])(?P<path>[\w.-]+(?:/[\w.-]+)*\.[A-Za-z]{1,5}):(?P<start>\d+)"
    r"(?:-(?P<end>\d+))?(?![\w:])"
)
FILE_RE = re.compile(r"`(?P<path>[\w.-]+(?:/[\w.-]+)*\.[A-Za-z]{1,5})`")
ISSUE_RE = re.compile(r"(?<![\w/&])#(?P<num>\d{2,6})\b")
QUOTE_VERB_RE = re.compile(
    r"\b(says|said|reads|states|stated|writes|wrote|quotes|docstring|"
    r"proposes|proposed)\b",
    re.IGNORECASE,
)
QUOTED_RE = re.compile(r"\"(?P<text>[^\"]{12,})\"")
CORPUS_STATE_RE = re.compile(
    r"\b(already (recorded|covered|documented|stated)|the corpus (has|carries) "
    r"no|nothing in the corpus|nowhere else|no other (site|file|place|rule)|"
    r"is the only (site|file|place|rule|instance))\b",
    re.IGNORECASE,
)
DERIVED_RE = re.compile(r"\b(grep|rg|git grep|ripgrep)\b|\]\(")


def git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def added_lines(root: Path, base: str) -> dict[str, list[tuple[int, str]]]:
    """{path: [(line_number_at_HEAD, text), ...]} for added prose lines."""
    diff = git(
        ["diff", "-U0", "--no-color", "--no-ext-diff", f"{base}...HEAD", "--",
         *PROSE_GLOBS],
        root,
    )
    out: dict[str, list[tuple[int, str]]] = {}
    path = None
    lineno = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:]
            path = target[2:] if target.startswith("b/") else None
            continue
        if raw.startswith("@@"):
            m = re.match(r"@@ -\S+ \+(\d+)(?:,\d+)? @@", raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if path and raw.startswith("+"):
            out.setdefault(path, []).append((lineno, raw[1:]))
            lineno += 1
    return out


def resolve(root: Path, citing: str, cited: str) -> Path | None:
    for candidate in (root / cited, (root / citing).parent / cited):
        if candidate.is_file():
            return candidate
    return None


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def issue_body(num: str, repo: str | None, cache: dict[str, str | None]) -> str | None:
    if num in cache:
        return cache[num]
    target = f"repos/{repo}/issues/{num}" if repo else f"repos/{{owner}}/{{repo}}/issues/{num}"
    res = subprocess.run(["gh", "api", target, "--jq", ".body"],
                         capture_output=True, text=True)
    cache[num] = res.stdout if res.returncode == 0 else None
    if res.returncode != 0:
        print(f"check-prose-citations: cannot read issue #{num}: "
              f"{res.stderr.strip()}", file=sys.stderr)
    return cache[num]


def check_line(root: Path, citing: str, text: str, issues: bool,
               repo: str | None, cache: dict) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for m in PATH_LINE_RE.finditer(text):
        cited = m.group("path")
        last = int(m.group("end") or m.group("start"))
        target = resolve(root, citing, cited)
        if target is None:
            findings.append(("path-line", f"`{cited}` does not exist at HEAD"))
            continue
        count = len(target.read_text(errors="replace").splitlines())
        if last > count:
            findings.append(("path-line",
                             f"`{cited}:{last}` is past the end ({count} lines)"))
    quotes = [q.group("text") for q in QUOTED_RE.finditer(text)]
    if quotes and QUOTE_VERB_RE.search(text):
        for f in FILE_RE.finditer(text):
            target = resolve(root, citing, f.group("path"))
            if target is None:
                continue
            body = squash(target.read_text(errors="replace"))
            for q in quotes:
                if squash(q) not in body:
                    findings.append(("quote-in-file",
                                     f"\"{q}\" is not in `{f.group('path')}`"))
        if issues:
            for i in ISSUE_RE.finditer(text):
                body = issue_body(i.group("num"), repo, cache)
                if body is None:
                    findings.append(("quote-in-issue",
                                     f"#{i.group('num')} could not be read"))
                    continue
                for q in quotes:
                    if squash(q) not in squash(body):
                        findings.append(("quote-in-issue",
                                         f"\"{q}\" is not in #{i.group('num')}'s body"))
    if CORPUS_STATE_RE.search(text) and not DERIVED_RE.search(text):
        findings.append(("corpus-state",
                         "claim about corpus state with no query beside it"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="origin/main",
                        help="diff base (default: origin/main)")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--issues", action="store_true",
                        help="also check quotes attributed to #N (needs gh)")
    parser.add_argument("--repo", help="owner/repo for --issues")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        added = added_lines(root, args.base)
    except subprocess.CalledProcessError as exc:
        print(f"check-prose-citations: git diff against {args.base} failed: "
              f"{exc.stderr.strip()}", file=sys.stderr)
        return 0

    results = []
    examined = 0
    cache: dict[str, str | None] = {}
    for path, lines in sorted(added.items()):
        full = root / path
        if not full.is_file():
            continue
        fenced, _, _ = find_fence_spans(full.read_text(errors="replace"))
        for lineno, text in lines:
            if lineno - 1 in fenced:
                continue
            examined += 1
            for kind, detail in check_line(root, path, text, args.issues,
                                           args.repo, cache):
                results.append({"file": path, "line": lineno, "kind": kind,
                                "detail": detail})

    if args.json:
        print(json.dumps({"examined_lines": examined,
                          "files": len(added), "findings": results}, indent=2))
        return 0
    for r in results:
        print(f"::warning file={r['file']},line={r['line']}::"
              f"[{r['kind']}] {r['detail']}")
    print(f"check-prose-citations: examined {examined} added line(s) in "
          f"{len(added)} file(s) against {args.base}; {len(results)} "
          f"finding(s) (advisory){'' if args.issues else '; #N quotes not checked (--issues)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
