#!/usr/bin/env python3
"""Tests for no-recursive-rm-unset-variable.py, in both directions. Every case
feeds the hook a payload; nothing here runs rm or find."""
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

UNSET = ("D", "BUILD_DIR", "OUT", "f", "d")  # "set in an earlier Bash call"

# Flags, emptying operators, late assignments, wrappers, find, sh -c, stray quotes.
DENIED = [
    'rm -rf "$BUILD_DIR"/*', 'rm -r "$D/"', 'rm -R "$D/"', 'rm -fr "$D/"',
    'rm --recursive "$D/"', 'rm -v -r "$D/"', 'rm -r -- "$D/"', 'rm -rf "${D}/"',
    'rm -rf "${D%/}/"', 'rm -rf "${D:+x}/"', 'rm -rf "${D/a/b}/"',
    'D=/tmp/x rm -rf "$D/"', 'rm -rf "$D/"; D=/tmp/x',
    'for x in a b; do rm -rf "$D/$x"; D=/tmp/y; done', 'sudo rm -rf "$D/"',
    'timeout 60 rm -rf "$D/"', 'if true; then rm -rf "$D/"; fi', 'find "$D/" -delete',
    'find -L "$OUT/" -name "*.o" -delete', 'find "$D/" -type f -exec rm -f {} +',
    'find "$D/" -execdir /bin/rm {} ;', "bash -c 'rm -rf \"$D/\"'", 'sh -c "rm -rf $D/"',
    "cat <<EOF\nit's\nEOF\nrm -rf \"$D/\"", "echo hi # don't\nrm -rf \"$D/\"",
]
# Not a recursive delete, set targets, earlier assignments, `:-`/`:?`, unexpanded `$`.
PASSED = [
    'rm -f "$D/x"', 'find "$D/" -name x', 'echo rm -rf "$D/"', 'ls "$D/"',
    "rm -rf /tmp/build", 'rm -rf "$HOME/scratch"', 'D=/tmp/x; rm -rf "$D/"',
    'D=/tmp/x && rm -rf "$D/"', 'export D=/tmp/x; rm -rf "$D/"',
    'd=$(mktemp -d); rm -rf "$d"', 'for d in a b; do rm -rf "$d"; done',
    'while read f; do rm -rf "$f"; done < list', 'printf -v D %s /tmp/x; rm -rf "$D/"',
    ': "${D:=/tmp/x}"; rm -rf "$D/"', 'D=/tmp/x; bash -c "rm -rf $D/"',
    'rm -rf "${D:-/tmp/x}"', 'rm -rf "${D:?}/"', 'rm -rf "${D:?D is unset}/"',
    "rm -rf '$D/'", 'rm -rf \\$D', 'rm -rf "$(dirname "$D")/x"', 'f() { rm -rf "$1"; }',
    'source env.sh; rm -rf "$D/"', '. ./env.sh && rm -rf "$D/"',
    'ALLOW_RM_UNSET_VARIABLE=1 rm -rf "$D/"',
]


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


class Guard(unittest.TestCase):
    def test_issue_case_and_message(self):
        result = run('rm -rf "$D/"')
        self.assertEqual(result["permissionDecision"], "deny")
        for text in ("`$D`", "`$D/`", "${D:?}", "ALLOW_RM_UNSET_VARIABLE=1", "#75859"):
            self.assertIn(text, result["permissionDecisionReason"])

    def test_denied_and_passed(self):
        for command, denied in [(c, True) for c in DENIED] + [(c, False) for c in PASSED]:
            with self.subTest(command=command, expect_deny=denied):
                self.assertEqual(run(command) is not None, denied)

    def test_environment_value(self):
        self.assertIsNotNone(run('rm -rf "$D/"', env={"D": ""}))
        self.assertIsNone(run('rm -rf "$D/"', env={"D": "/tmp/x"}))

    def test_other_tools_and_bad_input(self):
        self.assertIsNone(run('rm -rf "$D/"', tool="Write"))
        buf = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("not json")), redirect_stdout(buf):
            self.assertEqual(guard.main(), 0)
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])
