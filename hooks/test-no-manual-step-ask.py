#!/usr/bin/env python3
"""Tests for hooks/no-manual-step-ask.py (ai-config#4698).

Run: python3 hooks/test-no-manual-step-ask.py [hooks/no-manual-step-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-manual-step-ask.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny)
CASES = [
    ("type go in RC session", POST, "Please type `go` in the Remote Control session to start.", True),
    ("say go to the session", POST, "Say go in the session on cf463-02 and it will run.", True),
    ("RC then type go", POST, "The RC session is waiting; type \"go\" there.", True),
    ("click merge button", POST, "Click the green Merge button on the PR.", True),
    ("press the merge button", POST, "Press the merge button when CI is green.", True),
    ("merge it yourself", POST, "You can merge them yourself once green.", True),
    ("plain mwc ask", POST, "Both are ready. Type `mwc` to merge them.", False),
    ("fresh session sentence", POST, "I started a fresh Remote Control session with the brief as its opening task.", False),
    ("go as an ordinary word", POST, "Let's go ahead and type the results into the table.", False),
    ("reply then go ahead, session later", POST, "Reply if you disagree; otherwise we can go ahead and the session will start.", False),
    ("say we go, RC mentioned", POST, "You said we should go with the RC plan, so I started a session.", False),
    ("use the merge queue", POST, "Use the merge queue; the button is disabled by policy.", False),
    ("append to settings", POST, "Append this string to the autoMode.allow list in ~/.claude/settings.json.", True),
    ("paste into file", POST, "Please paste this into the file and save it.", True),
    ("you can add to config", POST, "You can add the entry to your config.json by hand.", True),
    ("script command form", POST, "Run `python3 ~/Documents/claude-fetch/add-automode-allow.py`; it adds the entry to settings.json and keeps a backup.", True),
    ("script handed over beside a could-add clause", POST, "You could add an entry to the allowlist in settings.json, but run `python3 ~/scripts/add-entry.py` instead; it does it.", True),
    ("ssh line to type (ai-config#4842)", POST, "Please run `ssh morri313@cf463-01.cs.wwu.edu 'bash -s' < restart-runners.sh` in your terminal.", True),
    ("type this in your Mac terminal", POST, "Type this in your Mac terminal: ssh cf463-02 hostname", True),
    ("run bash script line", POST, "Then run bash /Users/ezra/Documents/GitHub/install-tools.sh to finish.", True),
    ("command ask about a token is exempt", POST, "Please run `gh auth login` in your terminal and paste the token when asked.", False),
    ("asking permission is fine", POST, "May I run the restart script on cf463-01 for you? Tap yes on the card.", False),
    ("past tense run is fine", POST, "I ran bash restart-runners.sh and all six runners are up.", False),
    ("noun use of run is fine", POST, "The run of git history shows no deletions.", False),
    ("copy as a code instruction", POST, "Copy the array into a new variable before mutating it, to avoid aliasing in the config.", False),
    ("bare add to settings.json", POST, "Add the key to settings.json.", True),
    ("bare put into config file", POST, "Put this entry into your config file.", True),
    ("bare add to your settings", POST, "Add the entry to your settings.", True),
    ("bare put into your config", POST, "Put this entry into your config.", True),
    ("add to your config object", POST, "Add the handler to your config object in the fixture.", False),
    ("ask beside an unrelated script", POST, "Please add the entry to settings.json. Separately, I already ran bash deploy.sh for the release.", True),
    ("ask before an unrelated script mention", POST, "Please paste this into ~/.claude/settings.json. I also ran python3 scripts/unrelated.py earlier.", True),
    ("ask then a run-this-script sentence", POST, "You could add the entry to settings.json by hand. Run python3 ~/scripts/add-entry.py instead.", True),
    ("script alone, no ask", POST, "Run python3 ~/scripts/add-entry.py; it adds the entry to settings.json and keeps a backup.", True),
    ("unrelated script in a following run sentence", POST, "Please add the key to settings.json. Run the deploy script now, by the way also note python3 unrelated.py exists.", True),
    ("please add to config dict", POST, "Please add the handler to the config dict.", False),
    ("you can add to settings object", POST, "You can add validation logic to the settings object.", False),
    ("paste into the config", POST, "Please paste this into the config.", True),
    ("can you paste into settings", POST, "Can you paste this into settings?", True),
    ("append to the config", POST, "Could you append this to the config?", True),
    ("polite add to your settings", POST, "You can add this directly to your settings.", True),
    ("append row to settings dataframe", POST, "Append the row to the settings dataframe before saving.", False),
    ("insert record into config table", POST, "Insert a record into the config table in the test.", False),
    ("append result to settings cache", POST, "Please append the migration result to the settings cache for testing.", False),
    ("bare add to the settings", POST, "Add the key to the settings.", True),
    ("bare put into the config", POST, "Put the value into the config.", True),
    ("ask with a past-script aside", POST, "Please add this to settings.json, same as python3 other.py did last time.", True),
    ("ask with a comma script aside", POST, "Could you add the key to settings.json, the way python3 old-script.py used to?", True),
    ("ask with a since-script aside", POST, "Please paste this into ~/.claude/settings.json since python3 check.py already confirmed the format.", True),
    ("running the script hand-over", POST, "You could add the entry to settings.json, but running python3 ~/scripts/add-entry.py does it for you.", False),
    ("run sentence with a long lead-in", POST, "Please add the key to settings.json. Run the helper script that lives in the scripts directory of this repo, specifically python3 ~/scripts/add-entry.py, to do it.", True),
    ("second ask after an exempt sentence", POST, "You could add this to settings.json, but run python3 ~/scripts/add-entry.py instead. You could add that to ~/.claude/settings.json.", True),
    ("exempt ask whose match ends at a newline", POST, "You can run python3 ~/scripts/add-entry.py or just add this to the settings\nThat is all.", True),
    ("put in settings.json", POST, "Please put this entry in settings.json.", True),
    ("e.g. does not split the sentence", POST, "You could add the entry to settings.json, e.g. by hand, but run python3 ~/scripts/add-entry.py instead.", True),
    ("envs. is not an abbreviation break", POST, "You could add the entry to settings.json for the envs. Run python3 ~/scripts/add-entry.py to do the rest.", True),
    ("ask does not bridge a question mark", POST, "Could you add the key? Run python3 ~/scripts/add-entry.py; it writes to settings.json.", True),
    ("ask does not bridge an exclamation mark", POST, "Could you add the key! Run python3 ~/scripts/add-entry.py; it writes to settings.json.", True),
    ("scripted bare add after a prior sentence", POST, "Done. Add the entry to settings.json: run python3 ~/scripts/add-entry.py", True),
    ("e.g. inside an ask", POST, "Please add the entry e.g. the key to settings.json.", True),
    ("add to config dict", POST, "Add the result to the config dict before returning it.", False),
    ("add to settings object", POST, "Add the handler to the settings object in the test fixture.", False),
    ("put into settings dataclass", POST, "Put a default value into the settings dataclass.", False),
    ("bare add line to home settings", POST, "Add the following line to ~/.claude/settings.json.", True),
    ("agent did the edit", POST, "I added the entry to the file myself and the probe passes.", False),
    ("agent will add", POST, "I'll add the rule to the file in the next commit.", False),
    ("unrelated tool","Bash", "Click the Merge button", False),
    ("no text", POST, None, False),
]


def run(tool, text):
    payload = {"tool_name": tool, "tool_input": {"text": text} if text is not None else {}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, text, deny in CASES:
        rc, out = run(tool, text)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
