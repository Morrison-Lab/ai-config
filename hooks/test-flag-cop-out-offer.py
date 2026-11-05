"""Test the flag-cop-out-offer guard.

Two design choices carry the value, and each has its own negative case.

TAIL-ANCHORED: the failure is a recap that CLOSES on an offer. An offer
mid-message followed by real substance is usually a question posed in passing,
so it must not warn.

NOT whole-message: unlike no-placeholder-reply, the offer is one sentence at
the end of a long reply, so the matcher searches the tail rather than matching
the entire message.

The corpus-quoting case matters here too but is weaker by construction: prose
ABOUT the rule usually discusses the phrases mid-document, which the tail
anchor already excludes.

Run: python3 hooks/test-flag-cop-out-offer.py hooks/flag-cop-out-offer.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def narrate_and_reply(narration, text):
    """One turn speaking on both channels at once.

    Only `text` reaches the user; `narration` is a plain assistant text block,
    which a project-thread harness does not deliver.
    """
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": narration},
        {"type": "tool_use", "name": "mcp__hearthbot__reply",
         "input": {"text": text}}]}}


def reply(text):
    """A project-thread reply: the user-visible text lives in a TOOL payload.

    The harness delivers a thread session's prose this way and no other way,
    so a transcript from one carries no assistant text block at all.
    """
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__hearthbot__reply",
         "input": {"text": text}}]}}


def issue_filed():
    """An issue_write create call, as the GitHub MCP server names it."""
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__github__issue_write",
         "input": {"method": "create", "title": "nits"}}]}}


def bash_call(command):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}


USER_TURN = {"type": "user", "message": {"content": "next request"}}

LONG = ("Setup job 143472 completed in 19m32s and the array is running. " * 12)

CASES = [
    # The reported incidents, verbatim.
    ([TOOL, say("The results are ready.\n\nSay the word and I'll push and "
                "open it now.")], True,
     "'say the word' closing a recap warns (the reported case)"),
    ([TOOL, say("I'll keep digging at the row-count mismatch unless you'd "
                "rather I spend the remaining hours on meeting material.")],
     True, "'unless you'd rather' warns (the 2.5-hour stall)"),
    ([TOOL, say("Array is queued.\n\nWant me to kick off the re-run now?")],
     True, "'want me to' warns"),
    ([TOOL, say("Both files are safe.\n\nLet me know if you want the "
                "coefficients pulled out.")], True,
     "'let me know if' warns"),
    ([TOOL, say("Ready to push when you are.")], True,
     "'ready to X when you are' warns"),
    # Morrison-Lab/mds#501, 2026-10-27: two recaps closed on "I can ... if
    # you want" for an ai-config edit that `add_repo` and the
    # default-to-action grant already covered. The pattern took only
    # "if you'd like" / "if you would prefer", so neither warned.
    ([TOOL, say("The PR is waiting on review and CI. The ai-config rule is "
                "still unrecorded; I can add it if you want.")], True,
     "'I can X if you want' warns (mds#501)"),
    ([TOOL, say("That belongs in ai-config, which isn't attached here. I can "
                "attach it and open a PR for the rule if you want.\n\nThe "
                "session isn't done until CI comes back green.")], True,
     "'I can X if you want' followed by one status line still warns"),
    ([TOOL, say("I can see the job if you wanted to check it yourself, "
                "but it already passed.")], False,
     "'if you wanted' in a past-tense aside stays silent"),

    # ai-config#3694: `flag-session-boundaries` appends a stopping-point
    # declaration to every reply, and for a non-clean stop it puts the pending
    # work AFTER that declaration. In a busy session the block outruns
    # TAIL_CHARS on its own, so obeying that rule pushed the actual closing
    # move out of this hook's window and made it blind. Measured on
    # ucdavis/bcs, 2026-09-15.
    ([TOOL, say("Built and pushed the figure.\n\nOFFER -- the strongest "
                "version is a chart. Say the word and I will add it to "
                "#1016.\n\n**Stopping Point**: Not a clean stopping point / "
                "work remains queued: " + LONG)], True,
     "an offer warns even when a long stopping-point block follows it"),
    ([TOOL, say("Merged #1019 and filed #1020.\n\n**Stopping Point**: Not a "
                "clean stopping point / work remains queued: " + LONG)], False,
     "a stopping-point block with no offer before it stays silent"),

    # The first patch for #3694 cut everything from the marker onward, which
    # made the pending-work section -- where flag-session-boundaries puts the
    # remaining work, and calls it the most visible element of the reply -- a
    # permanently safe place to park an offer. A worse blind spot than the one
    # being closed. Caught in review on ai-config#3695.
    ([TOOL, say("Merged and pushed.\n\n**Stopping Point**: Not a clean "
                "stopping point / work remains queued: the array is mid-run. "
                "Want me to push the fix now?")], True,
     "an offer at the END of the pending-work block still warns"),

    # The second patch handed back the post-marker region WHOLE, with no tail
    # slice, which let an aside buried mid-block fire with paragraphs of
    # status after it -- reintroducing inside the pending-work section the
    # exact false positive TAIL_CHARS exists to prevent. Caught in review on
    # ai-config#3695; both windows are tails now.
    ([TOOL, say("Merged and pushed.\n\n**Stopping Point**: Not a clean "
                "stopping point / work remains queued: would you like me to "
                "try that? " + LONG)], False,
     "an aside mid-pending-block, with status after it, stays silent"),

    # Negatives that decide the anchoring.
    ([TOOL, say("Want me to do this? No -- it was already authorized, so I "
                "did it. " + LONG)], False,
     "an offer phrase EARLY in a long reply does not warn"),
    ([TOOL, say("Pushed as a5591a67 and opened #679. I did not commit the "
                "regenerated artifact, which is a large binary.")], False,
     "a past-tense report does not warn"),
    ([TOOL, say("This needs your decision because it is destructive: "
                "should I force-push over the other session's commit?")],
     False, "a plain question with no offer wording does not warn"),
    ([TOOL], False, "a turn with no assistant prose does not warn"),
    ([TOOL, say("Nothing changed since the last poll.")], False,
     "a no-change tick does not warn"),

    # The reply-tool payload. In a project-thread session this is the ONLY
    # channel the user reads, so a reader that walks assistant text blocks
    # alone sees an empty turn and the guard never fires. Measured
    # 2026-09-19: a closing offer whose phrase is in OFFERS, well inside
    # TAIL_CHARS, went unflagged for exactly this reason.
    ([TOOL, reply("The request is withdrawn and the PR is unblocked. "
                  "Say the word and I'll merge it.")], True,
     "an offer inside a reply-tool payload warns"),
    ([TOOL, reply("Withdrew the review request; the scorer exited 0 on "
                  "1755bc6.")], False,
     "a reply-tool payload with no offer stays silent"),

    # The other direction, and the one a both-channels reader gets wrong.
    # Narration is not delivered in this harness, so an offer sitting there
    # is a sentence nobody read -- warning about it quotes the user back
    # something they were never shown.
    ([TOOL, narrate_and_reply(
        "Internal note: the scorer exited 0, so this qualifies. "
        "Want me to go ahead and merge it now?",
        "Merged and pushed as f6a21ad2.")], False,
     "an offer in undelivered narration does not warn when a reply spoke"),
    ([TOOL, narrate_and_reply(
        "Internal note: the merge landed cleanly.",
        "Done. Say the word and I'll open the follow-up PR.")], True,
     "an offer in the reply wins over clean narration"),

    # ai-config#4962: optional work left as a closing remark, with no issue
    # filed or linked in the same turn.
    ([TOOL, say("Merged the fix.\n\nOptional cleanup: the two review nits are cosmetic "
                "and stay as they are.")], True,
     "'optional' with no issue filed or linked warns (ai-config#4962)"),
    ([TOOL, say("Merged the fix.\n\nOptional cleanup: the two review nits are filed as "
                "https://github.com/Morrison-Lab/ai-config/issues/4970.")], False,
     "'optional' with an issue link in the reply stays silent"),
    ([TOOL, issue_filed(), say("Merged the fix.\n\nOptional cleanup: the two review nits "
                               "are cosmetic and stay as they are.")], False,
     "'optional' after an issue_write create in the same turn stays silent"),
    ([issue_filed(), USER_TURN, TOOL,
      say("Merged the fix.\n\nOptional cleanup: the two review nits are cosmetic.")], True,
     "an issue filed in an EARLIER turn does not cover this one"),
    ([TOOL, bash_call("gh issue create --title nits --body-file b.md"),
      say("Merged the fix.\n\nOptional cleanup: the two review nits are cosmetic.")], False,
     "'optional' after gh issue create in the same turn stays silent"),

    ([TOOL, say("The parameter is optional and defaults to 10.")], False,
     "'optional' describing a parameter stays silent"),
    ([TOOL, say("Merged the fix. Filed #4970 for the two nits.")], False,
     "a 'Filed #N' close stays silent"),
    ([TOOL, say("**OFFER** -- I can also add the chart.")], False,
     "a FLAG/OFFER-marked message is left to flag-idea-without-issue"),
    ([TOOL, bash_call("gh issue comment 12 --body-file b.md"),
      say("Merged the fix. I can also fix the nits.")], False,
     "an issue comment discharges the optional check"),

    ([TOOL, say("You could also add a grouping variable with group_by().")], False,
     "'could also add' in instructional prose stays silent"),
    ([TOOL, say("The model fits well. I can also do a residual plot.")], False,
     "a plain 'I can also do' stays silent"),
    ([TOOL, say("**OFFER** -- add a dashboard later.\n\nMerged the fix.\n\n"
                "Optional cleanup: the two review nits stay as they are.")], True,
     "a marker in an unrelated paragraph does not exempt an unfiled optional"),

    ([TOOL, say("Merged the fix as a follow-up to the earlier PR. All done.")], False,
     "a completed 'as a follow-up' stays silent"),
    ([TOOL, say("No nits remain after this pass; everything is addressed.")], False,
     "'no nits remain' stays silent"),
    ([TOOL, say("All review nits were fixed; none are left.")], False,
     "'nits were fixed; none are left' stays silent"),
    ([TOOL, say("There are no new nits left after this pass.")], False,
     "'no new nits left' stays silent"),
    ([TOOL, say("No further nits are left; everything is addressed.")], False,
     "'no further nits are left' stays silent"),
    ([TOOL, say("There aren't any nits left.")], False,
     "'aren't any nits left' stays silent"),
    ([TOOL, say("Merged. Outstanding nits remain in the file.")], True,
     "'outstanding nits remain' with no issue warns"),
    ([TOOL, say("Merged. A couple of nits remain unaddressed.")], True,
     "'a couple of nits remain' with no issue warns"),
    ([TOOL, say("Merged. There's one nit left to fix.")], True,
     "'one nit left' with no issue warns"),
    ([TOOL, say("Merged. All nits were fixed, so none remain.")], False,
     "'all nits were fixed' stays silent"),
    ([TOOL, say("Status: all fixed; two nits remain in the output file.")], True,
     "a semicolon-joined 'all fixed; two nits remain' warns"),
    ([TOOL, say("No nits remain after this pass? Actually yes, two nits remain "
                "in the config.")], True,
     "a corrected question-then-answer 'two nits remain' warns"),
    ([TOOL, say("There are no nits left in module A, but two nits remain in "
                "module B.")], True,
     "a comma-joined contrast 'no nits in A, but two nits remain in B' warns"),
    ([TOOL, say("No nits remain, however two nits remain in the config file.")], True,
     "'No nits remain, however two nits remain' warns"),
    ([TOOL, say("No one complained, two nits remain though.")], True,
     "an unrelated 'No' before a comma does not silence a postposed-though report"),
    ([TOOL, say("Nothing broke in testing, two nits remain, however.")], True,
     "an unrelated 'Nothing' before a comma does not silence 'two nits remain'"),
    ([TOOL, say("No nits remain in module A and two nits remain in module B.")], True,
     "an 'and'-joined 'no nits in A and two nits remain in B' warns"),
    ([TOOL, say("All style nits were fixed in file A and two nits remain in file B.")],
     True, "an 'and'-joined 'all fixed in A and two nits remain in B' warns"),
    ([TOOL, say("Merged. Two nits or issues remain in the figure code.")], True,
     "'two nits or issues remain' (nouns joined by or) warns"),
    ([TOOL, say("Merged. The style nits and formatting issues remain unfiled.")], True,
     "'nits and issues remain unfiled' warns"),
    ([TOOL, say("Merged the fix. No nits or issues remain.")], False,
     "'No nits or issues remain' stays silent"),
    ([TOOL, say("No nits nor issues remain.")], False,
     "'No nits nor issues remain' stays silent"),
    ([TOOL, say("There are no nits or follow-ups left.")], False,
     "'no nits or follow-ups left' stays silent"),
    ([TOOL, say("None of the nits or follow-ups remain.")], False,
     "'None of the nits or follow-ups remain' stays silent"),
    ([TOOL, say("Zero nits or follow-ups remain unfiled.")], False,
     "'Zero nits or follow-ups remain unfiled' stays silent"),
    ([TOOL, say("Merged. I will handle the cache change as a follow-up.")], True,
     "a future 'as a follow-up' with no issue warns"),
    ([TOOL, say("Merged. Two nits remain in the figure code.")], True,
     "'two nits remain' with no issue warns"),

    # Antigravity transcript format: GENERIC tool result vs PLANNER_RESPONSE (ai-config#4635)
    ([{"source": "MODEL", "type": "GENERIC", "content": "Say the word and I'll push."}], False,
     "Antigravity GENERIC tool result containing offer is not assistant prose"),
    ([{"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Say the word and I'll push."}], True,
     "Antigravity PLANNER_RESPONSE containing offer warns"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        r = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        # Must SURFACE the warning to the agent. Asserting on stderr alone
        # cannot tell a surfaced warning from discarded output, and a bare
        # systemMessage reaches only the user, so the positive signal is a
        # block whose reason carries the warning (ai-config#4796).
        if not r.stdout.strip():
            return False
        payload = json.loads(r.stdout)
        assert payload.get("decision") == "block" and payload.get("reason"), (
            "Stop hook must block with its warning as the reason, the only part "
            "the agent reads (ai-config#4796)")
        assert payload.get("systemMessage") == payload["reason"], "user copy must match"
        return "offer" in payload["systemMessage"].lower()
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # Once-per-message sentinel: a second run over the same message is silent.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("Say the word and I'll push.")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    first = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True, env=env).stderr
    second = subprocess.run([sys.executable, HOOK], input=payload,
                            capture_output=True, text=True, env=env).stderr
    os.unlink(path)
    if "flag-cop-out-offer" in first and "flag-cop-out-offer" not in second:
        print("PASS: warns once per distinct message"); passes += 1
    else:
        print("FAIL: sentinel did not suppress the repeat"); failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
