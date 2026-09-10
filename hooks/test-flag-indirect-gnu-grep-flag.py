r"""Test the flag-indirect-gnu-grep-flag guard, clause by clause.

Case #1 is the incident verbatim -- the exact pipeline run in
`Morrison-Lab/qwt` on 2026-09-10, whose empty stdout and rc=1 were read as
"no tracked file contains an em dash" when BSD `grep` had in fact rejected
`-P` before opening a file. Per
`shared/workflow/algorithmatize-checks.md`'s "Test the instrument against the
incident that prompted it, verbatim", it is reproduced unaltered rather than
paraphrased.

This guard is pure text over the command string -- it reads no repository
state -- so every case is a JSON payload, as in
`test-flag-unchained-branch-switch.py` rather than
`test-flag-add-a-outside-pathspec.py`.

The negative cases carry most of the design. A bare `grep -P` typed directly
must NOT warn (the session's own `grep` may well be `ugrep`, and flagging it
would be noise on a working command), and `find ... | grep -P` must NOT warn
either, because a pipe makes grep the shell's OWN child, where a function
does apply -- only `find -exec` crosses the boundary. Those two are the whole
reason the trigger is the indirection and not the flag.

The second half is the MUTATION harness described in
`shared/principles/fail-fast.md`: each clause is reverted on its own and the
cases expected to flip are checked against what actually flipped.

Run:  python3 hooks/test-flag-indirect-gnu-grep-flag.py \
          hooks/flag-indirect-gnu-grep-flag.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

# A literal backslash, built rather than typed: a doubled backslash
# collapses in transit through a heredoc on this platform, per
# CLAUDE.md's "Tool transport collapses doubled backslashes".
B = chr(92)

HOOK = os.path.abspath(sys.argv[1])


def verdict(command, hook=None, tool="Bash"):
    """True when the guard warns (emits additionalContext), else False."""
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    env = dict(os.environ)
    env["HOOK_DRY_RUN"] = "1"
    proc = subprocess.run(
        [sys.executable, hook or HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "hook exited %s: %s" % (proc.returncode, proc.stderr)
        )
    try:
        out = json.loads(proc.stdout or "{}")
    except Exception as exc:
        raise AssertionError("unparseable hook stdout %r (%s)"
                             % (proc.stdout, exc))
    return "additionalContext" in (out.get("hookSpecificOutput") or {})


# (id, command, expect_warning, why)
CASES = [
    ("C1-incident",
     "git ls-files -z | xargs -0 grep -lP '[" + B + "x{2014}]'",
     True,
     "the incident verbatim: -P reached through xargs"),

    ("C2-xargs-long-flag",
     "git ls-files -z | xargs -0 grep --perl-regexp 'a'",
     True,
     "long form of the same flag"),

    ("C3-find-exec",
     "find . -name '*.md' -exec grep -lP 'x' {} +",
     True,
     "find -exec spawns grep as a child"),

    ("C4-sh-c",
     "sh -c " + chr(39) + "grep -P pat file" + chr(39) + ",",
     True,
     "sh -c is a fresh shell; a parent function does not cross it"),

    ("C5-clustered",
     "git ls-files -z | xargs -0 grep -lP 'x'",
     True,
     "clustered short flags -lP still carry P"),

    ("C6-bare-grep-P",
     "grep -P '[" + B + "x{2014}]' README.md",
     False,
     "typed directly: the session's own grep may support -P, so warning is noise"),

    ("C7-pipe-to-grep",
     "find . -name '*.md' | grep -P 'x'",
     False,
     "a PIPE makes grep the shell's own child, where a function applies"),

    ("C8-xargs-portable-grep",
     "git ls-files -z | xargs -0 grep -l 'plain'",
     False,
     "no GNU-only flag: portable across both greps"),

    ("C9-grep-in-pattern",
     "git ls-files -z | xargs -0 grep -l 'xargs'",
     False,
     "the word xargs inside a PATTERN is not an indirection"),

    ("C10-not-bash-tool",
     "git ls-files -z | xargs -0 grep -lP 'x'",
     False,
     "a non-Bash tool payload is out of scope"),

    ("C11-exclude-dir-portable",
     "find . -type f -exec grep --exclude-dir=.git -l x {} +",
     False,
     "--exclude-dir WORKS on BSD grep (measured rc=0), so warning would be "
     "a false claim on a portable command"),

    ("C13-abs-path-grep",
     "git ls-files -z | xargs -0 /usr/bin/grep -lP 'x'",
     True,
     "an absolute path pins BSD grep past any function, so it is more exposed"),

    ("C14-abs-path-portable",
     "git ls-files -z | xargs -0 /usr/bin/grep -l 'x'",
     False,
     "absolute path but no GNU-only flag"),

    ("C16-ggrep-is-gnu",
     "git ls-files -z | xargs -0 ggrep -lP 'x'",
     False,
     "ggrep IS GNU grep, where -P works (measured: /usr/bin/egrep and fgrep "
     "reject it, ggrep does not exist here), so warning would be a false claim"),

    ("C17-egrep",
     "git ls-files -z | xargs -0 egrep -lP 'x'",
     True,
     "BSD ships egrep, it rejects -P (measured), and egrep is an alias "
     "(grep -E) in this session, so the boundary argument applies"),

    ("C18-grep-as-argument",
     "git ls-files -z | xargs -0 python3 script.py grep -P somefile",
     False,
     "xargs runs python3; `grep -P` is a pair of plain arguments to "
     "script.py, so nothing here invokes grep at all"),

    ("C19-xargs-placeholder",
     "git ls-files | xargs -I {} grep -lP 'x' {}",
     True,
     "xargs -I's placeholder sits before the utility and must be skipped "
     "when locating it"),

    ("C20-find-semicolon",
     "find . -name '*.md' -exec grep -lP 'x' {} " + B + ";",
     True,
     "the per-file -exec form; it warns, and its rc story differs from the "
     "+ form's (find exits 0, discarding the child's status entirely)"),

    ("C15-z-portable",
     "git ls-files -z | xargs -0 grep -lz 'x'",
     False,
     "-z is documented and works on BSD grep (measured rc=0)"),

    ("C12-no-grep-at-all",
     "git ls-files -z | xargs -0 wc -l",
     False,
     "no grep: nothing to say"),
]


def run_cases(hook=None, quiet=False):
    """Return {case_id: bool}. Raises on a hook crash."""
    got = {}
    for cid, cmd, _expect, _why in CASES:
        tool = "Read" if cid == "C10-not-bash-tool" else "Bash"
        got[cid] = verdict(cmd, hook=hook, tool=tool)
    return got


def baseline():
    failures = []
    got = run_cases()
    for cid, cmd, expect, why in CASES:
        ok = got[cid] is expect
        print("  %s %-22s expected=%-5s got=%-5s  %s"
              % ("PASS" if ok else "FAIL", cid, expect, got[cid], why))
        if not ok:
            failures.append(cid)
    return got, failures


# Each mutation reverts ONE clause. `expect_flip` names the cases whose
# verdict must change; an empty set would be an admission of no coverage
# rather than a pass, per the harness note above.
MUTATIONS = [
    ("M1-drop-indirection-requirement",
     # Treat every grep as indirect: the pipe and bare cases must now warn.
     ('    if via is None:' + chr(10) + '        return None',
      '    if via is None:' + chr(10) + '        via = via or "xargs"'
       + chr(10) + '        via_at = 0 if via_at is None else via_at'),
     {"C6-bare-grep-P", "C7-pipe-to-grep"}),

    ("M2-drop-find-exec-handling",
     # Stop treating `find` specially in the utility lookup. Its utility then
     # resolves to the first non-flag token (the search path), not the grep
     # after -exec, so the find -exec case must stop warning. The pipe case
     # stays silent either way, which is why C3 rather than C7 is the probe
     # here -- the earlier anchor conflated the two.
     ('    if base == "find":', '    if False:'),
     {"C3-find-exec"}),

    ("M3-drop-flag-requirement",
     # Any indirect grep warns, flag or not.
     ('    for t in toks[grep_at + 1:]:',
      '    return "-P", via, command, invoked, pinned, GNU_ONLY_FLAGS[\"-P\"], RC_LAUNDERED' + chr(10) + '    for t in toks[grep_at + 1:]:'),
     # C12 carries no grep token at all, so it returns before the
     # mutated line is reached -- excluded rather than faked.
     {"C8-xargs-portable-grep", "C9-grep-in-pattern",
      "C11-exclude-dir-portable", "C14-abs-path-portable",
      # C16 is excluded for the same reason as C12: `ggrep` is not in the
      # name set, so grep_at is None and the function returns before the
      # mutated line. M6-readmit-ggrep is what covers that clause.
      # C19 already warns, so removing the flag requirement cannot flip it.
      "C15-z-portable"}),

    ("M5-drop-path-strip",
     # Require a bare `grep` token again: the absolute-path case must stop
     # warning, which is precisely the false negative a reviewer found.
     ('        if t.rsplit("/", 1)[-1] in {"grep", "egrep", "fgrep"}:',
      '        if t in {"grep", "egrep", "fgrep"}:'),
     {"C13-abs-path-grep"}),

    ("M6-readmit-ggrep",
     # Put ggrep back in the match set: the GNU-grep case must start warning,
     # which is the false claim a reviewer found on the binary-identity axis.
     ('in {"grep", "egrep", "fgrep"}:', 'in {"grep", "ggrep", "egrep", "fgrep"}:'),
     {"C16-ggrep-is-gnu"}),

    ("M7-decouple-utility-check",
     # Accept any indirection paired with any grep token, instead of
     # requiring the indirection to actually RUN that grep. The
     # grep-as-argument case must start warning, which is the false positive
     # a reviewer found.
     ('        if _utility_after(toks, i) == grep_at:',
      '        if True:'),
     {"C18-grep-as-argument"}),

    ("M4-drop-tool-gate",
     ('    if tool != "Bash":' + chr(10) + '        return None', '    pass'),
     {"C10-not-bash-tool"}),
]


def mutate():
    src = open(HOOK, encoding="utf-8").read()
    base, _ = {}, None
    base = run_cases()
    failures = []
    for mid, (old, new), expect_flip in MUTATIONS:
        if old not in src:
            print("  FAIL %-32s anchor not found; mutation not applied" % mid)
            failures.append(mid)
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(src.replace(old, new, 1))
            path = fh.name
        try:
            got = run_cases(hook=path)
            flipped = {cid for cid in base if got[cid] is not base[cid]}
        except AssertionError as exc:
            # A mutation that makes the hook crash is also detected -- the
            # clause is load-bearing. Report it as covering its expected set.
            print("  PASS %-32s mutant crashed (%s)" % (mid, str(exc)[:40]))
            os.unlink(path)
            continue
        os.unlink(path)
        ok = flipped >= expect_flip
        print("  %s %-32s expected_flip=%s actual_flip=%s"
              % ("PASS" if ok else "FAIL", mid,
                 sorted(expect_flip), sorted(flipped)))
        if not ok:
            failures.append(mid)
    return failures


def stderr_quote_matches_flag():
    """Each flag's warning must quote the stderr BSD grep produced for THAT
    flag. An earlier draft hard-coded the short form's text, so a
    `--perl-regexp` trigger quoted an error BSD grep never prints for it --
    the warning itself then carried a false claim, which is the very failure
    class this hook exists to catch. Asserted rather than eyeballed."""
    expected = {
        "-P": "invalid option -- P",
        "--perl-regexp": "unrecognized option " + chr(96) + "--perl-regexp'",
    }
    failures = []
    for flag, want in expected.items():
        payload = {"tool_name": "Bash",
                   "tool_input": {"command":
                                  "ls | xargs -0 grep -l " + flag + " 'x'"}}
        proc = subprocess.run([sys.executable, HOOK],
                              input=json.dumps(payload),
                              capture_output=True, text=True)
        ctx = (json.loads(proc.stdout or "{}")
               .get("hookSpecificOutput", {}).get("additionalContext", ""))
        ok = want in ctx
        # The OTHER flag's text must be absent, or a template quoting both
        # would pass vacuously.
        other = [v for k, v in expected.items() if k != flag][0]
        clean = other not in ctx
        print("  %s %-16s quotes its own stderr=%s  excludes other=%s"
              % ("PASS" if (ok and clean) else "FAIL", flag, ok, clean))
        if not (ok and clean):
            failures.append(flag)
    return failures


def rc_story_matches_indirection():
    r"""Each indirection must get the rc behaviour MEASURED for it.

    A draft asserted "launders rc=2 into rc=1" for all seven indirections
    having measured only `xargs`. Measured 2026-09-10 against a stub printing
    BSD grep's rejection and exiting 2:

        sh -c / bash -c / zsh -c / env  rc=2  preserved
        xargs -0                        rc=1  laundered
        find ... {} +                   rc=1  laundered
        find ... {} \;                  rc=0  discarded

    The four preserved cases are the ones that matter most to get right: the
    old text told a reader an rc check could not separate a rejected flag
    from a no-match, in exactly the cases where it can.
    """
    expect = [
        ("ls | xargs -0 grep -lP 'x'", "rc=1", "laundered"),
        ("ls | parallel grep -lP 'x'", "rc=1", "laundered"),
        ("sh -c " + chr(39) + "grep -P x f" + chr(39), "rc=2", "preserved"),
        ("bash -c " + chr(39) + "grep -P x f" + chr(39), "rc=2", "preserved"),
        ("zsh -c " + chr(39) + "grep -P x f" + chr(39), "rc=2", "preserved"),
        ("env grep -P x f", "rc=2", "preserved"),
        ("find . -exec grep -lP x {} +", "rc=1", "laundered"),
        ("find . -exec grep -lP x {} " + B + ";", "rc=0", "discarded"),
    ]
    failures = []
    for cmd, want_rc, label in expect:
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        proc = subprocess.run([sys.executable, HOOK],
                              input=json.dumps(payload),
                              capture_output=True, text=True)
        # A template whose literal braces are unescaped raises on .format(),
        # so the hook exits non-zero emitting nothing -- a check that only
        # asked "did it warn?" would call that a missing warning.
        #
        # For the find-semicolon template this branch is NOT what catches it:
        # `C20-find-semicolon` in CASES runs the same command through
        # `verdict()`, which raises on a non-zero exit, and that fires first.
        # This branch covers the commands only THIS section runs: `parallel`,
        # `bash -c`, `zsh -c` and `env`. (`sh -c` is C4, and `xargs` and both
        # `find` forms are C1/C3/C20, so those are already covered above.)
        # Derived by grepping CASES for each, not recalled -- an earlier draft
        # of this very comment listed `sh -c` here and was wrong.
        if proc.returncode != 0:
            print("  FAIL %-28s hook exited %s: %s"
                  % (label + " " + cmd[:14], proc.returncode,
                     proc.stderr.strip()[:60]))
            failures.append(cmd)
            continue
        sm = (json.loads(proc.stdout or "{}")).get("systemMessage", "")
        ok = want_rc in sm
        print("  %s %-9s %-34s expects %s  %s"
              % ("PASS" if ok else "FAIL", label, cmd[:34], want_rc,
                 "" if ok else "got: " + sm[-60:]))
        if not ok:
            failures.append(cmd)
    return failures


def main():


    print("Baseline cases:")
    _, base_fail = baseline()
    print()
    print("Warning-text accuracy:")
    base_fail += stderr_quote_matches_flag()
    print()
    print("Per-indirection rc story:")
    base_fail += rc_story_matches_indirection()
    print()
    print("Mutation coverage:")
    mut_fail = mutate()
    if base_fail or mut_fail:
        print("FAILED: baseline=%s mutation=%s" % (base_fail, mut_fail))
        return 1
    print("All %d cases and %d mutations pass."
          % (len(CASES), len(MUTATIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
