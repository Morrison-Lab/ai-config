#!/usr/bin/env python3
"""Check that tui-alloc's README states the script's own defaults.

`dotfiles/shiva/config/tui-alloc/README.md` hand-states four defaults
that `dotfiles/shiva/bin/tui-alloc` owns as `${VAR:-default}` expansions
plus an `--exclude` flag.
The README line went stale twice (12h -> 24h -> 48h) before #1227 asked
for this instrument, so drift fails loudly here instead of waiting for a
reader to notice.

Exit codes carry meaning (per `shared/principles/fail-fast.md`):
0 = README agrees with the script; 1 = drift (the defect this guards);
2 = parse failure (either file no longer matches the expected shape, so
the check could not run --- never reported as a pass).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "dotfiles/shiva/bin/tui-alloc"
README = ROOT / "dotfiles/shiva/config/tui-alloc/README.md"

# Anchored to the salloc flag lines themselves (leading whitespace only,
# then the flag): the header comment quotes flags in prose examples
# (`#   tui-alloc codex --exclude=c1,c2`), and an unanchored pattern
# matched that example instead of the real flag -- caught by this
# suite's live-corpus control before first merge.
CPUS = re.compile(r'^\s*--cpus-per-task="\$\{ALLOC_CPUS:-([^}]+)\}"', re.M)
MEM = re.compile(r'^\s*--mem="\$\{ALLOC_MEM:-([^}]+)\}"', re.M)
TIME = re.compile(r'^\s*--time="\$\{ALLOC_TIME:-([^}]+)\}"', re.M)
EXCLUDE = re.compile(r"^\s*--exclude=(\S+?)\s*\\?$", re.M)
# The README's claim line, e.g.
#   (defaults: 8 hwthreads / 32G / 48h, off GPU node c1)
CLAIM = re.compile(
    r"defaults: (\S+) hwthreads / (\S+) / (\S+), off GPU node (\S+)\)"
)

# Every walltime spelling salloc accepts. Checked before compaction, so a
# script value SLURM would reject -- the README's own "7d" shorthand, most
# plausibly -- is refused here rather than compacting to itself and
# comparing equal against the README that taught it.
SLURM_TIME = re.compile(
    r"""\d+                    # minutes
      | \d+:\d\d               # minutes:seconds
      | \d+:\d\d:\d\d          # hours:minutes:seconds
      | \d+-\d\d?              # days-hours
      | \d+-\d\d?:\d\d         # days-hours:minutes
      | \d+-\d\d?:\d\d:\d\d    # days-hours:minutes:seconds
    """,
    re.X,
)


def compact_time(slurm_time: str) -> str:
    """Render a SLURM walltime the way the README states it (48h, 7d).

    Both SLURM forms the default has used are handled: HH:MM:SS, and the
    D-HH:MM:SS form the 7-day default introduced. Any other accepted SLURM
    spelling is returned unchanged, so the README must then state it
    verbatim; `parse_script` has already refused anything SLURM would not
    accept at all, which is what stops an unknown value compacting to
    itself and matching a README that copied it.
    """
    m = re.fullmatch(r"(\d+)-(\d\d):(\d\d):(\d\d)", slurm_time)
    if m and m.group(2) == "00" and m.group(3) == "00" and m.group(4) == "00":
        return f"{int(m.group(1))}d"
    m = re.fullmatch(r"(\d+):(\d\d):(\d\d)", slurm_time)
    if m and m.group(2) == "00" and m.group(3) == "00":
        return f"{int(m.group(1))}h"
    return slurm_time


def parse_script(text: str) -> dict[str, str]:
    values = {}
    for name, rx in (("cpus", CPUS), ("mem", MEM), ("time", TIME),
                     ("exclude", EXCLUDE)):
        m = rx.search(text)
        if not m:
            print(f"parse failure: no {name} default found in the script"
                  " -- its flag shape changed; update this check's"
                  " patterns rather than letting it go vacuous",
                  file=sys.stderr)
            sys.exit(2)
        values[name] = m.group(1)
    if not re.fullmatch(SLURM_TIME, values["time"]):
        print(f"parse failure: the script's walltime {values['time']!r} is"
              " not a spelling salloc accepts -- fix the script rather than"
              " teaching this check to compare an invalid value",
              file=sys.stderr)
        sys.exit(2)
    return values


def parse_readme(text: str) -> dict[str, str]:
    m = CLAIM.search(text)
    if not m:
        print("parse failure: no 'defaults: ...' claim line found in the"
              " README -- its wording changed; update this check's CLAIM"
              " pattern rather than letting it go vacuous", file=sys.stderr)
        sys.exit(2)
    return {"cpus": m.group(1), "mem": m.group(2), "time": m.group(3),
            "exclude": m.group(4)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--script", type=Path, default=SCRIPT)
    ap.add_argument("--readme", type=Path, default=README)
    args = ap.parse_args()

    script_vals = parse_script(args.script.read_text(encoding="utf-8"))
    readme_vals = parse_readme(args.readme.read_text(encoding="utf-8"))
    expected = dict(script_vals)
    expected["time"] = compact_time(expected["time"])

    drift = [
        f"  {name}: script says {expected[name]!r}, README says"
        f" {readme_vals[name]!r}"
        for name in ("cpus", "mem", "time", "exclude")
        if expected[name] != readme_vals[name]
    ]
    print(f"Compared 4 defaults from {args.script.name} against"
          f" {args.readme.name}: "
          + ", ".join(f"{k}={v}" for k, v in expected.items()))
    if drift:
        print("README defaults drifted from the script (see #1227):")
        print("\n".join(drift))
        sys.exit(1)
    print("README agrees with the script.")


if __name__ == "__main__":
    main()
