"""Test warn-permission-prefix-mismatch (warn-only PreToolUse guard).

Run:  python3 hooks/test-warn-permission-prefix-mismatch.py \
          hooks/warn-permission-prefix-mismatch.py
Each clause of the hook is mutated and the cases that must flip are checked.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1])
with open(HOOK, encoding="utf-8") as fh:
    SOURCE = fh.read()

TMP = tempfile.mkdtemp()
RULES = os.path.join(TMP, "settings.json")
with open(RULES, "w", encoding="utf-8") as fh:
    json.dump({"permissions": {"allow": [
        "Bash(ALLOW_UNREVIEWED_PUSH=1 git push:*)", "Bash(git push:*)"]}}, fh)
EMPTY = os.path.join(TMP, "none.json")

P = "ALLOW_UNREVIEWED_PUSH=1 "
WARN = [
    ("W1", P + "git -C /r push -u origin b", RULES, "the incident"),
    ("W2", P + "git -c core.x=1 push", RULES, "-c k=v"),
    ("W3", P + "git --git-dir=/r/.git push", RULES, "--git-dir=value"),
    ("W4", P + "git --no-pager -C /r push", RULES, "two global options"),
    ("W6", P + "git -C /r push && echo done", RULES, "chained after"),
]
SILENT = [
    ("S1", P + "git push -u origin b", RULES, "already the rule form"),
    ("S2", "git -C /r push", RULES, "no env assignment"),
    ("S3", P + "git -C /r push", EMPTY, "no rule to match"),
    ("S4", P + "git -C /r status", RULES, "stripped form matches no rule"),
    ("S5", P + "git -C /r push", os.path.join(TMP, "missing.json"),
     "unreadable settings fail open"),
    ("S6", "echo hi && " + P + "git -C /r push", RULES,
     "git is not the first command"),
    ("S8", "FOO=1 " + P + "git -C /r push", RULES,
     "extra leading assignment: rule could not match even without -C"),
    ("S7", P + "git --weird-opt push", RULES, "unknown option, no guess"),
]
CASES = {c[0]: c for c in WARN + SILENT}
EXPECTED = {c[0]: "WARN" for c in WARN} | {c[0]: "silent" for c in SILENT}


def verdict(hook, case):
    _, cmd, settings, _ = case
    proc = subprocess.run(
        [sys.executable, hook], text=True, capture_output=True,
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        env={**os.environ, "WARN_PREFIX_SETTINGS_FILES": settings})
    if proc.returncode != 0:
        sys.exit(f"FATAL: exit {proc.returncode}: {proc.stderr}")
    if not proc.stdout.strip():
        return "silent"
    hso = json.loads(proc.stdout).get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit("FATAL: warn-only hook emitted permissionDecision")
    return "WARN" if hso.get("additionalContext") else "silent"


# default (non-override) search path: user settings under HOME, project
# settings under cwd
HOME = os.path.join(TMP, "home")
PROJ = os.path.join(TMP, "proj")
os.makedirs(os.path.join(HOME, ".claude"))
os.makedirs(os.path.join(PROJ, ".claude"))
with open(os.path.join(HOME, ".claude", "settings.local.json"), "w") as fh:
    json.dump({"permissions": {"allow": ["Bash(FOO=1 git push:*)"]}}, fh)
with open(os.path.join(PROJ, ".claude", "settings.team.json"), "w") as fh:
    json.dump({"permissions": {"allow": ["Bash(BAR=1 git push:*)"]}}, fh)


def default_verdict(hook, cmd):
    env = {k: v for k, v in os.environ.items()
           if k != "WARN_PREFIX_SETTINGS_FILES"}
    env["HOME"] = HOME
    proc = subprocess.run(
        [sys.executable, hook], text=True, capture_output=True, cwd=PROJ,
        env=env, input=json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": cmd}}))
    return "WARN" if proc.stdout.strip() else "silent"


DEFAULT = [("D1", "FOO=1 git -C /r push", "WARN", "user settings.local.json"),
           ("D2", "BAR=1 git -C /r push", "WARN", "project settings*.json"),
           ("D3", "BAZ=1 git -C /r push", "silent", "no rule anywhere")]

wrong = 0
for cid, case in CASES.items():
    got = verdict(HOOK, case)
    wrong += got != EXPECTED[cid]
    print(f"  {got:<6} {cid:<3} {case[3]}")
for payload in ({"tool_name": "Read", "tool_input": {}}, {}):
    proc = subprocess.run([sys.executable, HOOK], text=True,
                          capture_output=True, input=json.dumps(payload))
    wrong += bool(proc.stdout.strip()) or proc.returncode != 0
for cid, cmd, exp, desc in DEFAULT:
    got = default_verdict(HOOK, cmd)
    wrong += got != exp
    print(f"  {got:<6} {cid:<3} default search path: {desc}")
print(f"{len(CASES) - wrong}/{len(CASES)} correct (plus default-path cases)")

MUTATIONS = {
    "M1_requires_assignment": (
        [("    if i == 0 or i >= len(toks)", "    if i >= len(toks)")], {"S2"}),
    # the next two guard the same case (no global option present); either
    # alone is masked by the other, so they are reverted together
    "M2_3_require_option_and_not_already_matching": (
        [("    if j == start or j >= len(toks):", "    if j >= len(toks):"),
         ("    if any(matches(p, full) for p, _ in rules):\n        return None\n",
          "")], {"S1"}),
    "M4_stripped_must_match_rule": (
        [("        if matches(prefix, stripped):",
          "        if True:")], {"S4"}),
    "M5_unknown_option_bails": (
        [("            return None  # unknown option: do not guess",
          "            j += 1")], {"S7"}),
    "M6_user_settings_files": (
        [('os.path.join(home, "settings.local.json")]', '"/nonexistent"]')],
        {"D1"}),
    "M7_project_settings_glob": (
        [('"settings*.json"))', '"nonexistent.json"))')], {"D2"}),
}
mw = 0
for name, (edits, flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, rep in edits:
        if mutated.count(find) != 1:
            sys.exit(f"FATAL: anchor for {name} not found exactly once")
        mutated = mutated.replace(find, rep)
    fd, path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(mutated)
    try:
        flipped = {cid for cid, c in CASES.items()
                   if verdict(path, c) != EXPECTED[cid]}
        flipped |= {cid for cid, cmd, exp, _ in DEFAULT
                    if default_verdict(path, cmd) != exp}
    finally:
        os.unlink(path)
    ok = flipped >= flips and bool(flipped)
    mw += not ok
    print(f"  {'ok  ' if ok else 'WRONG'} {name}: flipped {sorted(flipped)}, "
          f"needed {sorted(flips)}")
sys.exit(1 if wrong or mw else 0)
