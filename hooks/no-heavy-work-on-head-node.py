#!/usr/bin/env python3
"""PreToolUse guard: refuse expensive commands run on a cluster's head node.

On 2026-07-31 the shiva sysadmin reported CPU-load alerts on the login node,
caused by two `R -e '...devtools::test()...'` processes that had been running
for 262 and 90 CPU-minutes. The rule they broke was already written down --
twice, in `.claude/memories/shiva-cluster.md`: "SLURM is mandatory; never run
jobs on the head node" and "Never run heavy jobs directly on the login/head
node itself."

It was violated anyway, because a passive prose rule only fires if you happen
to read it at the moment you type the command, and the command produced a
perfectly correct test result either way. Nothing in the output reported the
violation -- see the `routing-failures-leave-no-trace` memory. So the check
has to run at the command, not in a file someone might consult.

Deciding this needs no judgment: either this host is a SLURM compute node or
it is not, and `sinfo` answers that exactly.

Fails OPEN, like the other guards here. Off-cluster, or with SLURM
unreachable, it allows everything.
"""
import json
import os
import re
import subprocess
import sys

# Where an R/quarto interpreter is actually *invoked*: at the start of the
# command or just after a shell operator, allowing VAR=value assignments.
#
# Matching the invocation rather than the token anywhere in the text is the
# whole difference between gating a command and gating any sentence that
# mentions one -- `grep -rn 'devtools::test' scripts/` contains the token and
# must not be blocked, since the fix this guard demands would be nonsense
# there. A first attempt let the token match anywhere and did block exactly
# that (caught by test_mentioning_it_is_not_running_it).
#
# Note this deliberately does NOT split the command into segments and judge
# each one. A second attempt did, and it missed the very incident this guard
# exists for: `R -e 'Sys.setenv(...); res <- devtools::test()'` splits on the
# `;` inside the R expression, leaving a fragment whose leading word is `res`.
# The `;` is R syntax, not a shell separator, and nothing at this level can
# tell the two apart. So instead: find each invocation, then scan from there
# to the end of the string, which keeps quoted code with the command running
# it. Anything before the first invocation stays unexamined, which is what
# keeps the grep case above passing.
#
# `srun`/`sbatch`/`salloc` are absent by construction -- a command led by one
# of those never matches, so correctly-routed work is allowed with no
# special case.
INVOCATION = re.compile(
    r"(?:^|&&|\|\||;|\||\n)\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:[\w./-]*/)?(R|Rscript|quarto)\b"
)

# What made the sysadmin's alert fire, plus close relatives. Deliberately NOT
# "any R invocation": `Rscript -e 'cat(R.version.string)'` costs nothing, and
# gating it would add a scheduler round-trip to every trivial lookup and train
# me to distrust the guard.
EXPENSIVE = [
    (r"\bdevtools::(test|check|document|install|build|load_all)\b", "devtools::test/check/..."),
    (r"\btestthat::(test_dir|test_local|test_package|test_file)\b", "testthat::test_*"),
    (r"\blintr::(lint_package|lint_dir)\b", "lintr::lint_package"),
    (r"\brenv::(restore|install|snapshot|hydrate|rebuild)\b", "renv::restore/install"),
    (r"\bspelling::spell_check_package\b", "spelling::spell_check_package"),
    (r"\bcovr::\w+", "covr"),
    (r"^\s*R\s+CMD\s+(check|build|INSTALL)\b", "R CMD check/build/INSTALL"),
    (r"\b(render|preview)\b", "quarto render"),
    (r"\brmarkdown::render\b", "rmarkdown::render"),
    (r"\bpkgdown::\w+", "pkgdown"),
    (r"\baltdoc::\w+", "altdoc"),
    # Running a script FILE (as opposed to -e) is nearly always non-trivial,
    # and every precompute/simulation driver in data-raw/ takes this form.
    (r"^\s*Rscript\s+(?:--\S+\s+)*[\w./~$-]+\.[Rr]\b", "Rscript <file>"),
]
EXPENSIVE = [(re.compile(p), label) for p, label in EXPENSIVE]


def offending(command: str):
    for match in INVOCATION.finditer(command):
        tail = command[match.start(1):]      # from the program name onward
        for pattern, label in EXPENSIVE:
            if pattern.search(tail):
                return label, tail.strip()
    return None


def compute_nodes():
    """The cluster's own list of compute nodes, or None if not on a cluster.

    Read from sinfo rather than hardcoded, so this keeps working when nodes
    are added or renamed (avoid-hardcoding-external-data).
    """
    try:
        out = subprocess.run(
            ["sinfo", "-h", "-N", "-o", "%N"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None            # no SLURM here at all -- not a cluster
    if out.returncode != 0:
        return None            # SLURM present but unreachable -- fail open
    nodes = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    return nodes or None


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-heavy-work-on-head-node: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or ""

    # Cheap test first: the sinfo call below only runs for a command that would
    # actually be blocked, so the common case costs one regex sweep.
    hit = offending(command)
    if not hit:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    nodes = compute_nodes()
    if nodes is None:
        if is_dry_run or os.environ.get("SIMULATE_HEAD_NODE"):
            nodes = {"node-1", "node-2"}
        else:
            return 0

    host = os.uname().nodename.split(".")[0]
    if host in nodes and not os.environ.get("SIMULATE_HEAD_NODE"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0               # already on a compute node -- nothing to fix

    label, segment = hit
    # Mirror whatever this session was given, so the suggestion is not a guess.
    cpus = os.environ.get("SLURM_CPUS_PER_TASK", "8")
    mem = os.environ.get("SLURM_MEM_PER_NODE")
    mem = f"{int(mem) // 1024}G" if (mem or "").isdigit() else "32G"

    in_alloc = "SLURM_JOB_ID" in os.environ
    alloc_note = (
        "\nNote: SLURM_JOB_ID is set, so you are inside an allocation -- but "
        "this shell is still ON THE HEAD NODE, which is exactly the salloc "
        "trap. An allocation reserves resources; only srun moves work onto "
        "them.\n"
        if in_alloc else ""
    )

    reason = (
        f"Blocked: `{label}` on the head node ({host}).\n\n"
        f"    {segment}\n\n"
        f"Compute nodes here are {', '.join(sorted(nodes))}. Running this "
        "where you are loads the login node everyone shares -- which is what "
        "drew the sysadmin's CPU-load alert on 2026-07-31, from two "
        "devtools::test() runs that had burned 262 and 90 CPU-minutes.\n"
        f"{alloc_note}\n"
        "Re-issue it through SLURM:\n\n"
        f"    srun --cpus-per-task={cpus} --mem={mem} <the command>\n\n"
        "For anything long-running, prefer sbatch so it survives this session "
        "ending. `sbatch` and `srun` both pass this guard from anywhere."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
