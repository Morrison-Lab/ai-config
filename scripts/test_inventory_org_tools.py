#!/usr/bin/env python3
"""Tests for scripts/inventory-org-tools.py (ai-config#3936). No network."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "inventory_org_tools", Path(__file__).resolve().parent / "inventory-org-tools.py")
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)

failures = 0


def check(name, cond):
    global failures
    print(("PASS: " if cond else "FAIL: ") + name)
    failures += 0 if cond else 1


exts, pkg, lua = inv.classify_tree([
    "_extensions/Morrison-Lab/callouty-theorem/_extension.yml",
    "_extensions/quarto-ext/fontawesome/_extension.yaml",
    "_extensions/quarto-ext/fontawesome/fontawesome.lua",
    "sub/_extensions/a/b/_extension.yml",
    "_extensions/broken/_extension.yml",
    "DESCRIPTION", "R/fit.R",
    "filters/unlink-pages.lua", "math-xrefs.lua", "deep/dir/x.lua",
])
check("finds extensions at the root and nested, with .yml or .yaml",
      exts == {"Morrison-Lab/callouty-theorem", "quarto-ext/fontawesome", "a/b"})
check("an extension path missing its owner level is not an extension",
      "broken/_extension.yml" not in exts and not any(k.startswith("broken") for k in exts))
check("DESCRIPTION plus R/ is a package", pkg is True)
check("Lua filters: root and filters/ only, never inside _extensions/",
      lua == ["filters/unlink-pages.lua", "math-xrefs.lua"])
check("a Lua file in a subdirectory of filters/ is not counted",
      inv.classify_tree(["filters/sub/x.lua", "filters/y.lua"])[2] == ["filters/y.lua"])
check("DESCRIPTION without R/ is not a package",
      inv.classify_tree(["DESCRIPTION", "renv.lock"])[1] is False)

fields = inv.description_fields(
    "Package: lms\nTitle: Lab Model\n    Summaries\nVersion: 0.1\n")
check("DESCRIPTION fields fold continuation lines",
      fields == {"Package": "lms", "Title": "Lab Model Summaries"})
check("missing DESCRIPTION fields come back empty",
      inv.description_fields("Version: 1\n") == {"Package": "", "Title": ""})

md = inv.render("Morrison-Lab", {"Morrison-Lab/x": ["b", "a"], "other/y": ["a"]},
                [("psc", "lms", "Lab Model Summaries")], {"lds": ["filters/f.lua"]},
                ["big"], "3 checkouts", "2026-11-19 22:30 UTC")
check("render marks lab-owned extensions and sorts repos",
      "| `Morrison-Lab/x` | yes | a, b |" in md and "| `other/y` |  | a |" in md)
check("render states its scan size and time", "from 3 checkouts." in md and "2026-11-19 22:30 UTC" in md)
check("render reports truncated trees", "## Incomplete" in md and "big" in md)
check("render omits the Incomplete section when nothing was truncated",
      "## Incomplete" not in inv.render("o", {}, [], {}, [], "nothing", "t"))

check("an empty repository's 409 is recognized",
      inv.is_empty_repo_error('GET /repos/o/r/git/trees/main failed: 409 {"message":"Git Repository is empty."}'))
check("any other API failure is not read as an empty repository",
      not inv.is_empty_repo_error("GET /repos/o/r/git/trees/main failed: 404 Not Found")
      and not inv.is_empty_repo_error("GET /repos/o/r/git/trees/main failed: 409 Conflict"))

print(f"\n{failures} failed")
sys.exit(1 if failures else 0)
