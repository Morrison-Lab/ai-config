#!/usr/bin/env python3
"""List the reusable tools that an organization's repositories carry (ai-config#3936).

Ezra asked for an inventory of "quarto extensions, R packages, etc.;
anything reusable" across our repositories. Such a list goes stale the
moment any repository vendors a new extension, so this script derives it
from each repository's default-branch tree instead of keeping a hand list.

It finds, per non-archived, non-fork repository:

* Quarto extensions: every ``_extensions/<owner>/<name>/_extension.yml``
  (or ``.yaml``), keyed by ``<owner>/<name>`` and listed with every
  repository that vendors it;
* R packages: a root ``DESCRIPTION`` next to a root ``R/`` directory, with
  the ``Package:`` and ``Title:`` fields read from the file;
* Lua filters: ``*.lua`` files at the root or under ``filters/``, outside
  ``_extensions/``.

Output is Markdown on stdout, headed with the time it was generated.

Usage:
    python3 scripts/inventory-org-tools.py [--org Morrison-Lab] [--repo NAME ...]

Needs GITHUB_TOKEN or GH_TOKEN. Any failed API read stops the run with the
path that failed (fail fast); a repository whose tree the API truncates is
reported, not silently shortened.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

_SPEC = importlib.util.spec_from_file_location(
    "build_pr_payload", Path(__file__).resolve().parent / "build-pr-payload.py")
_PAYLOAD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PAYLOAD)
rest_get = _PAYLOAD.rest_get

EXTENSION_RE = re.compile(r"(?:^|/)_extensions/([^/]+)/([^/]+)/_extension\.ya?ml$")
LUA_RE = re.compile(r"^(?:filters/)?[^/]+\.lua$")


def classify_tree(paths: Iterable[str]) -> Tuple[Set[str], bool, List[str]]:
    """Return (extension keys, is an R package, Lua filter paths) for one tree."""
    paths = list(paths)
    extensions = set()
    for p in paths:
        m = EXTENSION_RE.search(p)
        if m:
            extensions.add(f"{m.group(1)}/{m.group(2)}")
    is_package = "DESCRIPTION" in paths and any(p.startswith("R/") for p in paths)
    lua = sorted(p for p in paths if LUA_RE.match(p))
    return extensions, is_package, lua


def description_fields(text: str) -> Dict[str, str]:
    """Package and Title from an R DESCRIPTION file (DCF, continuation lines folded)."""
    fields: Dict[str, str] = {}
    key = None
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and key:
            fields[key] += " " + line.strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            fields[key] = value.strip()
    return {k: fields.get(k, "") for k in ("Package", "Title")}


def render(org: str, extensions: Dict[str, List[str]], packages: List[Tuple[str, str, str]],
           lua: Dict[str, List[str]], truncated: List[str], source: str, now: str) -> str:
    out = [f"# Reusable tools in {org} repositories", "",
           f"Generated {now} by `scripts/inventory-org-tools.py` from {source}.", ""]
    out += ["## Quarto extensions", "",
            "| Extension | Lab-owned | Vendored by |", "| --- | --- | --- |"]
    for key in sorted(extensions, key=str.lower):
        owned = "yes" if key.split("/")[0].lower() == org.lower() else ""
        out.append(f"| `{key}` | {owned} | {', '.join(sorted(extensions[key]))} |")
    out += ["", "## R packages", "", "| Repository | Package | Title |", "| --- | --- | --- |"]
    for repo, pkg, title in sorted(packages):
        out.append(f"| {repo} | `{pkg}` | {title} |")
    out += ["", "## Lua filters outside extensions", "",
            "| Repository | Filters |", "| --- | --- |"]
    for repo in sorted(lua):
        out.append(f"| {repo} | {', '.join(f'`{p}`' for p in lua[repo])} |")
    if truncated:
        out += ["", "## Incomplete", "",
                "The API truncated these trees, so their rows above may be missing items: "
                + ", ".join(sorted(truncated)) + "."]
    return "\n".join(out) + "\n"


def scan_paths(org: str, dirs: List[str]) -> int:
    """Inventory local checkouts: each one's HEAD tree, named by its directory."""
    import subprocess
    extensions: Dict[str, List[str]] = defaultdict(list)
    packages: List[Tuple[str, str, str]] = []
    lua: Dict[str, List[str]] = {}
    for d in dirs:
        root = Path(d).resolve()
        name = root.name
        listing = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", "HEAD"],
                                 capture_output=True, text=True, check=True).stdout
        exts, is_package, filters = classify_tree(listing.splitlines())
        for key in exts:
            extensions[key].append(name)
        if filters:
            lua[name] = filters
        if is_package:
            blob = subprocess.run(["git", "-C", str(root), "show", "HEAD:DESCRIPTION"],
                                  capture_output=True, text=True, check=True).stdout
            fields = description_fields(blob)
            packages.append((name, fields["Package"], fields["Title"]))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sys.stdout.write(render(org, extensions, packages, lua, [],
                            f"{len(dirs)} local checkouts' HEAD commits", now))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--org", default="Morrison-Lab")
    parser.add_argument("--repo", action="append", default=[],
                        help="Limit to these repository names (repeatable).")
    parser.add_argument("--path", action="append", default=[], metavar="DIR",
                        help="Scan local git checkouts instead of the API (repeatable). "
                             "Reads each checkout's committed HEAD tree, so an uncommitted "
                             "file is not counted.")
    args = parser.parse_args(argv)
    if args.path:
        return scan_paths(args.org, args.path)
    token = _PAYLOAD._token()

    if args.repo:
        # Read each named repository directly. A cloud session's token is
        # bound to its configured repositories and refuses the org listing
        # (403 "sessions are bound to their configured repositories").
        repos = [rest_get(f"/repos/{args.org}/{n}", token) for n in args.repo]
        skipped = [r["name"] for r in repos if r.get("archived") or r.get("fork")]
        if skipped:
            print(f"skipping archived or fork repositories: {', '.join(skipped)}", file=sys.stderr)
    else:
        repos = rest_get(f"/orgs/{args.org}/repos?type=all", token)
    repos = [r for r in repos if not r.get("archived") and not r.get("fork")]

    extensions: Dict[str, List[str]] = defaultdict(list)
    packages: List[Tuple[str, str, str]] = []
    lua: Dict[str, List[str]] = {}
    truncated: List[str] = []
    scanned = 0
    for r in sorted(repos, key=lambda r: r["name"].lower()):
        name, branch = r["name"], r.get("default_branch")
        if not branch or r.get("size", 0) == 0:
            continue  # an empty repository has no tree to read
        tree = rest_get(f"/repos/{args.org}/{name}/git/trees/{branch}?recursive=1", token)
        scanned += 1
        if tree.get("truncated"):
            truncated.append(name)
        paths = [e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"]
        exts, is_package, filters = classify_tree(paths)
        for key in exts:
            extensions[key].append(name)
        if filters:
            lua[name] = filters
        if is_package:
            blob = rest_get(f"/repos/{args.org}/{name}/contents/DESCRIPTION?ref={branch}", token)
            text = base64.b64decode(blob.get("content", "")).decode("utf-8", "replace")
            fields = description_fields(text)
            packages.append((name, fields["Package"], fields["Title"]))

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sys.stdout.write(render(args.org, extensions, packages, lua, truncated,
                            f"{scanned} non-archived, non-fork repositories' default branches",
                            now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
