#!/usr/bin/env python3
"""Tests for warn-irreplaceable-under-cache-label.py.

This guard's defensibility rests entirely on ONE negative: "Clear the Docker
build cache" must stay silent. It is a correct, common, everyday phrase, and a
guard that warned on it would be switched off within a day -- README's "a hook
that misfires is worse than a missing one" in its sharpest form. `S1` is that
case, and `M2` breaks the clause that protects it on purpose.

The positives test the design claim that motivated the hook: the LABEL is what
carries consent, so the reversible word is read from the label while the
irreplaceable item may be named anywhere in the option. `M1` and `M4` pull
those two halves apart.

A suite that passes against a deliberately broken matcher is not testing the
matcher, so the mutation section at the end asserts exactly which cases flip
for each load-bearing clause.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "warn-irreplaceable-under-cache-label.py")
SOURCE = open(HOOK, encoding="utf-8").read()

spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def ask(*opts, tool="AskUserQuestion"):
    """A PreToolUse payload carrying one question with these options."""
    return {
        "tool_name": tool,
        "tool_input": {"questions": [{
            "question": "How much should I clean up?",
            "header": "Cleanup",
            "multiSelect": False,
            "options": [{"label": lab, "description": desc}
                        for lab, desc in opts],
        }]},
    }


CASES = {
    # -- must warn ---------------------------------------------------------
    # The measured incident, verbatim in shape: a reversible label over a
    # bundle that includes a live filesystem.
    "W1": ask(("Clear its caches only",
               "Temp directory, npm cache, browser HTTP caches, downloaded "
               "ollama models, and the WSL2 distribution's ~26 GB of "
               "storage -- all regenerable bulk.")),
    # the disk image named by extension rather than by prose
    "W2": ask(("Remove temp files",
               r"Includes a stale D:\vm\scratch.vmdk left by a failed "
               "import.")),
    # a named volume, not a build cache
    "W3": ask(("Safe to delete",
               "Dangling docker volumes and overlay2 layers.")),
    # the promise made without the word "cache"
    "W4": ask(("Regenerable bulk",
               "Package downloads plus the Ubuntu ext4 filesystem.")),
    # a database's data directory
    "W5": ask(("Disposable state",
               "The Postgres data directory and the test fixtures.")),
    # the bad option sits second, after a well-formed one
    "W6": ask(("Nothing", "Leave everything alone."),
              ("Clear caches", "npm cache and the .vhdx for the dev VM.")),

    # -- must stay silent --------------------------------------------------
    # THE case. Correct phrase, correct action, must never warn.
    "S1": ask(("Clear the Docker build cache",
               "Prunes the build cache and dangling images; everything "
               "re-downloads on the next build.")),
    "S2": ask(("Clear caches",
               "npm cache, pip cache, browser HTTP cache, and Temp.")),
    # the honest split this guard exists to produce
    "S3": ask(("Delete the WSL2 distribution",
               "Removes ext4.vhdx and everything inside that Linux install. "
               "Irreversible."),
              ("Clear caches only", "npm and pip caches.")),
    # re-downloadable weights are genuinely regenerable
    "S4": ask(("Regenerable downloads",
               "Ollama models and HuggingFace weights; all re-downloadable.")),
    # a cleanup word that promises nothing about reversibility
    "S5": ask(("Cleanup unused VMs",
               r"Removes old .vmdk files from D:\vm.")),
    # the reversible word is in the DESCRIPTION, not the label, and the label
    # claims nothing -- the label is what carries consent
    "S6": ask(("Free up 40 GB",
               "Clears caches and the ext4.vhdx for the dev VM.")),
    # no option carries an irreplaceable item at all
    "S7": ask(("Clear temp", "Just the Temp directory.")),
    # a different tool must never be evaluated
    "S8": ask(("Clear caches", "npm cache and the dev VM's .vhdx."),
              tool="ExitPlanMode"),
    # a payload with no options at all
    "S9": {"tool_name": "AskUserQuestion",
           "tool_input": {"questions": [{"question": "Proceed?"}]}},
}

EXPECTED = {cid: cid.startswith("W") for cid in CASES}

WHY = {
    "S1": "THE false positive that would sink the guard -- a correct phrase",
    "S2": "every listed item genuinely rebuilds itself",
    "S3": "the irreplaceable item has its own honest option",
    "S4": "model weights re-download; that is what regenerable means",
    "S5": "'cleanup' promises nothing about reversibility",
    "S6": "the reversible word is not in the label, which carries consent",
    "S7": "nothing irreplaceable is named",
    "S8": "not an AskUserQuestion call",
    "S9": "no options to evaluate",
}

KNOWN_LIMITS = {
    "a mislabelling that avoids every listed reversible word ('tidy up the "
    "leftovers') is invisible -- this is a vocabulary matcher and the hook's "
    "own docstring says so",
    "a bare POSIX path (/home/work) is NOT treated as irreplaceable, because "
    "'clear /home/work/.cache/pip' is a correct cache option; only the words "
    "'home directory' qualify",
    "an irreplaceable item named only by a product name the list does not "
    "carry (a Proxmox .raw volume, an LVM logical volume) is missed",
}


def verdict(script, payload):
    out = subprocess.run(
        [sys.executable, script], input=json.dumps(payload),
        capture_output=True, text=True, timeout=60)
    return "additionalContext" in (out.stdout or "")


print("case tests (full payload through the hook):")
wrong = 0
for cid in sorted(CASES, key=lambda k: (k[0], int(k[1:]))):
    got = verdict(HOOK, CASES[cid])
    if got != EXPECTED[cid]:
        wrong += 1
        failures.append(f"{cid}: got warn={got}, want warn={EXPECTED[cid]} "
                        f"({WHY.get(cid, 'must warn')})")
print(f"  {len(CASES) - wrong}/{len(CASES)} cases behaved as declared")

# ---------------------------------------------------------------------------
# Unit-level assertions. The diagnostic must name the real label, the real
# reversible word, and the real item -- a guard that names the wrong thing
# loses credibility faster than one that stays silent.
hits = hook.find_mislabelled(CASES["W1"]["tool_input"])
check("names one option", len(hits), 1)
check("names the label", hits[0][0], "Clear its caches only")
check("names the reversible word", hits[0][1].lower(), "caches")
check("names the irreplaceable item",
      hits[0][2].lower().startswith("wsl2 distribution"), True)
check("options() finds both options of a two-option question",
      len(hook.options(CASES["S3"]["tool_input"])), 2)
check("docker build cache carries no irreplaceable item",
      hook.find_mislabelled(CASES["S1"]["tool_input"]), [])
check("bare 'docker' is not an irreplaceable trigger",
      bool(hook.IRREPLACEABLE.search("prune docker images")), False)
check("'docker volumes' is",
      bool(hook.IRREPLACEABLE.search("prune docker volumes")), True)

# ---------------------------------------------------------------------------
MUTATIONS = {
    "M1_reversible_word_read_from_label": (
        "the LABEL is what carries consent, so the reversible word is read "
        "from the label alone -- reading it from the whole option would "
        "warn on any option whose description merely mentions a cache",
        [("        word = REVERSIBLE.search(label)",
          "        word = REVERSIBLE.search(body)")],
        # S6 is the case: its label promises nothing ("Free up 40 GB") while
        # its description happens to say "clears caches", so widening to the
        # body invents a promise the user was never shown.
        #
        # S3 -- the honest split -- does NOT flip, and that is worth stating:
        # its irreplaceable option's description says "Irreversible" rather
        # than any reversible word, and its cache option names nothing
        # irreplaceable. The two halves stay in different options under either
        # reading, which is exactly what makes S3 the well-formed shape.
        {"S6"},
    ),
    "M2_docker_is_not_a_trigger": (
        "THE defensibility clause: `docker` alone must never qualify, or "
        "'clear the Docker build cache' warns every time and the guard "
        "gets switched off",
        [(r"\bdocker\s+volumes?\b", r"\bdocker\b")],
        {"S1"},
    ),
    "M3_reversible_list_is_closed": (
        "only words that INDEPENDENTLY promise the action rebuilds itself "
        "belong on the list -- a generic cleanup word promises nothing",
        [("      | junk | cruft", "      | junk | cruft | cleanup")],
        {"S5"},
    ),
    "M4_description_is_scanned_for_the_item": (
        "the irreplaceable item is usually named in the DESCRIPTION while "
        "the label carries the reversible word -- that split IS the "
        "incident, so dropping descriptions loses the case the hook exists "
        "for",
        [('                _strings(node, {"description", "detail", '
          '"details", "body",\n'
          '                                "explanation", "summary"}, parts)',
          "                parts = []")],
        {"W1", "W2", "W3", "W4", "W5", "W6"},
    ),
    "M5_tool_gate": (
        "a payload from another tool must never be evaluated",
        [('    if payload.get("tool_name") != "AskUserQuestion":\n'
          "        return 0",
          '    if payload.get("tool_name") == "__never__":\n        return 0')],
        {"S8"},
    ),
}

print("\nmutation tests (break one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is not present exactly "
                     f"once in {HOOK} (found {count}). The mutation harness is "
                     f"measuring nothing; re-derive the anchor.\n---\n{find}\n"
                     "---")
        mutated = mutated.replace(find, replace)

    fd, path = tempfile.mkstemp(suffix=".py", dir=HERE)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {cid for cid in CASES
                   if verdict(path, CASES[cid]) != EXPECTED[cid]}
    finally:
        os.unlink(path)

    ok = flipped == expected_flips
    mutation_wrong += not ok
    if not flipped and expected_flips:
        note = "NOTHING FLIPPED -- this clause is untested"
    elif ok:
        note = "flipped " + ", ".join(sorted(flipped))
    else:
        note = f"flipped {sorted(flipped)}, expected {sorted(expected_flips)}"
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<38} {statement}\n"
          f"         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under mutation")
print(f"{len(KNOWN_LIMITS)} known limits recorded (see KNOWN_LIMITS)")

if failures or mutation_wrong:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
