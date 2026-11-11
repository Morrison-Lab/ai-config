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
        self.assert_denied("/usr/bin/sudo chown -R me /etc")
        self.assert_denied("/usr/bin/env chown -R me /etc")
        self.assert_denied("pkexec chown -R me /etc")
        self.assert_denied("sudo -u root -g wheel -H -n -E -S -k -p x -C 3 chmod -R 755 /etc")
        self.assert_denied("timeout -s KILL 60 chmod -R 755 /usr")
        self.assert_denied("sudo chown -R postgres /var/lib/dpkg")
        self.assert_denied("chmod -R 755 /var/log")

    def test_bsd_chmod_options(self):
        self.assert_denied("chmod -RH 755 /usr")
        self.assert_denied("chmod -hR 755 /usr")

    def test_quoted_parenthesis_inside_a_substitution(self):
        self.assert_denied("x=$(printf ')'); chown -R me /etc")
        self.assert_denied('x=$(echo ")"); sudo chown -R me /usr')

    def test_command_after_a_heredoc_with_a_redirect(self):
        self.assert_denied("python3 - <<'EOF' 2>&1\nprint(1)\nEOF\nsudo chown -R me /usr")
        self.assert_denied("tee <<EOF out.txt\nhi\nEOF\nsudo chown -R me /usr")

    def test_assignments_are_scoped_to_their_subshell(self):
        self.assert_denied("d=/usr; (d=/tmp/x); chown -R me $d")

    def test_assigning_default(self):
        self.assert_denied('chown -R me "${PREFIX:=/usr}"')
        self.assert_denied('chown -R me "${PREFIX=/usr}"')

    def test_literal_default_is_not_a_guess(self):
        self.assert_denied('chmod -R 755 "${PREFIX:-/var}"')
        self.assert_denied('chown -R me "${DIR:-$HOME}"')
        self.assert_denied('chown -R me "${DIR:-~}"')
        self.assert_denied('chown -R me "${DIR:-${HOME}}"')

    def test_assignment_expands_home_and_unset_variables(self):
        self.assert_denied('d=~ && chmod -R 755 "$d"')
        self.assert_denied('d=$HOME && chmod -R 755 "$d"')
        self.assert_denied('d="$WORKDIR" && chmod -R 755 "$d/"')

    def test_wrapper_flag_then_value_option(self):
        self.assert_denied("sudo -E -u root chown -R me /etc")
        self.assert_denied("timeout -v 60 chmod -R 755 /usr")

    def test_bundled_wrapper_flags(self):
        self.assert_denied("sudo -Eu root chown -R me /etc")
        self.assert_denied("sudo -uroot chown -R me /etc")
        self.assert_denied("timeout -sKILL 60 chmod -R 755 /usr")
        # A lone `-h` takes the next non-option word as the host.
        self.assert_denied("sudo -h host chown -R me /etc")
        self.assert_denied("sudo -h -u root chown -R me /etc")
        # getopt_long accepts an unambiguous prefix: `--us` is `--user`.
        self.assert_denied("sudo --us root chown -R me /etc")
        self.assert_denied("sudo --u root chown -R me /etc")
        self.assert_denied("timeout --s KILL 60 chown -R me /etc")
        # An exact flag beats a longer option it prefixes (`--login-class`).
        self.assert_denied("sudo --login chown -R me /etc")
        self.assert_denied("sudo --user=root chown -R me /etc")
        self.assert_denied("sudo -- chown -R me /etc")
        self.assert_denied("nice -- chown -R me /etc")
        self.assert_denied("env --env0-from vars chown -R me /etc")
        self.assert_denied("pkexec --user root chown -R me /etc")
        self.assert_denied("pkexec -u root chown -R me /etc")
        self.assert_denied("/usr/bin/time --output log chown -R me /etc")
        self.assert_denied("env time -o log chown -R me /etc")
        self.assert_denied("exec -a x chmod -R 755 /usr")
        self.assert_denied("env -a x chown -R me /etc")
        self.assert_denied("env --argv0 x chown -R me /etc")
        # In each bundle the first value-taking letter takes the rest, `u`.
        self.assert_denied("sudo -au chown -R me /etc")
        self.assert_denied("sudo -cu chown -R me /etc")
        self.assert_denied("doas -au chown -R me /etc")
        self.assert_denied("env -Pu chown -R me /etc")

    def test_env_split_string(self):
        self.assert_denied('env -S "chown -R me /etc"')
        self.assert_denied('env -iS "chown -R me /etc"')
        self.assert_denied("env --split-string='sudo chmod -R 777 /usr'")
        self.assert_denied('env -S "sudo -u root" chown -R me /etc')

    def test_operators_other_than_a_default_are_refused(self):
        # Each rebuilds `/etc` in bash.
        self.assert_denied("chown -R me /e${HOME:+tc}")
        self.assert_denied("chown -R me /e${HOME:0:0}tc")
        self.assert_denied('chmod -R 755 "${DIR%/}/build"')

    def test_export_with_a_bare_name(self):
        self.assert_denied('export d=/etc PATH; chown -R me "$d"')

    def test_outer_assignment_inside_a_nested_shell(self):
        self.assert_denied('d=/etc; bash -c "chown -R root:root $d"')
        self.assert_denied('d=/etc; echo "$(chown -R me $d)"')

    def test_chmod_mode_bundled_with_recursive(self):
        for cmd in ("chmod -Rw /usr", "chmod -Rx /usr", "chmod -vRw /etc",
                    "chmod -R-w /usr"):
            self.assert_denied(cmd)

    def test_positional_and_special_parameters(self):
        for cmd in ('chown -R me "${1:-/etc}"', 'chmod -R 755 "$1/"',
                    'chown -R me "$@/"'):
            self.assert_denied(cmd)

    def test_long_option_prefixes(self):
        for cmd in ("chmod --recur 755 /etc", "chown --rec me /usr",
                    "chown -R --from root:root me /etc",
                    "chown -R --fr root:root me /etc"):
            self.assert_denied(cmd)

    def test_operator_on_a_computed_variable(self):
        self.assert_denied("d=$(echo x); chown -R me /e${d:+tc}")
        self.assert_denied("d=$(echo x); chown -R me /e${d:0:0}tc")

    def test_indirection_and_length(self):
        self.assert_denied('P=HOME; chown -R me "${!P}"')
        self.assert_denied('chown -R me "/${#HOME}"')

    def test_command_after_a_tab_stripped_heredoc(self):
        self.assert_denied("cat <<-EOF\n\tx\n\tEOF\nchown -R me /etc")

    def test_default_nested_three_deep(self):
        self.assert_denied('chown -R me "${A:-${B:-${HOME}}}"')

    def test_bare_brace_in_a_default_is_text(self):
        # Bash nests only on `${`: `${D:-{}usr` with D=/ is `/usr`.
        self.assert_denied('D=/; chmod -R 755 "${D:-{}usr"')
        self.assert_denied('chmod -R 755 "${HOME:-a{b}"')
        self.assert_denied("chmod -R 755 ${HOME:-x{}")

    def test_sudo_attached_host(self):
        # `-hhost` is one option; its `t` is not sudo's `-t`.
        self.assert_denied("sudo -hhost chown -R me /etc")

    def test_bsd_env_value_options(self):
        self.assert_denied("env -U root chown -R me /etc")
        self.assert_denied("env -L root chown -R me /etc")

    def test_nesting_past_the_cutoff_is_refused(self):
        for depth in (33, 100, 600):
            deep = "${A:-" * depth + "/etc" + "}" * depth
            self.assert_denied(f'chown -R me "{deep}"')
            self.assert_denied(f'X="{deep}"; chown -R me "$X"')
            # Text around the nest cannot hide the path either.
            split = "/e" + "${A:-" * depth + "tc" + "}" * depth
            self.assert_denied(f'chown -R me "{split}"')
            self.assert_denied(f'X="{split}"; chown -R me "$X"')
        # Below the cutoff the nest is expanded and judged on its value.
        shallow = "${A:-" * 30 + "./build" + "}" * 30
        self.assertIsNone(run(f'chown -R me "{shallow}"'))

    def test_deep_nesting_does_not_crash_the_hook(self):
        deep = "${A:-" * 600 + "/x" + "}" * 600
        self.assert_denied(f'X="{deep}"; chown -R me /etc')

    def test_absolute_target_inside_a_nested_shell(self):
        self.assert_denied("cd /tmp && bash -c 'chmod -R 755 /usr'")


class Allows(unittest.TestCase):
    def assert_allowed(self, command, **kw):
        self.assertIsNone(run(command, **kw), f"expected no deny for: {command}")

    def test_sudo_lone_h_takes_the_next_word_as_host(self):
        # sudo reads `chown` as the host and `-R me` as the chroot, then runs /etc.
        self.assert_allowed("sudo -h chown -R me /etc")

    def test_error_check_on_a_project_path(self):
        self.assert_allowed('chown -R me "${PROJ:?}/build"')
        self.assert_allowed('chmod -R 755 "${BUILD_DIR:?unset}/"')

    def test_operator_outside_a_recursive_call(self):
        self.assert_allowed('chmod 755 "${D%/}/x"')
        self.assert_allowed('echo "${D%/}"; chown -R me ./build')

    def test_reference_prefix_takes_the_next_word(self):
        self.assert_allowed("chmod -R --ref /etc/passwd ./build")

    def test_from_value_is_not_a_target(self):
        self.assert_allowed("chown -R --from root:root me ./build")

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

    def test_mentions_that_never_run(self):
        self.assert_allowed("git commit -m 'never run `chmod -R 755 /etc`'")
        self.assert_allowed("echo '$(chown -R me /usr)'")
        self.assert_allowed("gh issue create --body-file - <<'EOF'\n"
                            "The agent ran `sudo chown -R me /usr` and broke sudo.\n"
                            "EOF")
        self.assert_allowed("ls # see `chown -R me /etc`")

    def test_partial_glob_is_not_its_directory(self):
        self.assert_allowed("chmod -R u+w /tmp/build-*")
        self.assert_allowed("chmod -R 755 ~/proj*")

    def test_nested_shell_and_subshell_directories(self):
        self.assert_allowed("cd proj && bash -c 'chmod -R u+w .'", cwd=HOME)
        self.assert_allowed("(cd / && ls); chmod -R 755 build", cwd="/srv/app")

    def test_application_and_container_directories(self):
        self.assert_allowed("sudo chown -R postgres /var/lib/postgresql/data")
        self.assert_allowed("sudo chown -R me /var/log/myapp")
        self.assert_allowed("chmod -R u+w .", cwd="/app")

    def test_program_run_by_another_program_under_sudo(self):
        self.assert_allowed("sudo docker run --rm -v /srv/x:/work alpine chown -R 1000:1000 /work")

    def test_reference_file_is_not_a_target(self):
        self.assert_allowed("chmod -R --reference /etc/hosts mydir")

    def test_pwd_after_an_unknown_cd(self):
        self.assert_allowed('cd "$BUILD" && chmod -R 755 "$PWD/dist"')

    def test_variable_set_in_the_environment_keeps_its_value(self):
        env = {"VIRTUAL_ENV": "/home/tester/p/.venv"}
        self.assert_allowed('chmod -R +x "$VIRTUAL_ENV/bin"', env=env)

    def test_subshell_assignment_does_not_leak(self):
        self.assert_allowed('d=/tmp/x; (d=/usr; echo $d); chown -R me "$d"')

    def test_wrapper_flag_does_not_swallow_the_program(self):
        self.assert_allowed("sudo -E echo chown -R me /usr")
        self.assert_allowed("sudo -n git log -S chmod -R /etc")
        self.assert_allowed("env -i myapp chmod -R 755 /usr")

    def test_attached_wrapper_value_then_another_program(self):
        self.assert_allowed("sudo -uroot echo chown -R me /usr")
        self.assert_allowed("sudo -Eu root echo chown -R me /usr")

    def test_env_split_string_runs_another_program(self):
        self.assert_allowed('env -S "echo chown -R me /etc"')
        self.assert_allowed('env -S "chown -R me build"')

    def test_unclosed_brace_is_left_as_written(self):
        self.assert_allowed('chmod -R 755 "build/${A:-x"')

    def test_declare_with_flags(self):
        self.assert_allowed('declare -x OUT=/tmp/build && chmod -R 755 "$OUT/"')

    def test_malformed_cwd(self):
        self.assertIsNone(run("chmod -R 755 build", cwd=["/"]))

    def test_unset_variable_below_root(self):
        # `$WORKDIR/build` with WORKDIR unset is `/build`: not a reason to refuse.
        self.assert_allowed('chmod -R 755 "$WORKDIR/build"')
        self.assert_allowed('chmod -R 755 "${WORKDIR}/dist"')
        # `${PWD}` is the working directory, so this is `<cwd>/dist`.
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
