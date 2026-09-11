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
import importlib.util
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


# Read the per-utility notes out of the hook itself, so this check tracks the
# source rather than duplicating it -- and assert they are distinct, since a
# check for "its own note" is vacuous if two utilities share one.
def _load_laundered_notes():
    spec = importlib.util.spec_from_file_location("_h", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    notes = dict(mod.LAUNDERED_NOTE)
    assert len(set(notes.values())) == len(notes), (
        "two utilities share a laundered note; the per-utility check would "
        "pass vacuously")
    return notes


LAUNDERED_NOTES = _load_laundered_notes()

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

    ("C21-nested-xargs-over-sh",
     "ls | xargs -0 sh -c " + chr(39) + "grep -P x f" + chr(39),
     True,
     "an inner sh -c runs the grep and an outer xargs runs the sh; it warns, "
     "and the rc story must come from the outer link"),

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
     # Accept a command with no indirection chain reaching the grep: the bare
     # and piped cases must now warn.
     ('    if not chain:' + chr(10) + '        return None',
      '    if not chain:' + chr(10) + '        chain = [0]'),
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
      '    return "-P", via, command, invoked, pinned, GNU_ONLY_FLAGS[\"-P\"], RC_LAUNDERED, "xargs"' + chr(10) + '    for t in toks[grep_at + 1:]:'),
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
     # Let any indirection join the chain without running the next link, so
     # `xargs -0 python3 script.py grep -P f` is attributed again.
     ('            if t in INDIRECTIONS and _utility_after(toks, i) == cur:',
      '            if t in INDIRECTIONS:'),
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
        xargs -0                        laundered (1 on BSD, 123 on GNU)
        find ... {} +                   laundered
        find ... {} \;                  rc=0  discarded

    The four preserved cases are the ones that matter most to get right: the
    old text told a reader an rc check could not separate a rejected flag
    from a no-match, in exactly the cases where it can.
    """
    expect = [
        ("ls | xargs -0 grep -lP 'x'", "a status of its own", "laundered"),
        ("ls | parallel grep -lP 'x'", "a status of its own", "laundered"),
        ("sh -c " + chr(39) + "grep -P x f" + chr(39), "rc=2", "preserved"),
        ("bash -c " + chr(39) + "grep -P x f" + chr(39), "rc=2", "preserved"),
        ("zsh -c " + chr(39) + "grep -P x f" + chr(39), "rc=2", "preserved"),
        ("env grep -P x f", "rc=2", "preserved"),
        ("find . -exec grep -lP x {} +", "a status of its own", "laundered"),
        ("find . -exec grep -lP x {} " + B + ";", "rc=0", "discarded"),
        # Nested chains. The observable status is the chain composed outward,
        # so an inner `sh -c` that preserves rc=2 is overridden by whatever
        # the outer link does -- measured, not inferred. An earlier draft
        # reported the INNERMOST link's behaviour and so promised rc=2 here,
        # pointing a reader at a `case $rc` branch that never fires.
        ("ls | xargs -0 sh -c " + chr(39) + "grep -P x f" + chr(39),
         "a status of its own", "nested: xargs over sh"),
        ("find . -exec sh -c " + chr(39) + "grep -P x {}" + chr(39) + " " + B + ";",
         "rc=0", "nested: find ; over sh"),
        ("find . -exec sh -c " + chr(39) + "grep -P x" + chr(39) + " +",
         "a status of its own", "nested: find + over sh"),
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


def composition_clause_is_load_bearing():
    """Mutate the chain composition and confirm the rc story regresses.

    This clause cannot be covered by the MUTATIONS harness above, which
    compares warn-versus-silent: reporting the wrong rc story still warns, so
    nothing there flips. Declaring an empty expected-flip set for it would be
    an admission of no coverage rather than coverage, so the check lives here
    and asserts the regression directly.

    The mutation is the exact defect a reviewer measured: take the innermost
    link's behaviour instead of the composed chain's, and
    `xargs -0 sh -c 'grep -P ...'` goes back to promising rc=2 where the
    caller sees 1.
    """
    src = open(HOOK, encoding="utf-8").read()
    old = "    rc_kind, rc_at = _observable_rc(toks, chain)"
    new = ("    rc_kind, rc_at = _rc_behaviour(toks, chain[-1]), chain[-1]")
    if old not in src:
        print("  FAIL composition anchor not found; mutation not applied")
        return ["composition"]
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src.replace(old, new, 1))
        path = fh.name
    nested = "ls | xargs -0 sh -c " + chr(39) + "grep -P x f" + chr(39)
    payload = {"tool_name": "Bash", "tool_input": {"command": nested}}
    try:
        proc = subprocess.run([sys.executable, path],
                              input=json.dumps(payload),
                              capture_output=True, text=True)
        sm = (json.loads(proc.stdout or "{}")).get("systemMessage", "")
    finally:
        os.unlink(path)
    # Mutated, it must claim the WRONG story (rc=2) for this command.
    regressed = "rc=2" in sm
    print("  %s composition mutant claims rc=2 for a chain measured rc=1: %s"
          % ("PASS" if regressed else "FAIL", regressed))
    return [] if regressed else ["composition"]


def laundering_is_not_platform_asserted():
    r"""The laundered message must not name one platform's exit code as the code.

    This is the gap that let a wrong number survive: `rc_story_matches_indirection`
    compares the hook's rendered text against expectations written from the same
    measurements the hook itself encodes, so a table that is wrong for the host
    and an expectation that is wrong for the host agree with each other. The
    check never ran `xargs`.

    So measure the host's own `xargs` here, and require the message to be
    consistent with whatever it returns rather than with a constant. BSD xargs
    returns 1 for any non-zero child; GNU findutils returns 123. Both are
    laundering, and a message naming only the other platform's value is wrong
    for this one.
    """
    failures = []
    with tempfile.TemporaryDirectory() as d:
        stub = os.path.join(d, "exit2")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh" + chr(10) + "exit 2" + chr(10))
        os.chmod(stub, 0o755)
        stub1 = os.path.join(d, "exit1")
        with open(stub1, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh" + chr(10) + "exit 1" + chr(10))
        os.chmod(stub1, 0o755)

        def through_xargs(path):
            p1 = subprocess.run(["xargs", "-0", path],
                                input=b"x" + bytes([0]),
                                capture_output=True)
            return p1.returncode

        rc2 = through_xargs(stub)
        rc1 = through_xargs(stub1)
        print("  host xargs: child exit 2 -> %s, child exit 1 -> %s" % (rc2, rc1))
        # The load-bearing property is the COLLAPSE, not the value.
        if rc2 != rc1:
            print("  FAIL host xargs distinguishes them; the guard's premise "
                  "does not hold here")
            failures.append("collapse")
        elif rc2 == 2:
            print("  FAIL host xargs preserved the child's status; `xargs` "
                  "should not be in RC_BEHAVIOUR as laundered here")
            failures.append("preserved")
        else:
            print("  PASS host xargs collapses both to %s" % rc2)

    # This check used to require the message to NAME both platform values.
    # That requirement is retired: the runtime text now deliberately states no
    # replacement value at all, and
    # `no_platform_integer_in_runtime_text` enforces the absence. What is still
    # worth asserting here is that the message points somewhere for the number.
    payload = {"tool_name": "Bash",
               "tool_input": {"command": "ls | xargs -0 grep -lP 'x'"}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True)
    ctx = (json.loads(proc.stdout or "{}")
           ).get("hookSpecificOutput", {}).get("additionalContext", "")
    points_at_record = "debugging.cases.md" in ctx
    print("  %s message points at the cases file for the measured value: %s"
          % ("PASS" if points_at_record else "FAIL", points_at_record))
    if not points_at_record:
        failures.append("no-pointer-to-record")
    return failures


def laundered_note_names_only_its_own_utility():
    """A laundered warning must not describe one utility with another's numbers.

    The gap this closes: the sentence was corrected for `xargs` and kept
    rendering verbatim for `parallel` and `find ... {} +`, telling a reader the
    value came from "the BSD/macOS xargs" for commands that invoke no xargs.
    Every earlier check looked for the class label, which all three share, so
    none of them could see it.
    """
    expect = [
        ("ls | xargs -0 grep -lP 'x'", "xargs", ["parallel"]),
        ("ls | parallel grep -lP 'x'", "parallel", ["xargs"]),
        ("find . -exec grep -lP x {} +", "find", ["xargs", "parallel"]),
    ]
    failures = []
    for cmd, own, foreign in expect:
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True)
        ctx = (json.loads(proc.stdout or "{}")
               ).get("hookSpecificOutput", {}).get("additionalContext", "")
        note = LAUNDERED_NOTES.get(own)
        has_own = note in ctx if note else False
        # No OTHER utility's note may appear.
        leaked = [f for f in foreign
                  if LAUNDERED_NOTES.get(f) and LAUNDERED_NOTES[f] in ctx]
        ok = has_own and not leaked
        print("  %s %-9s carries its own note=%s  foreign notes leaked=%s"
              % ("PASS" if ok else "FAIL", own, has_own, leaked or "none"))
        if not ok:
            failures.append(own)
    return failures


def blames_the_transforming_link():
    r"""The rc story must name the link that CHANGES the status.

    Not the outermost. The two differ whenever a pass-through wraps a
    transformer, which every earlier nested case had backwards: each tested a
    launderer OUTSIDE a shell, so naming the outermost happened to be right and
    nothing probed the reverse. `sh -c 'xargs -0 grep -P x'` then described
    `sh` as replacing a status it passes through, and fell back to the generic
    unmeasured note while `xargs`'s measured one sat unused.
    """
    expect = [
        # (command, utility the message must blame)
        ("ls | xargs -0 grep -lP " + chr(39) + "x" + chr(39), "xargs", True),
        ("sh -c " + chr(39) + "grep -P x f" + chr(39), "sh", True),
        # launderer outside a shell -- the shape the old code got right
        ("ls | xargs -0 sh -c " + chr(39) + "grep -P x f" + chr(39), "xargs", True),
        # pass-through outside a launderer -- the shape it got wrong
        ("sh -c " + chr(39) + "xargs -0 grep -P x" + chr(39), "xargs", True),
        ("sh -c " + chr(39) + "find . -exec grep -P x {} +" + chr(39), "find", True),
        # DISCARDED rather than LAUNDERED, so it carries no laundered note --
        # `want_note` is False here for that reason, not as an exemption.
        ("sh -c " + chr(39) + "find . -exec grep -P x {} " + B + ";" + chr(39),
         "find", False),
    ]
    failures = []
    for cmd, blame, want_note in expect:
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True)
        d = json.loads(proc.stdout or "{}")
        sm = d.get("systemMessage", "")
        ctx = d.get("hookSpecificOutput", {}).get("additionalContext", "")
        blamed = ("(through " + chr(96) + blame + chr(96) + ")") in sm
        # And a laundering utility must still carry ITS note, not the default.
        note = LAUNDERED_NOTES.get(blame)
        note_ok = ((note in ctx) if note else True) if want_note else True
        ok = blamed and note_ok
        print("  %s blames %-6s and carries its own note=%s  %s"
              % ("PASS" if ok else "FAIL", blame, note_ok, cmd[:40]))
        if not ok:
            failures.append(cmd)
    # Prove the responsible-link tracking is load-bearing, rather than
    # declaring an empty expected-flip set in the MUTATIONS table -- that table
    # compares warn-versus-silent, and a misattributed rc story still warns.
    src = open(HOOK, encoding="utf-8").read()
    old = "        if rc != before:" + chr(10) + "            responsible = i"
    new = "        if False:" + chr(10) + "            responsible = i"
    if old not in src:
        print("  FAIL blame anchor not found; mutation not applied")
        return failures + ["blame-mutation"]
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src.replace(old, new, 1))
        path = fh.name
    try:
        cmd = "sh -c " + chr(39) + "xargs -0 grep -P x" + chr(39)
        proc = subprocess.run([sys.executable, path],
                              input=json.dumps({"tool_name": "Bash",
                                                "tool_input": {"command": cmd}}),
                              capture_output=True, text=True)
        sm = (json.loads(proc.stdout or "{}")).get("systemMessage", "")
    finally:
        os.unlink(path)
    regressed = ("(through " + chr(96) + "sh" + chr(96) + ")") in sm
    print("  %s blame-outermost mutant misattributes to `sh`: %s"
          % ("PASS" if regressed else "FAIL", regressed))
    if not regressed:
        failures.append("blame-mutation")
    return failures


def no_platform_integer_in_runtime_text():
    r"""No implementation-specific laundered value may reach the runtime text.

    This is the structural guard, not another case. Eight findings on this file
    were one class, and six were per-utility/per-platform exit-code numbers in
    the warning text. Each was fixed by correcting that number; none stopped
    the next one. So forbid the surface instead: the runtime message may state
    grep's OWN codes (2 for a rejection, 1 for a no-match, 0 where a status is
    discarded), because those are properties of grep and of the three-way
    classification, and may not state an indirection's replacement value.

    `123` is GNU findutils' value and is the canonical instance. It belongs in
    `memories/debugging.cases.md`, and this asserts it is there and not here.
    """
    own_codes = {"0", "1", "2"}
    failures = []
    probes = [
        "ls | xargs -0 grep -lP " + chr(39) + "x" + chr(39),
        "ls | parallel grep -lP " + chr(39) + "x" + chr(39),
        "find . -exec grep -lP x {} +",
        "find . -exec grep -lP x {} " + B + ";",
        "sh -c " + chr(39) + "xargs -0 grep -P x" + chr(39),
        "sh -c " + chr(39) + "grep -P x f" + chr(39),
    ]
    for cmd in probes:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": cmd}}),
            capture_output=True, text=True)
        d = json.loads(proc.stdout or "{}")
        text = (d.get("systemMessage", "") + chr(10)
                + d.get("hookSpecificOutput", {}).get("additionalContext", ""))
        # Match integers in an EXIT-CODE context only. An earlier draft of
        # this check scanned every integer and flagged the date (2026-09-10)
        # and the version string (2.6.0-FreeBSD) -- a detector so broad it
        # could never pass, which is its own failure mode.
        coded = set()
        for pat in (r"rc=([0-9]+)", r"exits? (?:to )?[*]{0,2}([0-9]+)[*]{0,2}",
                    r"give[s]? [*]{0,2}([0-9]+)[*]{0,2}",
                    r"report[s]? [*]{0,2}([0-9]+)[*]{0,2}",
                    r"status of [*]{0,2}([0-9]+)[*]{0,2}"):
            coded.update(re.findall(pat, text))
        # `123` is GNU findutils' value and the canonical instance, so it is
        # forbidden outright rather than only in a matched context.
        suspect = {n for n in coded if n not in own_codes}
        if "123" in text:
            suspect.add("123")
        if suspect:
            print("  FAIL %-34s platform value(s) in runtime text: %s"
                  % (cmd[:34], sorted(suspect)))
            failures.append(cmd)
        else:
            print("  PASS %-34s no platform value in runtime text" % cmd[:34])
    # And the cases file must still carry the number the runtime text dropped.
    cases = os.path.join(os.path.dirname(os.path.dirname(HOOK)),
                         "memories", "debugging.cases.md")
    if os.path.exists(cases):
        has = "123" in open(cases, encoding="utf-8").read()
        print("  %s cases file still records GNU findutils' 123: %s"
              % ("PASS" if has else "FAIL", has))
        if not has:
            failures.append("cases-file")
    return failures


def every_platform_claim_is_hedged():
    """Both rendered surfaces must hedge which binary PATH resolves to.

    The structural guard for the hedging half of this file's recurring class,
    mirroring `no_platform_integer_in_runtime_text` for the numeric half.

    The claim "BSD grep rejects this flag" is only ever conditional: the module
    warns rather than blocks precisely because which grep resolves in the child
    is not decidable from the command text. Two rounds fixed that claim in one
    rendered surface and left the textually-parallel sibling unhedged -- first
    the two `systemMessage` branches against each other, then `systemMessage`
    against `NOTE_RESOLVED`. So assert it across every surface at once rather
    than per location.
    """
    # A hedge is any of these, in either surface.
    HEDGES = ("if it is", "if that resolves", "is not decidable",
              "this warning is noise")
    failures = []
    probes = [
        ("resolved", "ls | xargs -0 grep -lP " + chr(39) + "x" + chr(39)),
        ("pinned", "ls | xargs -0 /usr/bin/grep -lP " + chr(39) + "x" + chr(39)),
        ("resolved-nested", "sh -c " + chr(39) + "xargs -0 grep -P x" + chr(39)),
        ("pinned-find",
         "find . -exec /usr/bin/grep -lP x {} +"),
    ]
    for label, cmd in probes:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"tool_name": "Bash",
                              "tool_input": {"command": cmd}}),
            capture_output=True, text=True)
        d = json.loads(proc.stdout or "{}")
        sm = d.get("systemMessage", "")
        ctx = d.get("hookSpecificOutput", {}).get("additionalContext", "")
        sm_ok = any(h in sm for h in HEDGES)
        ctx_ok = any(h in ctx for h in HEDGES)
        ok = sm_ok and ctx_ok
        print("  %s %-16s systemMessage hedged=%s  additionalContext hedged=%s"
              % ("PASS" if ok else "FAIL", label, sm_ok, ctx_ok))
        if not ok:
            failures.append(label)
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
    print("Every platform claim is hedged:")
    base_fail += every_platform_claim_is_hedged()
    print()
    print("No platform integer in runtime text:")
    base_fail += no_platform_integer_in_runtime_text()
    print()
    print("Blames the transforming link:")
    base_fail += blames_the_transforming_link()
    print()
    print("Laundered note names only its own utility:")
    base_fail += laundered_note_names_only_its_own_utility()
    print()
    print("Laundering is measured, not asserted:")
    base_fail += laundering_is_not_platform_asserted()
    print()
    print("Composition coverage:")
    mut_fail = composition_clause_is_load_bearing()
    print()
    print("Mutation coverage:")
    mut_fail += mutate()
    if base_fail or mut_fail:
        print("FAILED: baseline=%s mutation=%s" % (base_fail, mut_fail))
        return 1
    print("All %d cases and %d mutations pass."
          % (len(CASES), len(MUTATIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
