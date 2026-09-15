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
    # a database's live volume. The first spelling said "Postgres data
    # directory", and `data directory` came off the list in review because a
    # fixture's recreated one is disposable (finding FP-6); `pgdata` is
    # specific enough to keep.
    "W5": ask(("Disposable state",
               "The pgdata volume and the test fixtures.")),
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

    # -- cases added from the adversarial review of a331d675 ---------------
    # FP-4: the reassurance the hook exists to PRODUCE. Naming an item in
    # order to say it is safe is the opposite of putting it at risk, and
    # warning here would punish the honest disclosure.
    "S10": ask(("Clear caches only",
                "npm and pip caches. Your WSL2 ext4.vhdx and home directory "
                "are untouched.")),
    "S11": ask(("Safe to delete",
                "Docker build cache and dangling images. Named docker "
                "volumes are preserved.")),
    "S12": ask(("Clear caches",
                "Removes ~/.cache only; no uncommitted work is affected.")),
    # FP-5: `docker builder prune` really does reclaim overlay2 layers, so
    # saying so is a correct sentence in a correct option.
    "S13": ask(("Clear the Docker build cache",
                "Prunes build cache; frees overlay2 layers that are "
                "dangling.")),
    # FP-6: a bare filesystem name shows up in cache contexts.
    "S14": ask(("Clear caches",
                "Removes the zfs ARC cache stats dump and the npm cache.")),
    # FP-6: an item the description says is recreated is disposable.
    "S15": ask(("Remove temp files",
                r"D:\vm\scratch.vmdk, recreated by the packer build.")),

    # -- must warn, added in the same pass ---------------------------------
    # reassurance about ONE item must not silence a second item that really
    # is at risk, so a guarded hit is skipped rather than ending the search
    "W7": ask(("Clear caches",
               "Your home directory is untouched. Also deletes the dev VM's "
               "ext4.vhdx.")),

    # -- cases added from round 2 of the adversarial review (b1694279) -----
    # R-9: a reassurance about something ELSE, in the same sentence as the
    # item being destroyed, disarmed the whole sentence. The comma form is
    # the natural English and was the untested one.
    "W8": ask(("Clear caches",
               "Purges the ext4.vhdx, leaving Windows files unaffected.")),
    "W9": ask(("Clear caches",
               "Deletes the ext4.vhdx, and the npm cache is preserved.")),
    "W10": ask(("Clear caches",
                "Wipes docker volumes, but the images are kept for the "
                "rebuild.")),
    # R-10: `remaining` and `keeps` are ordinary English in a destructive
    # sentence, and neither independently promises the item survives.
    "W11": ask(("Clear caches", "Deletes the remaining ext4.vhdx images.")),
    "W12": ask(("Clear caches",
                "Deletes everything the VM keeps, including its ext4.vhdx.")),
    # R-11: `?` and `!` end sentences too.
    "W13": ask(("Clear caches",
                "Deletes the dev VM's .vhdx? Home directory untouched.")),
    # ... and W15 is the one that ISOLATES that clause: no destructive verb
    # precedes the item, so only the sentence boundary keeps the next
    # sentence's reassurance from guarding it.
    "W15": ask(("Clear caches",
                "Includes the dev VM's .vhdx! Your home directory is "
                "untouched.")),
    # `remaining` with nothing destructive before the item -- the case that
    # isolates the preservation list's admission test from the precedence
    # rule that otherwise subsumes it.
    "W14": ask(("Clear caches", "The remaining ext4.vhdx images are stale.")),
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
    "S10": "naming an item to say it is SAFE is not putting it at risk",
    "S11": "the volumes are explicitly preserved",
    "S12": "the sentence says no uncommitted work is affected",
    "S13": "`docker builder prune` genuinely reclaims overlay2 layers",
    "S14": "a bare filesystem name appears in cache contexts",
    "S15": "an item the description says is recreated is disposable",
}

KNOWN_LIMITS = {
    "the polarity check is per SENTENCE, so a reassurance separated from its "
    "item by a full stop ('...and the ext4.vhdx. None of that is touched.') "
    "does not reach it",
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
        # every option that merely MENTIONS Docker starts warning, which is
        # the point: three of the suite's negatives say the word innocently
        {"S1", "S11", "S13"},
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
        # every positive, old and new: each names its irreplaceable item in
        # the description rather than in the label
        {"W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9",
         "W10", "W11", "W12", "W13", "W14", "W15"},
    ),
    "M6_preservation_guard": (
        "naming an item in order to say it is SAFE is the opposite of "
        "putting it at risk -- without this the well-formed option the hook "
        "exists to produce was the one that warned (finding FP-4)",
        [("        if (PRESERVED.search(sentence)\n"
          "                and not DESTRUCTIVE.search(sentence[:hit.start()])):\n"
          "            continue",
          "        if False:\n            continue")],
        {"S10", "S11", "S12", "S15"},
    ),
    "M7_overlay2_is_not_a_trigger": (
        "`overlay2` came off the irreplaceable list because a build-cache "
        "prune legitimately reclaims those layers -- the same admission "
        "test `docker` alone fails",
        [(r"  | \bpgdata\b", r"  | \bpgdata\b | \boverlay2\b")],
        {"S13"},
    ),
    "M8_sentence_split_keeps_filenames_whole": (
        "a sentence break is a period followed by space or end of string; a "
        "period inside `ext4.vhdx` is not one, and splitting there both hid "
        "the extension and stranded the reassurance in another fragment",
        [(r'SENTENCE = re.compile(r"(?:[.;!?](?=\s|$)|\n)+")',
          r'SENTENCE = re.compile(r"[.;\n]+")')],
        # S10's reassurance is stranded from `ext4`; W2's `.vmdk` and W6's
        # `.vhdx` are each cut in half, so the only irreplaceable item in
        # those options disappears
        # W15 joins them: its `!` boundary is also lost under a plain
        # `[.;\n]` split, so its reassurance guards the item beside it
        {"S10", "W2", "W6", "W13", "W15"},
    ),
    # -- clauses added in round 2, each covering code that round-2 review
    # broke with NOTHING flipping -- the gap that let R-9 and R-10 through.
    "M9_destructive_verb_precedence": (
        "a reassurance disarms an item only when nothing destructive is said "
        "about it first: 'Purges the ext4.vhdx, leaving Windows files "
        "unaffected' reassures about something ELSE",
        [("        if (PRESERVED.search(sentence)\n"
          "                and not DESTRUCTIVE.search(sentence[:hit.start()])):",
          "        if PRESERVED.search(sentence):")],
        # W11 is NOT here: `remaining` came off the preservation list, so
        # that case never depended on the precedence rule. M10 owns it.
        {"W8", "W9", "W10", "W12"},
    ),
    "M10_preserved_admission_test": (
        "`remaining` and `excluded` came off the preservation list for "
        "failing the same admission test that removed four entries from "
        "IRREPLACEABLE -- neither independently promises the item survives",
        [("      | survives? | survived\n    )",
          "      | survives? | survived | remains? | remaining | excluded\n    )")],
        # W14, not W11: W11 says "Deletes the remaining ...", so the
        # precedence rule fires it whichever way this list reads. Only a
        # sentence with no destructive verb before the item isolates it.
        {"W14"},
    ),
    "M11_bang_and_question_end_sentences": (
        "`?` and `!` end a sentence as surely as `.`, and without them a "
        "reassurance in the NEXT sentence guards the previous one's item",
        [(r'SENTENCE = re.compile(r"(?:[.;!?](?=\s|$)|\n)+")',
          r'SENTENCE = re.compile(r"(?:[.;](?=\s|$)|\n)+")')],
        {"W15"},
    ),
    "M12_label_is_its_own_sentence": (
        "the label joins the description as a SEPARATE sentence -- run "
        "together, a label like 'Remove temp files' puts a destructive verb "
        "in front of every item in the first description sentence and "
        "cancels the recreation exemption",
        [('found.append((label, ". ".join([label] + parts)))',
          'found.append((label, " ".join([label] + parts)))')],
        {"S15"},
    ),
    "M13_guarded_hit_is_skipped_not_final": (
        "a guarded hit is SKIPPED rather than ending the search, so an "
        "option that reassures about one item and destroys another still "
        "fires on the second",
        [("        if (PRESERVED.search(sentence)\n"
          "                and not DESTRUCTIVE.search(sentence[:hit.start()])):\n"
          "            continue",
          "        if (PRESERVED.search(sentence)\n"
          "                and not DESTRUCTIVE.search(sentence[:hit.start()])):\n"
          "            return None")],
        {"W7"},
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

    # NOT `dir=HERE`: `scripts/test_hooks.py` globs `hooks/*.py` for subjects
    # and requires a `test-<stem>.py` for each, so a mutant left behind by an
    # interrupted run reads as a hook with no test and fails CI (adversarial
    # review of a331d675, finding 3d). This hook imports nothing relative to
    # its own location.
    fd, path = tempfile.mkstemp(suffix=".py")
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
