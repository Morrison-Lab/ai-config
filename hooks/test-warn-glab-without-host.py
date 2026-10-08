"""Test the warn-glab-without-host guard.

Case W1 is the incident (ai-config#4387): `glab api` run from a folder that is
not a git checkout, with no host named anywhere. The silent cases are what keep
the guard from being switched off: a host named by flag, repo path, or env; a
checkout whose remote names a self-hosted GitLab; subcommands that never
resolve a host.

The working directory is part of the verdict, so each case carries a `cwd`
kind that the harness materialises: `plain` (a directory that is not a git
checkout), `selfhosted` (a checkout whose origin is a self-hosted GitLab),
`gitlabcom` (origin on gitlab.com), `github` (origin on github.com).

Run:  python3 hooks/test-warn-glab-without-host.py \\
          hooks/warn-glab-without-host.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.realpath(sys.argv[1])

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

with open(HOOK, encoding="utf-8") as handle:
    SOURCE = handle.read()

ROOT = tempfile.mkdtemp(prefix="glab-host-test-")


def make_dir(kind):
    path = os.path.join(ROOT, kind)
    os.makedirs(path, exist_ok=True)
    urls = {
        "selfhosted": "https://gitlab.example.org/group/project.git",
        "gitlabcom": "https://gitlab.com/group/project.git",
        "github": "git@github.com:owner/repo.git",
    }
    if kind in urls:
        subprocess.run(["git", "init", "-q", path], check=True)
        subprocess.run(["git", "-C", path, "remote", "add", "origin", urls[kind]],
                       check=True)
    return path


CWDS = {k: make_dir(k) for k in ("plain", "selfhosted", "gitlabcom", "github")}


def payload(command, cwd_kind, tool="Bash"):
    return {"tool_name": tool, "cwd": CWDS[cwd_kind],
            "tool_input": {"command": command}}


# (id, command, cwd kind, description)
SHOULD_WARN = [
    ("W1", "glab api projects/1/issues", "plain",
     "the incident: glab api in a non-checkout with no host"),
    ("W2", "glab api projects/1/issues", "gitlabcom",
     "a checkout whose remote is gitlab.com names no self-hosted host"),
    ("W3", "glab api user", "github",
     "a github.com checkout is no GitLab host"),
    ("W4", "glab issue list", "plain",
     "a non-api subcommand that resolves its host from cwd"),
    ("W5", "glab mr list -R group/project", "plain",
     "-R with owner/repo only carries no host"),
    ("W6", "cd /tmp && glab api user", "selfhosted",
     "a cd out of the self-hosted checkout into a non-checkout"),
    ("W7", "echo hi; glab api user | jq .", "plain",
     "glab later in a compound command"),
    ("W8", "GH_HOST=github.example.org glab api user", "plain",
     "GH_HOST is not GITLAB_HOST"),
    ("W9", "GITLAB_HOST= glab api user", "plain",
     "an EMPTY GITLAB_HOST names no host"),
    ("W10", "/opt/homebrew/bin/glab api user", "plain",
     "glab invoked by absolute path"),
    ("W11", "glab -R group/project mr list", "plain",
     "a leading -R with its value must not be read as the subcommand"),
    ("W12", "glab --repo group/project issue list", "plain",
     "a leading --repo with its value must not be read as the subcommand"),
]

SHOULD_STAY_SILENT = [
    ("S1", "glab api --hostname gitlab.example.org user", "plain",
     "--hostname given"),
    ("S2", "glab api --hostname=gitlab.example.org user", "plain",
     "--hostname=value form"),
    ("S3", "glab mr list -R gitlab.example.org/group/project", "plain",
     "-R names a host"),
    ("S4", "glab mr list --repo https://gitlab.example.org/group/project",
     "plain", "--repo with a URL"),
    ("S5", "GITLAB_HOST=gitlab.example.org glab api user", "plain",
     "GITLAB_HOST prefix"),
    ("S6", "export GITLAB_HOST=gitlab.example.org; glab api user", "plain",
     "an earlier export of GITLAB_HOST in the same command"),
    ("S7", "glab api user", "selfhosted",
     "cwd is a checkout whose origin is a self-hosted GitLab"),
    ("S8", "glab auth login", "plain",
     "auth does not resolve a project host"),
    ("S9", "glab version", "plain", "version needs no host"),
    ("S10", "git status && ls", "plain", "no glab at all"),
    ("S11", "echo glab api user", "plain",
     "glab only as an argument to echo"),
    ("S12", "gh api user", "plain", "gh is out of scope for this hook"),
    ("S13", "cd /tmp && cd " + "{selfhosted}" + " && glab api user", "plain",
     "a cd INTO the self-hosted checkout before glab"),
    ("S15", "GITLAB_HOST=gitlab.example.org; glab api user", "plain",
     "a bare GITLAB_HOST assignment statement sets the host"),
    ("S14", "glab api -R gitlab.example.org/g/p projects/1", "plain",
     "-R host before the endpoint"),
]

NON_COMMAND_PAYLOADS = [
    ({"tool_name": "Bash", "tool_input": None}, "null tool_input"),
    ({"tool_name": "Bash"}, "absent tool_input"),
    ({"tool_name": "Bash", "tool_input": "glab api user"}, "string tool_input"),
    ({"tool_name": "Bash", "tool_input": {"command": 123}}, "non-string command"),
    ({"tool_name": "Bash", "tool_input": {}}, "no command key"),
    (["Bash"], "payload is a list"),
    ({"tool_name": "Edit", "cwd": CWDS["plain"],
      "tool_input": {"command": "glab api user"}}, "a non-Bash tool"),
    ({"tool_name": "Bash", "tool_input": {"command": "glab api 'unterminated"},
      "cwd": CWDS["plain"]}, "an unparseable command fails open"),
]


def run_hook(hook_path, data, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != "GITLAB_HOST"}
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, hook_path], input=json.dumps(data),
        capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode} on {data!r}\n"
                 f"{proc.stderr.strip()}")
    return proc.stdout


def verdict(hook_path, data):
    out = run_hook(hook_path, data)
    if not out.strip():
        return "silent"
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError as exc:
        sys.exit(f"FATAL: non-JSON stdout ({exc}): {out!r}")
    hso = parsed.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        sys.exit("FATAL: hook emitted permissionDecision; warn-only guard")
    return "WARN" if hso.get("additionalContext") else "silent"


def case_payload(command, kind):
    return payload(command.replace("{selfhosted}", CWDS["selfhosted"]), kind)


wrong = 0
print("should WARN:")
for cid, command, kind, desc in SHOULD_WARN:
    got = verdict(HOOK, case_payload(command, kind))
    wrong += got != "WARN"
    print(f"  {got:<6} {cid:<4} {desc}")

print("\nshould STAY SILENT:")
for cid, command, kind, desc in SHOULD_STAY_SILENT:
    got = verdict(HOOK, case_payload(command, kind))
    wrong += got != "silent"
    print(f"  {got:<6} {cid:<4} {desc}")

print("\nnon-command payloads (must fail open silently):")
for data, desc in NON_COMMAND_PAYLOADS:
    got = verdict(HOOK, data)
    wrong += got != "silent"
    print(f"  {got:<6} {desc}")

# A GITLAB_HOST inherited by the hook process names the host.
inherited = run_hook(HOOK, payload("glab api user", "plain"),
                     {"GITLAB_HOST": "gitlab.example.org"})
inherit_ok = not inherited.strip()
print(f"\n  {'ok  ' if inherit_ok else 'WRONG'} INHERITED  GITLAB_HOST in the hook environment silences the warning")
wrong += not inherit_ok

# The message must carry the remedy, and an Antigravity run must not double-print.
out = json.loads(run_hook(HOOK, payload("glab api user", "plain")))
ctx = out["hookSpecificOutput"]["additionalContext"]
message_ok = "--hostname" in ctx and "systemMessage" in out
print(f"\n  {'ok  ' if message_ok else 'WRONG'} MESSAGE  names --hostname and sets systemMessage")
wrong += not message_ok

total = len(SHOULD_WARN) + len(SHOULD_STAY_SILENT) + len(NON_COMMAND_PAYLOADS)
print(f"\n{total + 2 - wrong}/{total + 2} correct"
      + ("" if wrong == 0 else f"  ({wrong} WRONG)"))

EXPECTED = {cid: "WARN" for cid, *_ in SHOULD_WARN}
EXPECTED.update({cid: "silent" for cid, *_ in SHOULD_STAY_SILENT})
CASES = {cid: (command, kind)
         for cid, command, kind, _ in SHOULD_WARN + SHOULD_STAY_SILENT}

MUTATIONS = {
    "M1_hostname_flag": (
        "dropping the --hostname exemption makes S1/S2 warn",
        [('if tok == "--hostname" or tok.startswith("--hostname="):',
          'if False:')],
        {"S1", "S2"},
    ),
    "M2_repo_host": (
        "dropping the host-qualified -R exemption makes S3/S4/S14 warn",
        [('if value is not None and RX_HOST_REPO.match(value):',
          'if False:')],
        {"S3", "S4", "S14"},
    ),
    "M3_env_prefix": (
        "dropping the GITLAB_HOST prefix exemption makes S5 warn",
        [('env_value(env, "GITLAB_HOST") or ', '')],
        {"S5"},
    ),
    "M4_export": (
        "dropping the export exemption makes S6 warn",
        [('if names_host(rest) or exported_host:', 'if names_host(rest):')],
        {"S6", "S15"},
    ),
    "M5_cwd_remote": (
        "ignoring the cwd remote makes S7 and S13 warn",
        [('if cur_dir is not None and cwd_names_host(cur_dir):', 'if False:')],
        {"S7", "S13"},
    ),
    "M6_cwd_gitlabcom_not_host": (
        "treating gitlab.com as a named host silences W2",
        [('NOT_GITLAB_HOSTS = {"gitlab.com", "www.gitlab.com", "github.com"}',
          'NOT_GITLAB_HOSTS = {"github.com"}')],
        {"W2"},
    ),
    "M7_subcommand_filter": (
        "dropping the host-sensitive subcommand filter makes S8/S9 warn",
        [('if sub not in HOST_SENSITIVE:', 'if sub is None:')],
        {"S8", "S9"},
    ),
    "M8_cd_tracking": (
        "ignoring cd makes W6 silent (still in the self-hosted checkout) "
        "and S13 warn",
        [('cur_dir = resolve_cd_target(rest, cur_dir)', 'pass')],
        {"W6", "S13"},
    ),
    "M9_program_is_glab": (
        "dropping the program check lets gh api (a sensitive-looking "
        "second token) warn",
        [('if prog != "glab":', 'if False:')],
        {"S12"},
    ),
    "M10_value_flags": (
        "value-taking flags must be skipped when finding the subcommand",
        [('        if tok in VALUE_FLAGS:', '        if False:')],
        {"W11", "W12"},
    ),
}

print("\nmutation tests (break one clause, see which cases flip):")
mutation_wrong = 0
for clause, (statement, edits, expected_flips) in MUTATIONS.items():
    mutated = SOURCE
    for find, replace in edits:
        count = mutated.count(find)
        if count != 1:
            sys.exit(f"FATAL: clause {clause}'s anchor is present {count} "
                     f"times in {HOOK}, expected once:\n{find}")
        mutated = mutated.replace(find, replace)
    # The copy must sit next to the hook: it resolves scripts/lib from __file__.
    fd, path = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(HOOK))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(mutated)
    try:
        flipped = {cid for cid, (command, kind) in CASES.items()
                   if verdict(path, case_payload(command, kind)) != EXPECTED[cid]}
    finally:
        os.unlink(path)
    ok = flipped == expected_flips
    mutation_wrong += not ok
    note = ("flipped " + ", ".join(sorted(flipped)) if flipped
            else "NOTHING FLIPPED -- this clause is untested")
    if not ok:
        note += f" (expected {sorted(expected_flips)})"
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<28} {statement}\n         {note}")

print(f"\n{len(MUTATIONS) - mutation_wrong}/{len(MUTATIONS)} clauses behaved "
      "as declared under mutation")

shutil.rmtree(ROOT, ignore_errors=True)
sys.exit(1 if (wrong or mutation_wrong) else 0)
