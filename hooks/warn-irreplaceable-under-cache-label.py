#!/usr/bin/env python3
"""PreToolUse reminder: an `AskUserQuestion` option whose LABEL says
"cache"/"temp" while the option itself names irreplaceable storage.

WHAT HAPPENED
-------------
Measured 2026-09-15, same Windows disk-cleanup session as
`warn-cross-drive-toolchain-move.py`. A cleanup choice was offered with an
option labelled **"Clear its caches only"**, whose description bundled a Temp
directory, an npm cache, browser HTTP caches, downloaded ollama models -- and a
WSL2 distribution's ~26 GB of storage, the whole set described as "regenerable
bulk".

A WSL2 `ext4.vhdx` is a filesystem, not a cache. It holds whatever home
directory, git repos, dotfiles and uncommitted work that Linux install
accumulated. The other four genuinely rebuild on demand; that one destroys
data that may exist nowhere else.

The user approved the option. The mischaracterization had therefore already
done its work by the time it was noticed -- the approval was obtained under a
word that means "reversible", for an action that was not.

THE RULE THIS MECHANIZES
------------------------
**The label is the part that carries consent.** A description can list the
item honestly and still yield an uninformed approval, because the label is what
the reader weighs the option by. So reversibility is the axis that must not be
blurred: items of different blast radius belong in different options, however
similar their size or location makes them look. Partition a deletion choice by
BLAST RADIUS -- regenerable / re-downloadable / irreplaceable -- never by
location or size. "Cache", "temp" and "regenerable" are load-bearing words, and
every item under one of them must independently earn it.

This composes with, and does not duplicate,
`shared/workflow/avoid-false-dichotomies.md`, which governs whether the options
are mutually exclusive. This one governs what each option's label claims about
the option's own contents.

WHY THIS IS A WORD-LIST GUARD, AND WHAT THAT COSTS
--------------------------------------------------
Stated plainly because it is the honest weakness. `warn-status-read-after-pipe.py`
anchors on STRUCTURE precisely because vocabulary matchers fire on prose. Here
there is no structure to anchor on: the defect is semantic, and lives entirely
in the words chosen. So this is a vocabulary matcher, it will go stale as
phrasing drifts, and it cannot see a mislabelling that avoids every listed word.

Two things make that acceptable rather than disqualifying:

  * the surface is an `AskUserQuestion` payload, not free prose -- a short,
    deliberately-written label, not a paragraph;
  * both word lists are chosen so each entry INDEPENDENTLY carries its meaning.
    Every REVERSIBLE entry means "this rebuilds itself"; every IRREPLACEABLE
    entry names a live filesystem or volume -- or, in the one case that is
    not storage, uncommitted work -- rather than a thing that re-downloads.
    Adversarial review of a331d675 found four entries that failed that test
    and they were removed rather than defended; the comment beside the regex
    names each and why it went.

POLARITY
--------
Naming an item is not destroying it, and the well-formed option this hook
exists to PRODUCE is the one that says so: "npm and pip caches. Your WSL2
ext4.vhdx and home directory are untouched." So each sentence of the
description is checked for a preservation or recreation marker first, and a
sentence carrying one supplies no hit. A guarded hit is skipped rather than
ending the search, so an option that reassures about one item and destroys
another still fires on the second.

THE FALSE POSITIVE THAT WOULD SINK IT
-------------------------------------
"Clear the Docker build cache" is correct, common, and exactly right. A guard
that fired on the word `docker` would be switched off within a day, which is
README's "a hook that misfires is worse than a missing one" in its sharpest
form. So `docker`, `container`, `image`, `wsl` and `vm` are NOT triggers on
their own. The irreplaceable list is keyed on VM/container **disk images** by
file extension, on named **volumes**, and on explicit
filesystem wording -- the things that hold state nothing can re-fetch.
`uncommitted` is the one entry that is not storage: it describes WORK rather
than a place, and it earns its slot on the same test, since uncommitted work
exists nowhere else. Stated explicitly because a maintainer applying the
storage-shaped reading of this paragraph would otherwise strike it.

Likewise `npm cache`, `pip cache`, `browser cache`, `Temp`, `.gradle caches`
and `model downloads` are all silent: each re-downloads, and none matches the
irreplaceable list.

It warns and never blocks: no `permissionDecision` key is emitted at all, so an
absent decision defers to the normal permission flow. A false positive costs
one line of context on a question that has not been asked yet -- the cheapest
possible moment to be wrong, and the only moment at which re-splitting the
options is still free.

Fails OPEN and SILENT on any parse trouble.
"""
import json
import os
import re
import sys

# Words that promise the reader the action rebuilds itself. Each entry means
# that on its own; none of them is merely a location.
REVERSIBLE = re.compile(
    r"""\b(?:
        caches? | cached | cacheing | caching
      | temp | temporary | tempfiles?
      | scratch
      | regenerable | regenerate[ds]? | rebuildable
      | re-?downloadable | re-?fetchable
      | disposable | throwaway | ephemeral
      | junk | cruft
    )\b
  | \bsafe(?:ly)?\s+to\s+(?:delete|remove|clear|purge|wipe)\b
  | \bsafely\s+(?:delete|remove|clear|purge|wipe)\w*\b
  | \bnothing\s+(?:is\s+)?lost\b""",
    re.I | re.X,
)

# Storage that holds state nothing can re-fetch.
#
# Keyed on DISK IMAGE extensions and named volumes -- never
# on `docker`, `container`, `image`, `wsl` or `vm` alone, because "clear the
# Docker build cache" is a correct sentence and firing on it is what gets a
# guard ignored.
IRREPLACEABLE = re.compile(
    r"""\.(?:vhdx?|avhdx|vmdk|vdi|qcow2|qed)\b
  | \bext[234]\b
  | \bdocker\s+volumes?\b | \bnamed\s+volumes?\b | \bvolume\s+data\b
  | \bpgdata\b
  | \bhome\s+director(?:y|ies)\b
  | \buncommitted\b
  | \bwsl\d?\s+(?:distro|distribution|install(?:ation)?|filesystem|file\s?system)\b
  | \b(?:distro|distribution)'?s?\s+(?:storage|filesystem|file\s?system|disk)\b
  | \bvirtual\s+(?:disk|machine)\s+(?:image|file)s?\b
    """,
    re.I | re.X,
)


# Entries removed after adversarial review of a331d675, each because it failed
# the list's own admission test -- it did not INDEPENDENTLY mean irreplaceable:
#
#   overlay2                 `docker builder prune` genuinely reclaims overlay2
#                            layers, so "frees dangling overlay2 layers" is a
#                            correct sentence in a correct cache option (FP-5).
#   btrfs / zfs / xfs        a bare filesystem name appears in cache contexts
#                            ("the zfs ARC cache stats dump") (FP-6).
#   data directory / datadir a fixture's recreated data directory is
#                            disposable; `pgdata` is specific enough to keep.
#   .hdd                     a Parallels image, but too close to ordinary words
#                            to be worth the risk.

# A sentence that PRESERVES or RECREATES the thing it names is not a sentence
# putting it at risk. Without this the well-formed option the hook exists to
# PRODUCE was the one that warned: "npm and pip caches. Your WSL2 ext4.vhdx and
# home directory are untouched." fired on `ext4` (finding FP-4). Punishing the
# honest disclosure is the worst available misfire, so polarity is checked per
# sentence.
#
# The entries are held to the same admission test as IRREPLACEABLE: each must
# INDEPENDENTLY promise that the named thing survives. Round-2 review applied
# it and `remains`/`remaining` and `excluded` failed -- "Deletes the remaining
# ext4.vhdx images" and "Deletes home directory backups, excluded from the
# nightly job" are destructive sentences containing them -- so both were
# removed rather than defended (finding R-10).
PRESERVED = re.compile(
    r"""\b(?:
        untouched | unaffected | unchanged | intact | spared
      | preserve[sd]? | preserving | retain(?:s|ed|ing)? | kept | keeps
      | recreated | re-?created | regenerated | rebuilt | restored
      | survives? | survived
    )\b
  | \bnot\s+(?:be\s+)?(?:affected|touched|removed|deleted|cleared|wiped)\b
  | \bnever\s+(?:affected|touched|removed|deleted)\b
  | \bno\s+\w+(?:\s+\w+)?\s+(?:is|are|will\s+be)\s+
        (?:affected|touched|removed|deleted|lost)\b
  | \bleft\s+alone\b""",
    re.I | re.X,
)

# Sentence-ish boundaries. A description is one or two sentences, so this only
# has to separate a risk clause from a reassurance clause.
# The lookahead is not cosmetic: a bare `[.;]` split `ext4.vhdx` and
# `scratch.vmdk` down the middle, which hid the extension from
# IRREPLACEABLE and stranded a reassurance in a different fragment from
# the item it reassures about. A sentence break is a period followed by
# space or end of string; a period inside a filename is not one.
SENTENCE = re.compile(r"(?:[.;!?](?=\s|$)|\n)+")

# Verbs that put the thing named after them at risk. A preservation marker
# suppresses a hit only when NO destructive verb precedes the item in the same
# sentence -- without that, one reassuring clause disarmed everything beside
# it: "Purges the ext4.vhdx, leaving Windows files unaffected" and "Deletes the
# ext4.vhdx, and the npm cache is preserved" both went silent (finding R-9).
# The comma form is the natural English, and splitting harder on commas is not
# the fix: "Your WSL2 ext4.vhdx and home directory are untouched" would then
# lose its own reassurance.
DESTRUCTIVE = re.compile(
    r"\b(?:delete[sd]?|deleting|remove[sd]?|removing|purge[sd]?|purging"
    r"|wipe[sd]?|wiping|clear[sd]?|clearing|erase[sd]?|erasing"
    r"|destroy(?:s|ed)?|drop(?:s|ped)?|prune[sd]?|pruning|blow(?:s|n)?\s+away"
    r"|free[sd]?|freeing|reclaim(?:s|ed)?|nuke[sd]?)\b",
    re.I,
)

def _strings(node, keys, out):
    """Collect strings stored under any of `keys`, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and key.lower() in keys:
                out.append(value)
            else:
                _strings(value, keys, out)
    elif isinstance(node, list):
        for item in node:
            _strings(item, keys, out)


def options(tool_input):
    """[(label, body)] for every option in an AskUserQuestion payload.

    `body` is the label plus its description, because the irreplaceable item
    may be named in either -- in the measured incident it was in the
    description while the label carried the reversible word. The label alone is
    what is tested for the reversible word, since the label is what carries
    consent.

    Walks the structure rather than assuming `questions[].options[]`, so a
    schema change costs a missed detection rather than a crash.
    """
    found = []
    if not isinstance(tool_input, dict):
        return found

    def walk(node):
        if isinstance(node, dict):
            label = node.get("label")
            if isinstance(label, str) and label.strip():
                parts = []
                _strings(node, {"description", "detail", "details", "body",
                                "explanation", "summary"}, parts)
                # Joined with a FULL STOP, not a space: the label is its own
                # sentence. Run together, a label like "Remove temp files"
                # put a destructive verb in front of every item in the first
                # description sentence, which cancelled the recreation
                # exemption for "...scratch.vmdk, recreated by the packer
                # build" (round-2 review of b1694279).
                found.append((label, ". ".join([label] + parts)))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(tool_input)
    return found


def _at_risk(body):
    """The first irreplaceable item named in a sentence that does NOT preserve
    or recreate it, or None.

    A guarded hit is skipped rather than ending the search, so an option that
    reassures about one item and quietly destroys another still fires on the
    second.
    """
    for sentence in SENTENCE.split(body):
        hit = IRREPLACEABLE.search(sentence)
        if not hit:
            continue
        # A reassurance disarms the item only when nothing destructive is said
        # about it first. "Your ext4.vhdx is untouched" reassures; "Purges the
        # ext4.vhdx, leaving Windows files unaffected" does not, however
        # reassuring its second clause sounds.
        if (PRESERVED.search(sentence)
                and not DESTRUCTIVE.search(sentence[:hit.start()])):
            continue
        return hit.group(0)
    return None


def find_mislabelled(tool_input):
    """[(label, reversible_word, irreplaceable_item)] for each bad option."""
    hits = []
    seen = set()
    for label, body in options(tool_input):
        word = REVERSIBLE.search(label)
        if not word:
            continue
        item = _at_risk(body)
        if not item:
            continue
        key = (label, word.group(0), item)
        if key in seen:
            continue
        seen.add(key)
        hits.append(key)
    return hits


NOTE = (
    "An option's label promises reversibility for something that is not "
    "reversible.\n"
    "{items}\n"
    "The label is the part that carries consent. A reader weighs the option by "
    "its label, so bundling an irreplaceable item under a word that means "
    '"rebuilds itself" produces an approval that is uninformed even when the '
    "description lists the item honestly -- and the approval cannot be taken "
    "back once the deletion runs.\n"
    "A VM or WSL disk image is a filesystem, not a cache: it holds whatever "
    "home directory, repos, dotfiles and uncommitted work that install "
    "accumulated. A package cache, a Temp directory, a browser cache and a "
    "re-downloadable model all genuinely rebuild; that one does not.\n"
    "Partition the options by BLAST RADIUS -- regenerable / re-downloadable / "
    "irreplaceable -- not by size or location, and give the irreplaceable item "
    "its own option with its own honest label. Every item under a "
    '"cache"/"temp"/"regenerable" label must independently earn that word.\n'
    "If the named item really is disposable here, say why and carry on; this "
    "only adds context and blocks nothing."
)


def _read_payload():
    args = sys.argv[1:]
    if "--dry-run" in args or "--simulate" in args:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            try:
                return json.loads(raw)
            except Exception:
                return {}
    try:
        payload = json.load(sys.stdin)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        print(f"warn-irreplaceable-under-cache-label: unreadable hook input "
              f"({exc})", file=sys.stderr)
        return {}


def main():
    payload = _read_payload()
    if not isinstance(payload, dict) or not payload:
        return 0
    if payload.get("tool_name") != "AskUserQuestion":
        return 0

    try:
        hits = find_mislabelled(payload.get("tool_input"))
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-irreplaceable-under-cache-label: could not evaluate "
              f"({exc})", file=sys.stderr)
        return 0
    if not hits:
        return 0

    items = "\n".join(
        f'- option "{label}" says "{word}" but names `{item}`'
        for label, word, item in hits)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(items=items),
        },
    }
    # Gated per README's Antigravity double-warn rule.
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        first = hits[0]
        out["systemMessage"] = (
            f'Option "{first[0]}" labels `{first[2]}` as "{first[1]}". That is '
            "a filesystem, not a cache -- split it into its own option so the "
            "approval is informed."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
