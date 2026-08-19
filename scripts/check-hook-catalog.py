#!/usr/bin/env python3
"""Assert README's hook catalog and `hooks/hooks.json` describe the same hooks.

`hooks/hooks.json` is what actually binds a hook to an event; README's
"Enforcement hooks" table is what a human reads to find out which guards exist.
Nothing kept the two in step, and they drifted apart in both directions
(ai-config#1206). The two directions fail differently, and the second is worse:

  registered but undocumented  -- the guard runs on every session while the
                                  catalog a reader consults says it does not
                                  exist.
  documented but unregistered  -- the README asserts an active guard that never
                                  fires. This is the failure mode the corpus
                                  already warns about at length: an unregistered
                                  guard and a guard with nothing to block look
                                  identical, because neither ever produces
                                  output. A README row is then positive evidence
                                  for something inert.

Per `shared/workflow/algorithmatize-checks.md`, "do these two sets match" is
decidable over data both files already carry, so it belongs in an instrument
rather than in anyone's periodic reading. The drift grew by one entry in the ten
days between #1206 being filed and being fixed, which is the argument for
gating it rather than only reconciling it once.

This checks three things:

  1. Every hook registered in `hooks.json` has a README row.
  2. Every hook with a README row is registered in `hooks.json`, unless it is in
     `KNOWN_UNREGISTERED` -- and an allowlisted hook's row must SAY it is not
     registered, so the table never reads as an active guard.
  3. For a hook in both, README's stated event and matcher match the binding.

Check 3 is what stops the table drifting in a way the set comparison cannot see:
a row can name every hook correctly and still tell a reader the wrong event.

Hard-gating rather than advisory. Unlike a file-length threshold, nothing here
is a judgment call -- the two sets either match or they do not.

Run: python3 scripts/check-hook-catalog.py
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")
README = os.path.join(ROOT, "README.md")

# Hooks documented in README but deliberately NOT registered, each mapped to
# the issue tracking its activation. An explicit, reviewable list -- not a
# silent gap -- mirroring KNOWN_UNTESTED in scripts/test_hooks.py. This list
# should only ever shrink: registering a hook, or dropping its README row,
# means removing it from here.
#
# Keyed per entry rather than sharing one issue number, because the entries
# are unregistered for different reasons and a reader of the printed NOTE
# would otherwise be sent to the wrong tracker. #1505 covers two hooks that
# were registered nowhere by oversight; #1527's hook is inert BY THE GATE,
# since README's activation rule makes the hooks.json entry itself the
# plugin-path activation, so it is registered by the follow-up after its
# authoring PR merges.
KNOWN_UNREGISTERED = {}

# The README row of an allowlisted hook must contain this, so the table states
# the hook is inert rather than describing it as an active guard.
UNREGISTERED_MARKER = "not registered"

# Heading that opens the catalog section, and the row shape inside it. Bounding
# the scan to one section keeps an unrelated table elsewhere in README from
# being read as hook rows.
SECTION_HEADING = "## Enforcement hooks"

# | `name.py` | `Event` (Matcher) | prose |   -- matcher is optional.
ROW = re.compile(
    r"^\|\s*`(?P<script>[A-Za-z0-9._-]+\.(?:py|sh))`\s*"
    r"\|\s*`(?P<event>[A-Za-z0-9_, ]+)`\s*(?:\((?P<matcher>[A-Za-z0-9_.*, -]+)\))?\s*"
    r"\|(?P<rest>.*)\|\s*$"
)


def registered():
    """{script: (event, matcher)} for every hook bound in hooks/hooks.json."""
    with open(HOOKS_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    for event, groups in data["hooks"].items():
        for group in groups:
            matcher = group.get("matcher") or ""
            for entry in group.get("hooks", []):
                script = entry.get("script")
                if script:
                    if script in out:
                        prev_event, prev_matcher = out[script]
                        if prev_event == event:
                            matchers = [m for m in (prev_matcher, matcher) if m]
                            out[script] = (event, ", ".join(matchers))
                        else:
                            events = f"{prev_event}, {event}"
                            matchers = [m for m in (prev_matcher, matcher) if m]
                            out[script] = (events, ", ".join(matchers))
                    else:
                        out[script] = (event, matcher)
    return out


def documented():
    """{script: (event, matcher, row_text)} for every row in README's catalog.

    Raises SystemExit if the section or its table cannot be found -- a parser
    that silently returns nothing would make every set comparison vacuously
    pass, which is the shape `shared/principles/fail-fast.md` warns about.
    """
    with open(README, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    start = next((i for i, ln in enumerate(lines)
                  if ln.startswith(SECTION_HEADING)), None)
    if start is None:
        sys.exit(f"FAIL: no {SECTION_HEADING!r} section in README.md; "
                 "this check cannot run")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))

    out = {}
    for ln in lines[start:end]:
        m = ROW.match(ln)
        if m:
            out[m.group("script")] = (
                m.group("event"), m.group("matcher") or "", m.group("rest"))
    if not out:
        sys.exit(f"FAIL: parsed 0 hook rows from README's {SECTION_HEADING!r} "
                 "section; the table shape changed and this check is blind")
    return out


def check(reg, doc):
    """Compare the two catalogs. Returns the failure count."""
    failures = 0

    for script in sorted(set(reg) - set(doc)):
        event, matcher = reg[script]
        where = f"{event}" + (f" ({matcher})" if matcher else "")
        print(f"FAIL: hooks/{script} is registered ({where}) but has no README "
              "row; add one to the Enforcement hooks table")
        failures += 1

    for script in sorted(set(doc) - set(reg)):
        if script in KNOWN_UNREGISTERED:
            if UNREGISTERED_MARKER in doc[script][2]:
                print(f"NOTE: {script} is documented but not registered "
                      f"(known, ai-config#{KNOWN_UNREGISTERED[script]})")
            else:
                print(f"FAIL: {script} is in KNOWN_UNREGISTERED but its README "
                      f"row does not say {UNREGISTERED_MARKER!r}, so the table "
                      "reads as an active guard")
                failures += 1
        else:
            print(f"FAIL: hooks/{script} has a README row but is not "
                  "registered in hooks/hooks.json, so it never fires; "
                  "register it, or add it to KNOWN_UNREGISTERED with a "
                  "tracking issue")
            failures += 1

    # An allowlisted hook that has since been registered should leave the list,
    # so the debt cannot linger as silently satisfied.
    for script in sorted(KNOWN_UNREGISTERED):
        if script in reg:
            print(f"FAIL: {script} is now registered; drop it from "
                  "KNOWN_UNREGISTERED")
            failures += 1
        elif script not in doc:
            print(f"FAIL: {script} is in KNOWN_UNREGISTERED but has no README "
                  "row; drop it from the allowlist")
            failures += 1

    for script in sorted(set(reg) & set(doc)):
        want_event, want_matcher = reg[script]
        got_event, got_matcher, _ = doc[script]
        if (want_event, want_matcher) != (got_event, got_matcher):
            def fmt(e, m):
                return e + (f" ({m})" if m else "")
            print(f"FAIL: {script} README says {fmt(got_event, got_matcher)} "
                  f"but hooks.json binds {fmt(want_event, want_matcher)}")
            failures += 1

    return failures


def main() -> int:
    reg = registered()
    doc = documented()
    failures = check(reg, doc)

    print(f"\n{len(reg)} hooks registered in hooks.json; {len(doc)} documented "
          f"in README ({len(KNOWN_UNREGISTERED)} known unregistered); "
          f"{len(set(reg) & set(doc))} compared for event and matcher")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
