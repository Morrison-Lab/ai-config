#!/usr/bin/env python3
"""Tests for no-recursive-rm-unset-variable.py.

Every case feeds the hook a payload; nothing here runs rm or find
(shared/workflow/destructive-actions-catalog.md). Both directions are tested,
since a guard seen only to pass cannot be told from one that cannot fire.
"""
import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HOOK = (sys.argv[1] if len(sys.argv) > 1
        else str(Path(__file__).with_name("no-recursive-rm-unset-variable.py")))
spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

# Names the cases use as "set in an earlier Bash call": never in the hook's
# environment while a case runs.
UNSET = ("D", "BUILD_DIR", "OUT", "f", "d")


def run(command, env=None, tool="Bash"):
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": "/tmp"}
    environ = {k: v for k, v in os.environ.items() if k not in UNSET}
    environ.update({"HOME": "/home/tester", **(env or {})})
    buf = io.StringIO()
    with mock.patch.dict(os.environ, environ, clear=True), \
            mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
            redirect_stdout(buf):
        guard.main()
    out = buf.getvalue().strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


class Denies(unittest.TestCase):
    def assert_denied(self, command, **kw):
        result = run(command, **kw)
        self.assertIsNotNone(result, f"expected a deny for: {command}")
        self.assertEqual(result["permissionDecision"], "deny")
        return result["permissionDecisionReason"]

    def test_issue_cases(self):
        reason = self.assert_denied('rm -rf "$D/"')
        self.assertIn("`/`", reason)
        self.assertIn("ALLOW_RM_UNSET_VARIABLE=1", reason)
        self.assertIn("${D:?}", reason)
        self.assert_denied('rm -rf "$BUILD_DIR"/*')

    def test_flag_spellings(self):
        for flags in ("-r", "-R", "-fr", "-Rf", "--recursive", "-v -r", "-r --"):
            self.assert_denied(f'rm {flags} "$D/"')

    def test_braced_and_emptying_operators(self):
        for target in ('"${D}/"', '"${D%/}/"', '"${D:+x}/"', '"${D#a}/"', '"${D/a/b}/"'):
            self.assert_denied(f"rm -rf {target}")

    def test_set_but_empty_in_environment(self):
        self.assert_denied('rm -rf "$D/"', env={"D": ""})

    def test_prefix_assignment_is_expanded_too_late(self):
        # Bash expands the arguments before it applies `D=/x` to rm.
        self.assert_denied('D=/tmp/x rm -rf "$D/"')

    def test_assignment_after_the_delete(self):
        self.assert_denied('rm -rf "$D/"; D=/tmp/x')

    def test_wrappers(self):
        self.assert_denied('sudo rm -rf "$D/"')
        self.assert_denied('timeout 60 rm -rf "$D/"')
        self.assert_denied('if true; then rm -rf "$D/"; fi')

    def test_find(self):
        self.assert_denied('find "$D/" -delete')
        self.assert_denied('find -L "$OUT/" -name "*.o" -delete')
        self.assert_denied('find "$D/" -type f -exec rm -f {} +')
        self.assert_denied('find "$D/" -execdir /bin/rm {} ;')

    def test_nested_shell(self):
        self.assert_denied("bash -c 'rm -rf \"$D/\"'")
        self.assert_denied('sh -c "rm -rf $D/"')

    def test_quote_in_heredoc_or_comment_does_not_hide_later_delete(self):
        self.assert_denied("cat <<EOF\nit's\nEOF\nrm -rf \"$D/\"")
        self.assert_denied("echo hi # don't\nrm -rf \"$D/\"")

    def test_loop_body_runs_before_later_assignment(self):
        self.assert_denied('for x in a b; do rm -rf "$D/$x"; D=/tmp/y; done')


class Passes(unittest.TestCase):
    def assert_passes(self, command, **kw):
        self.assertIsNone(run(command, **kw), f"expected a pass for: {command}")

    def test_not_recursive_or_not_a_delete(self):
        self.assert_passes('rm -f "$D/x"')
        self.assert_passes('find "$D/" -name x')
        self.assert_passes('echo rm -rf "$D/"')
        self.assert_passes('ls "$D/"')

    def test_literal_and_set_targets(self):
        self.assert_passes("rm -rf /tmp/build")
        self.assert_passes('rm -rf "$D/"', env={"D": "/tmp/x"})
        self.assert_passes('rm -rf "$HOME/scratch"')

    def test_assigned_earlier_in_the_command(self):
        self.assert_passes('D=/tmp/x; rm -rf "$D/"')
        self.assert_passes('D=/tmp/x && rm -rf "$D/"')
        self.assert_passes('export D=/tmp/x; rm -rf "$D/"')
        self.assert_passes('d=$(mktemp -d); rm -rf "$d"')
        self.assert_passes('for d in a b; do rm -rf "$d"; done')
        self.assert_passes('while read f; do rm -rf "$f"; done < list')
        self.assert_passes('printf -v D %s /tmp/x; rm -rf "$D/"')
        self.assert_passes(': "${D:=/tmp/x}"; rm -rf "$D/"')
        self.assert_passes('D=/tmp/x; bash -c "rm -rf $D/"')

    def test_defaults_and_stops(self):
        self.assert_passes('rm -rf "${D:-/tmp/x}"')
        self.assert_passes('rm -rf "${D:?}/"')
        self.assert_passes('rm -rf "${D:?D is unset}/"')

    def test_unexpanded_dollar(self):
        self.assert_passes("rm -rf '$D/'")
        self.assert_passes('rm -rf \\$D')

    def test_substitution_and_positional(self):
        self.assert_passes('rm -rf "$(dirname "$D")/x"')
        self.assert_passes('f() { rm -rf "$1"; }')

    def test_after_source(self):
        self.assert_passes('source env.sh; rm -rf "$D/"')
        self.assert_passes('. ./env.sh && rm -rf "$D/"')

    def test_override(self):
        self.assert_passes('ALLOW_RM_UNSET_VARIABLE=1 rm -rf "$D/"')

    def test_other_tools_and_bad_input(self):
        self.assert_passes('rm -rf "$D/"', tool="Write")
        payload = io.StringIO("not json")
        buf = io.StringIO()
        with mock.patch.object(sys, "stdin", payload), redirect_stdout(buf):
            self.assertEqual(guard.main(), 0)
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])
