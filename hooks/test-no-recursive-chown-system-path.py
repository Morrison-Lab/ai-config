#!/usr/bin/env python3
"""Tests for no-recursive-chown-system-path.py.

Every case feeds the hook a payload; nothing here runs chown or chmod
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
        else str(Path(__file__).with_name("no-recursive-chown-system-path.py")))
spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

HOME = "/home/tester"
REPO = "/home/tester/GitHub/lds"


def run(command, cwd=REPO, env=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    buf = io.StringIO()
    environ = {"HOME": HOME, **(env or {})}
    with mock.patch.dict(os.environ, environ, clear=False), \
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

    def test_claude_code_168(self):
        reason = self.assert_denied(
            "sudo chown -R $USER:$(id -gn) /usr && sudo chmod -R u+w /usr")
        self.assertIn("/usr", reason)
        self.assertIn("ALLOW_RECURSIVE_SYSTEM_CHOWN=1", reason)

    def test_claude_code_39283_repair(self):
        self.assert_denied("chown -R root:root /usr/")
        self.assert_denied("chown -R root:root /etc/")

    def test_root_and_top_level(self):
        for target in ("/", "/*", "/home", "/mnt", "/opt"):
            self.assert_denied(f"chmod -R 755 {target}")

    def test_inside_system_tree(self):
        self.assert_denied("chmod -R 777 /usr/local/bin")
        self.assert_denied("chgrp -R staff /var/lib/dpkg")

    def test_home_and_its_parent(self):
        for target in ("~", "~/", "$HOME", "${HOME}/", HOME, "/home/tester/*"):
            self.assert_denied(f"chmod -R go-rwx {target}")

    def test_relative_paths_resolve(self):
        self.assert_denied("chmod -R 700 .", cwd=HOME)
        self.assert_denied("chown -R me ../..", cwd=REPO)
        self.assert_denied("cd / && chmod -R 755 usr")

    def test_flag_spellings(self):
        self.assert_denied("chmod --recursive 755 /etc")
        self.assert_denied("chown -hR me /etc")
        self.assert_denied("chown -R --reference=/tmp/x /etc")

    def test_wrappers_and_shells(self):
        self.assert_denied("sudo -u root chown -R me /etc")
        self.assert_denied("timeout 60 chmod -R 755 /usr")
        self.assert_denied("bash -c 'chmod -R 755 /etc'")
        self.assert_denied("/bin/chown -R me /etc")

    def test_variable_from_an_earlier_call(self):
        # #75859: a variable an earlier Bash call set is empty in this one.
        self.assert_denied('chmod -R 755 "$WORKDIR/"')
        self.assert_denied('chown -R me "$WORKDIR"/*')

    def test_variable_set_to_a_system_path(self):
        self.assert_denied('chown -R me "$PREFIX"', env={"PREFIX": "/usr"})
        self.assert_denied('d=/etc; chown -R me "$d"')
        self.assert_denied('chown -R me "${PREFIX:-/usr}"')

    def test_command_substitution_unquoted(self):
        self.assert_denied("sudo chown -R $USER:$(id -gn) /usr")
        self.assert_denied("chown -R `whoami` /etc")
        self.assert_denied("echo $(chown -R me /etc)")

    def test_chmod_mode_that_looks_like_an_option(self):
        self.assert_denied("chmod -R -w /usr")
        self.assert_denied("chmod -R -x /etc")

    def test_more_system_trees_and_wrappers(self):
        self.assert_denied("chown -R me /var/log")
        self.assert_denied("chown -R me ~root")
        self.assert_denied("sudo -u root -g wheel -H -n -E chown -R me /etc")
        self.assert_denied("setsid chmod -R 755 /usr")
        self.assert_denied("chmod -R 755 /usr/local")
        self.assert_denied("chmod -R 755 /usr/local/lib")


class Allows(unittest.TestCase):
    def assert_allowed(self, command, **kw):
        self.assertIsNone(run(command, **kw), f"expected no deny for: {command}")

    def test_project_paths(self):
        self.assert_allowed("chmod -R u+w .")
        self.assert_allowed("chmod -R 755 hooks/")
        self.assert_allowed("chown -R me ~/GitHub/lds")
        self.assert_allowed("chmod -R 700 ~/.ssh")
        self.assert_allowed("sudo chown -R me /opt/homebrew")

    def test_not_recursive(self):
        self.assert_allowed("chmod 755 /usr/local/bin/tool")
        self.assert_allowed("chmod +x ~")
        self.assert_allowed("chmod -w /etc/hosts")

    def test_other_programs_and_mentions(self):
        self.assert_allowed("echo chown -R me /usr")
        self.assert_allowed("git commit -m 'never chmod -R 755 /etc'")
        self.assert_allowed("ls -R /usr")
        self.assert_allowed("grep -R chown /etc")

    def test_variable_set_in_the_same_command(self):
        self.assert_allowed('d=$(mktemp -d) && chmod -R 755 "$d/"')
        self.assert_allowed('export OUT=build; chmod -R 755 "$OUT"')

    def test_unset_variable_below_root(self):
        # `$OUT/dist` with OUT unset is `/dist`: not a reason to refuse.
        self.assert_allowed('chmod -R 755 "$WORKDIR/build"')
        self.assert_allowed('chmod -R 755 "${PWD}/dist"')

    def test_user_managed_usr_local(self):
        self.assert_allowed("sudo chown -R me /usr/local/lib/node_modules")
        self.assert_allowed("sudo chown -R me /usr/local/Cellar")

    def test_non_string_command(self):
        buf = io.StringIO()
        payload = {"tool_name": "Bash", "tool_input": {"command": ["chown", "-R", "/usr"]}}
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                redirect_stdout(buf):
            guard.main()
        self.assertEqual(buf.getvalue(), "")

    def test_empty_operand(self):
        self.assert_allowed('chmod -R 755 "$UNSET_DIR"')

    def test_override(self):
        self.assert_allowed("ALLOW_RECURSIVE_SYSTEM_CHOWN=1 chown -R me /usr/local/share")

    def test_override_mention_is_not_an_override(self):
        self.assertIsNotNone(run("echo ALLOW_RECURSIVE_SYSTEM_CHOWN=1; chown -R me /usr"))

    def test_non_bash_tool_and_bad_input(self):
        buf = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("not json")), redirect_stdout(buf):
            guard.main()
        self.assertEqual(buf.getvalue(), "")
        payload = {"tool_name": "Write", "tool_input": {"command": "chown -R me /usr"}}
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                redirect_stdout(buf):
            guard.main()
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])
