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
import time
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
        # Under a harmless prefix, so only the operator rule can deny them.
        self.assert_denied('P=HOME; chown -R me "./${!P}"')
        self.assert_denied('chown -R me "/tmp/${#HOME}"')

    def test_positional_parameters_set_in_the_command(self):
        for cmd in ("bash -c 'chown -R root \"$1\"' _ /etc",
                    'set -- /etc; chown -R me "$1"',
                    'f(){ chown -R me "$1"; }; f /etc',
                    'chown -R me "./$1"'):
            self.assert_denied(cmd)

    def test_colonless_forms_on_a_set_but_empty_variable(self):
        for cmd in ('D=; chown -R me "${D?}/"', 'export D=; chown -R me "${D?}/"',
                    'D=; chown -R me "/${D?}etc"', 'D=; chown -R me "${D-x}/"',
                    'D=; chown -R me "${D=x}/"'):
            self.assert_denied(cmd)

    def test_assigning_default_as_a_side_effect(self):
        self.assert_denied(': "${D:=/etc}"; chown -R me "$D"')
        self.assert_denied('echo "${D=/usr}" && chmod -R 755 "$D"')

    def test_background_pid_may_be_empty(self):
        self.assert_denied('chown -R me "$HOME/$!"')

    def test_dollar_zero_set_by_a_nested_shell(self):
        self.assert_denied("bash -c 'chown -R root \"$0\"' /etc")
        self.assert_denied("sh -c 'chown -R root \"${0}/\"' /")

    def test_assigning_default_flows_into_later_uses(self):
        for cmd in (': "${PREFIX:=/usr}"; DEST="$PREFIX/share"; chown -R me "$DEST"',
                    ': "${D:=/etc}"; E="$D"; chown -R me "$E"',
                    ': "${D:=/etc}"; sudo sh -c "chown -R root $D"',
                    ': "${D:=/usr}"; echo $(chown -R me "$D")'):
            self.assert_denied(cmd)

    def test_read_after_an_assignment_or_keyword(self):
        for cmd in ('IFS= read -r D <<< /etc; chown -R me "$D"',
                    'while read -r D; do chown -R me "$D"; done <<< /etc',
                    'find / -maxdepth 1 | while IFS= read -r d; do chown -R me "$d"; done'):
            self.assert_denied(cmd)

    def test_assignment_after_a_shell_keyword(self):
        for cmd in ('if [ -z "$PREFIX" ]; then PREFIX=/usr/local; fi; chown -R me "$PREFIX"',
                    '{ D=/etc; }; chown -R me "$D"',
                    'for x in a; do D=/usr; done; chown -R me "$D"',
                    'if true; then export D=/etc; fi; chown -R me "$D"'):
            self.assert_denied(cmd)

    def test_names_set_by_read_and_printf_forms(self):
        for cmd in ('command read -r D <<< /etc; chown -R me "$D"',
                    'read < f; chown -R me "$REPLY"',
                    'mapfile < f; chown -R me "$MAPFILE"',
                    'IFS= printf -v D %s /etc; chown -R me "$D"',
                    'printf -vD %s /etc; chown -R me "$D"',
                    'printf -v A -v D %s /etc; chown -R me "$D"'):
            self.assert_denied(cmd)

    def test_cd_after_a_shell_keyword(self):
        for cmd in ("if cd /etc; then chown -R me .; fi",
                    "if true; then cd /etc; chown -R me .; fi",
                    "{ cd /usr; }; chown -R me .",
                    "for d in a; do cd /usr/lib; done; chown -R me .",
                    "if true; then pushd /etc; fi; chown -R me ."):
            self.assert_denied(cmd)

    def test_cd_that_may_not_run_keeps_the_directory_before(self):
        for cmd in ("cd /etc; if [ -d ~/proj ]; then cd ~/proj; fi; chown -R me .",
                    "cd /usr/lib; if [ -d build ]; then cd ~/proj; fi; chmod -R u+w .",
                    "cd /etc; while false; do cd ~/proj; done; chown -R me .",
                    "cd /etc; if [ -d x ]; then echo; cd ~/proj; fi; chown -R me .",
                    "cd /etc; case $x in a) cd ~/proj;; esac; chown -R me ."):
            self.assert_denied(cmd)

    def test_pwd_after_a_cd_that_may_not_run(self):
        cwd = HOME
        for cmd in ('if [ -d proj ]; then cd proj; fi; chown -R me "$PWD"',
                    'if [ -d proj ]; then cd proj; fi; X=$PWD; chmod -R u+w "$X"',
                    'if [ -d proj ]; then cd proj; fi; ROOT=$PWD OUT=$ROOT; chown -R me "$OUT"',
                    'if [ -d proj ]; then cd proj; fi; : "${ROOT:=$PWD}"; chown -R me "$ROOT"'):
            self.assert_denied(cmd, cwd=cwd)

    def test_relative_pwd_value_after_a_cd_that_may_not_run(self):
        self.assert_denied('if [ -d proj ]; then cd proj; fi; D="./$PWD/../.."; cd /tmp; '
                           'chown -R me "$D"', cwd=HOME)

    def test_nested_text_after_a_maybe_cd_sees_every_world(self):
        cwd = HOME + "/proj"
        self.assert_denied('if [ -d sub ]; then cd sub; fi; X=$PWD; bash -c "chmod -R u+w $X/.."',
                           cwd=cwd)
        self.assert_denied('if [ -d sub ]; then cd sub; fi; X=$PWD; Y=$(chown -R me "$X/..")',
                           cwd=cwd)

    def test_cd_up_in_a_loop_reaches_every_ancestor(self):
        self.assert_denied('while [ ! -d .git ] && [ "$PWD" != / ]; do cd ..; done; '
                           'chmod -R u+w .')
        self.assert_denied("until [ -d .git ]; do cd ../..; done; chown -R me .")
        self.assert_denied("until cd ..; do :; done; chmod -R u+w .", cwd=HOME + "/a/b")
        for cmd in ('while [ ! -d .git ]; do cd "$PWD/.."; done; chmod -R u+w .',
                    "while [ ! -d .git ]; do cd ./..; done; chmod -R u+w ."):
            self.assert_denied(cmd, cwd=HOME + "/a/b")
        # Outside home, only reaching / is protected; deep, past the budget.
        self.assert_denied("while [ ! -d .git ]; do cd ..; done; chmod -R u+w .", cwd="/app/x")
        self.assert_denied("while [ ! -d .git ]; do cd ..; done; chmod -R u+w .",
                           cwd="/app/" + "/".join("abcdefghijklmnopqrst"))

    def test_cd_to_an_unset_variable_may_go_home(self):
        for cmd in ('cd $UNSET_D && chmod -R u+w "$PWD"', "cd $UNSET_D && chmod -R u+w ."):
            self.assert_denied(cmd, cwd=HOME + "/proj")
        # From home, either way it stays home.
        self.assert_denied('cd "$UNSET_D"; X=$PWD; chown -R me "$X"', cwd=HOME)
        # Options before the operand, and a name set empty, go home too.
        for cmd in ("cd -P $UNSET_D && chown -R me .", "cd -- $UNSET_D && chown -R me .",
                    "D=; cd $D && chown -R me ."):
            self.assert_denied(cmd, cwd=HOME + "/proj")

    def test_cd_to_an_unset_variable_then_slash_is_root(self):
        self.assert_denied('cd "$UNSET_D/" && chown -R me .', cwd=HOME + "/proj")

    def test_cd_to_an_unset_variable_unquoted_in_other_spellings(self):
        for cmd in ("cd $UNSET_D>/dev/null; chown -R me .", "(cd $UNSET_D && chown -R me .)",
                    "cd -eP $UNSET_D; chown -R me .", "cd -LPe $UNSET_D; chown -R me ."):
            self.assert_denied(cmd, cwd=HOME + "/proj")

    def test_cd_to_an_unset_variable_then_dot_stays_weakly(self):
        self.assert_denied('cd "${OUT}." && chown -R me .', cwd=HOME)
        self.assert_denied('cd "$HOME/$PROJECT" && chmod -R u+w .', cwd=HOME)
        self.assert_denied('cd "$OUT/tmp" && chown -R me ..', cwd="/tmp")

    def test_cd_under_an_unset_variable_that_may_not_run(self):
        # Where the `cd` did not run, the shell is still in the project.
        for cmd in ('if [ -n "$X" ]; then cd "$OUT/a/b/c"; fi; chown -R me ..',
                    'while read -r f; do cd "$OUT/a/b"; done; chmod -R u+w ..'):
            self.assert_denied(cmd, cwd=HOME + "/proj")

    def test_hash_inside_a_word_is_not_a_comment(self):
        for cmd in ("curl -fsSL https://x.org/i.sh#v2 -o i.sh && sudo chmod -R 755 /usr/local",
                    "sed -i s#foo#bar#g conf && sudo chown -R root:root /usr",
                    "echo ${#A} $#; chmod -R u+w /etc",
                    "open https://x.org/b/$(git rev-parse HEAD)#L10 && sudo chmod -R 755 /usr",
                    "echo $(echo x)#y; chmod -R u+w /etc",
                    "echo a\\ #b; chmod -R u+w /etc",
                    "echo \\ #b; chmod -R u+w /etc"):
            self.assert_denied(cmd)

    def test_absolute_cd_from_an_unknown_directory(self):
        for lead in ('cd "$(git rev-parse --show-toplevel)" && make && ', "cd - && ",
                     "".join(f"if t{i}; then cd d{i}; fi; " for i in range(20))):
            self.assert_denied(lead + "cd /usr/local && sudo chown -R me .")
        self.assert_denied("cd - && cd ~ && chmod -R go-w .")
        for cmd in ("cd - && cd $UNSET_D && chmod -R go-w .",
                    'cd - && cd "$UNSET_D/etc" && chmod -R u+w .',
                    'cd "$(git rev-parse --show-toplevel)" && cd "$UNSET_P/lib" && chmod -R u+w .',
                    'cd - && cd "$UNSET_D"/usr && sudo chown -R me .',
                    "diff <(ls)#x; chmod -R u+w /etc",
                    "a=(x y)#z; chmod -R u+w /etc"):
            self.assert_denied(cmd)
        self.assert_denied("".join(f"cd {'n' * 250}{i}; " for i in range(17))
                           + "cd /; chmod -R u+w .")

    def test_deep_subshells_are_read(self):
        self.assert_denied("( " * 200 + "D=x; chmod -R u+w /etc" + " )" * 200)
        self.assert_denied("( " * 200 + "cd /; chmod -R u+w ." + " )" * 200)

    def test_absolute_cd_leaves_a_weak_directory(self):
        self.assert_denied('cd "$OUT/x"; cd /; chmod -R u+w opt', cwd=HOME + "/proj")

    def test_weak_flag_is_out_of_reach_of_names(self):
        self.assert_denied('cd x; chmod -R u+w "$__AICFG_WEAK_PWD__/etc"')
        self.assert_denied('cd x; chmod -R u+w "${weak PWD}/etc"')

    def test_climb_from_a_directory_under_an_unset_variable(self):
        # With OUT unset, `cd "$OUT/tmp"` is `cd /tmp`, and `..` is `/`.
        for cmd in ('cd "$OUT/tmp" && chown -R me ..',
                    'cd "$OUT/var/lib/myapp" && chown -R me ..',
                    'cd "$OUT/x" && cd sub && chmod -R u+w ../..'):
            self.assert_denied(cmd, cwd=HOME + "/proj")

    def test_names_survive_past_the_work_budget(self):
        forks = "".join(f"if t{i}; then cd d{i}; fi; " for i in range(4))
        files = " ".join(f"f{i}" for i in range(guard.MAX_WORK // 8))
        for tail in ('sh -c "chown -R me $D"', 'X=$(chown -R me "$D")'):
            # `a=b` keeps the `ls` from being skipped, so it spends the budget.
            self.assert_denied(f"{forks}D=/etc; ls a=b {files}; {tail}", cwd=HOME + "/proj")

    def test_nested_texts_at_each_depth(self):
        for cmd in ('X=$(sh -c "chown -R me /etc")',
                    "echo $(echo $(chown -R me /etc))",
                    "sudo sh -c \"bash -c 'chown -R me /etc'\"",
                    "sh -c 'echo $(echo $(echo $(chown -R me /etc)))'"):
            self.assert_denied(cmd)

    def test_nested_texts_past_max_nested_are_read_with_no_directory(self):
        deep = "chown -R me /etc"
        for _ in range(guard.MAX_NESTED + 2):
            deep = f"echo $({deep})"
        self.assert_denied(deep)

    def test_pwd_name_used_with_a_suffix(self):
        for cmd in ('if [ -d sub ]; then cd sub; fi; X=$PWD; chown -R me "$X/.."',
                    'if [ -d sub ]; then cd sub; fi; X=$PWD; chown -R me "$X"/../'):
            self.assert_denied(cmd, cwd=HOME + "/proj")

    def test_shell_c_runs_in_the_callers_directory(self):
        for cmd in ('sudo sh -c "chown -R me $PWD"', 'sudo sh -c "chown -R me ."',
                    "sudo sh -c 'chown -R me .'"):
            self.assert_denied(cmd, cwd=HOME)
        self.assert_denied("if a; then cd /; fi; if b; then cd y; fi; chown -R me .")
        # A `cd` after the nested text, or in another subshell, does not move it.
        for cmd in ("sh -c 'chown -R me .'; cd /tmp", 'echo "$(chown -R me .)"; cd /tmp',
                    "(cd /tmp && ls); sh -c 'chown -R me .'",
                    "(cd /tmp && ls -c); sh -c 'chown -R me .'",
                    "(cd /tmp && echo $(true)); sh -c 'chown -R me .'",
                    "cd proj; cd ..; sh -c 'chown -R me .'",
                    "OUT=$(sudo chmod -R u+w . 2>&1); cd build; tar -czf a.tgz .",
                    "X=$(chmod -R u+w .); cd /tmp; Y=$(date)",
                    "sh -c 'cd /tmp; ls $(echo)'; sh -c 'chown -R me .'"):
            self.assert_denied(cmd, cwd=HOME)

    def test_indirection_with_a_check(self):
        for cmd in ('chown -R me "${!?}"', 'chown -R me "${#?}"', 'chown -R me "/${#-}"'):
            self.assert_denied(cmd)

    def test_nested_text_in_a_later_world(self):
        self.assert_denied('if [ -d sub ]; then cd ..; fi; X=$PWD; bash -c "chmod -R u+w $X"',
                           cwd=HOME + "/proj")

    def test_refusal_quotes_pwd_substitution_as_written(self):
        reason = run('sudo chown -R "$USER" "$(pwd)"', cwd=HOME)["permissionDecisionReason"]
        self.assertIn("$(pwd)", reason)
        self.assertNotIn("${PWD}", reason)

    def test_current_directory_named_another_way(self):
        for cmd in ('sudo chown -R "$USER" "$(pwd)"', 'X=$(pwd -P); chown -R me "$X"',
                    "chown -R me `pwd`", "chown -R me ~+"):
            self.assert_denied(cmd, cwd=HOME)

    def test_cd_behind_time_or_command(self):
        for cmd in ("time cd /etc; chown -R me .", "command cd /etc; chown -R me .",
                    "builtin cd /etc; chown -R me ."):
            self.assert_denied(cmd)

    def test_names_set_by_getopts_and_time_read(self):
        self.assert_denied('set -- -d /etc; getopts d: o; chown -R me "$OPTARG"')
        self.assert_denied('time read -r D <<< /etc; chown -R me "$D"')

    def test_literal_root_gives_the_root_reason(self):
        reason = self.assert_denied("chown -R root /")
        self.assertIn("the filesystem root", reason)

    def test_assignment_in_a_cd_word(self):
        self.assert_denied('cd "${D:=/etc}" && chown -R me "$D"')

    def test_names_set_by_builtins(self):
        for cmd in ('printf -v D %s /etc; chown -R me "$D"',
                    'read D <<< /etc; chown -R me "$D"',
                    'echo /etc; chown -R me "$_"',
                    'cd /etc && cd /tmp && chown -R me "$OLDPWD"'):
            self.assert_denied(cmd)

    def test_command_after_a_tab_stripped_heredoc(self):
        self.assert_denied("cat <<-EOF\n\tx\n\tEOF\nchown -R me /etc")

    def test_reference_value_attached_to_a_prefix(self):
        self.assert_denied("chmod -R --ref=x /etc")

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
        # The owner names the home directory's basename, from its parent.
        self.assert_allowed("chown -R --from root:root tester ./build", cwd="/home")

    def test_special_parameters_are_not_empty(self):
        for cmd in ('chmod -R 700 "$HOME/$$"', "chmod -R 700 ~/$$",
                    'chown -R me "${HOME}/${#}"'):
            self.assert_allowed(cmd)

    def test_assignment_after_a_shell_keyword_then_a_trailing_slash(self):
        self.assert_allowed('if true; then D=./build; fi; chown -R me "$D/"')
        # After `--`, `-v x` is the format and its argument: x keeps its value.
        self.assert_allowed('x=./build; printf -- -v x; chown -R me "$x"')

    def test_cd_in_a_condition_or_group_is_read_as_run(self):
        # The `{ ... }` case pins a Limit: a `cd` that fails (no ~/proj) is
        # read as run, so this chowns $HOME then and is still allowed.
        for cmd in ("if cd ~/proj; then chown -R me .; fi",
                    "{ cd ~/proj; }; chown -R me .",
                    "while ! cd ~/proj; do sleep 1; done; chown -R me ."):
            self.assert_allowed(cmd, cwd=HOME)

    def test_cd_after_an_if_with_elif(self):
        self.assert_allowed("if [ -d a ]; then echo a; elif [ -d b ]; then echo b; fi; "
                            "cd ~/proj; chmod -R u+w .", cwd=HOME)

    def test_pwd_assignment_after_a_cd_that_may_not_run(self):
        self.assert_allowed('if [ -d build ]; then cd build; fi; BUILD_DIR="$PWD/out"; '
                            'chmod -R u+w "$BUILD_DIR"')
        self.assert_allowed("if [ -d build ]; then cd build; fi; PWD_OK=1 chmod -R u+w ./dist")
        self.assert_allowed('if [ -d build ]; then cd build; fi; X=$PWD; chmod -R u+w "$X"')
        self.assert_allowed('if [ -d build ]; then cd build; fi; MYPWD=./x; chmod -R u+w "$MYPWD"')
        self.assert_allowed("bash -c 'd=$PWD/build; chmod -R u+w \"$d\"'")

    def test_getopts_option_string_is_not_a_name(self):
        self.assert_allowed('d=./build; while getopts d o; do :; done; chmod -R 755 "$d"')

    def test_below_the_current_directory(self):
        # From $HOME, so reading these as the current directory itself would deny.
        for cmd in ('chmod -R u+w "$(pwd)/build"', "chmod -R u+w ~+/build",
                    'chown -R me "$(pwd; echo)"'):
            self.assert_allowed(cmd, cwd=HOME)

    def test_pwd_after_a_cd_this_cannot_resolve(self):
        # Limit pins: `$PWD` there is read like `.` there, taken as empty.
        for cmd in ('cd -; X=$PWD; chown -R me "$X"', 'cd -; chown -R me "$PWD"',
                    'cd "$(git rev-parse --show-toplevel)" && chmod -R u+w "$PWD"',
                    'cd "$(git rev-parse --show-toplevel)" && chmod -R u+w "$PWD/build"'):
            self.assert_allowed(cmd, cwd=HOME)
        self.assert_allowed("cd build && bash -c 'chmod -R u+w \"$PWD\"'")

    def test_past_max_worlds_the_directory_is_unknown(self):
        # Four guarded cds make 16 ways to run; the fifth leaves the directory
        # unknown (a Limit pin: in bash `..` there may be /tmp).
        guarded = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        self.assert_allowed(guarded + "if e; then cd /tmp/a; fi; chown -R me ..")
        # Under the cap, the same `cd` is judged both ways, and `..` is /tmp.
        self.assertIsNotNone(run(guarded[len("if a; then cd a; fi; "):]
                                 + "if e; then cd /tmp/a; fi; chown -R me .."))

    def test_deeply_nested_command_is_read_quickly(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        level3 = [guards + f"echo $(ls {n}a) $(ls {n}b); ls {n}" for n in range(16)]
        level2 = [guards + " ".join(f'echo "$({x})"' for x in level3[4 * i:4 * i + 4])
                  for i in range(4)]
        command = guards + " ".join(f'echo "$({x})"' for x in level2)
        start = time.monotonic()
        self.assert_allowed(command + "; chmod -R u+w ./x")
        self.assertLess(time.monotonic() - start, 5)

    def test_shell_c_in_a_project(self):
        self.assert_allowed("sudo sh -c 'chown -R me .'")
        self.assert_allowed("cd build && sh -c 'chmod -R u+w .'")
        self.assert_allowed("if a; then cd x; fi; if b; then cd y; fi; if c; then cd z; fi; "
                            "chmod -R u+w ./q")

    def test_guarded_cd_into_the_project(self):
        self.assert_allowed("if [ -d build ]; then cd build; fi; chmod -R u+w .")
        self.assert_allowed("cd ~/proj; if [ -d out ]; then cd out; fi; chown -R me .")

    def test_assigning_default_then_a_trailing_slash(self):
        self.assert_allowed(': "${D:=./build}"; chown -R me "${D:-./out}"')
        self.assert_allowed(': "${OUT:=./dist}"; chmod -R a+rX "$OUT/"')
        self.assert_allowed(': "${D:=build}"; chmod -R u+w "$D"/*')

    def test_colonless_default_on_a_set_variable(self):
        self.assert_allowed('D=./build; chown -R me "${D-/etc}"')
        self.assert_allowed(': "${D:=./build}"; chown -R me "$D"')

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

    def test_cd_to_a_loop_variable_or_set_name_stays_in_the_project(self):
        for cmd in ('for d in */; do (cd "$d" && chmod -R u+w .); done',
                    'for d in */; do cd "$d"; chmod -R u+w .; cd ..; done',
                    'cd "$PROJECT_ROOT" && chmod -R u+w .',
                    'cd "$OUT/build" && chmod -R u+w .',
                    "for d in */; do cd $d; chmod -R u+w .; cd ..; done",
                    'cd "$WORKDIR" && chmod -R u+w . && echo done in $WORKDIR'):
            self.assert_allowed(cmd, cwd=HOME + "/work/lds")

    def test_directory_under_an_unset_variable_is_judged_weakly(self):
        # With OUT set, the `cd` goes somewhere this cannot name, so home and
        # a top-level name reached through an empty value are no reason to refuse.
        for cmd in ('cd "$OUT/build" && chmod -R u+w .', 'cd "$OUT/opt" && chmod -R u+w .',
                    'cd "$OUT/build" && chmod -R u+w "$PWD"'):
            self.assert_allowed(cmd, cwd=HOME)
        # `$PWD` and a relative `cd` there stay weak.
        for cmd in ('cd "$OUT/opt" && chmod -R u+w "$PWD"',
                    'cd "$OUT/x" && cd .. && chmod -R u+w ./opt',
                    'if [ -n "$X" ]; then cd "$OUT/build"; fi; chmod -R u+w .',
                    # Where the second `cd` did not run, `/opt` is still weak.
                    f'cd "$OUT/opt"; if t; then cd {HOME}/proj; fi; chmod -R u+w .'):
            self.assert_allowed(cmd, cwd=HOME + "/proj")

    def test_cd_in_a_comment_is_not_a_cd(self):
        self.assert_allowed('echo x # cd $D\ncd "$D"; chmod -R u+w .', cwd=HOME + "/proj")

    def count_calls(self, name, command):
        real, calls = getattr(guard, name), []

        def counted(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        with mock.patch.object(guard, name, counted):
            guard._hit(command, REPO, HOME)
        return len(calls)

    def test_text_without_a_program_name_is_not_parsed(self):
        self.assertEqual(self.count_calls("_split", "ls; echo 'ch' own; cd /usr"), 0)

    def test_nested_text_is_parsed_once(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        self.assertEqual(self.count_calls("_split", guards + 'sh -c "chmod -R u+w ./x"'), 2)

    def test_only_words_with_a_default_are_expanded_for_one(self):
        # `a=b` keeps the `echo` from being skipped as changing nothing.
        command = "echo a=b " + " ".join(f"w{i}" for i in range(500)) + "; chmod -R u+w ./x"
        self.assertLess(self.count_calls("_expand", command), 50)

    def test_past_the_work_budget_the_rest_is_read_once(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        command = guards + "echo ${A}; " * 5000 + "chmod -R u+w ./x"
        self.assertLess(self.count_calls("_judge", command), 4 * 5000)

    def test_nested_text_is_keyed_by_the_names_it_uses(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        command = guards + "".join(f'D{i}=x; sh -c "chmod -R u+w ./x"; ' for i in range(300))
        self.assertLess(self.count_calls("_scan", command), 40)

    def test_budget_is_checked_between_texts_of_one_command(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        words = " ".join(f"w{i}" for i in range(1000))
        command = guards + " ".join(f"echo $(chmod -R u+w ./x{k} {words})" for k in range(60))
        self.assertLess(self.count_calls("_scan", command), 300)

    def test_one_long_command_across_many_ways_is_read_once(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        command = guards + "chmod -R u+w ./x " + "y " * (guard.MAX_WORK // 2)
        self.assertLess(self.count_calls("_why", command), guard.MAX_WORK)

    def test_deep_subshells_chain_at_most_max_scope_maps(self):
        real, widest = guard.ChainMap, [0]

        def recorded(*maps):
            widest[0] = max(widest[0], len(maps))
            return real(*maps)

        with mock.patch.object(guard, "ChainMap", recorded):
            guard._hit("( " * 200 + "D=x; chmod -R u+w ./x" + " )" * 200, REPO, HOME)
        self.assertLessEqual(widest[0], guard.MAX_SCOPE + 1)

    def test_relative_cd_from_an_unknown_directory_stays_unknown(self):
        for cmd in ("cd - && cd build && chmod -R u+w .", 'cd "$(x)" && cd .. && chmod -R u+w .',
                    'cd - && cd "${UNSET_D}etc" && chmod -R u+w .'):
            self.assert_allowed(cmd)

    def test_a_long_directory_under_an_unset_variable_is_unknown(self):
        real, longest = guard._judge, [0]

        def recorded(words, home, assigned, here):
            longest[0] = max(longest[0], len(here or ""))
            return real(words, home, assigned, here)

        with mock.patch.object(guard, "_judge", recorded):
            guard._hit('cd "$OUT/' + "a" * 5000 + '"; chmod -R u+w x', REPO, HOME)
        self.assertLessEqual(longest[0], guard.PATH_MAX)

    def test_long_cd_chains_stop_growing_the_directory(self):
        self.assert_allowed("cd a; " * 3000 + "chmod -R u+w ../../x")
        real, longest = guard.resolve_cd_target, [0]

        def recorded(words, here):
            longest[0] = max(longest[0], len(here or ""))
            return real(words, here)

        with mock.patch.object(guard, "resolve_cd_target", recorded):
            guard._hit("cd a; " * 3000 + "chmod -R u+w ../../x", REPO, HOME)
        self.assertLessEqual(longest[0], guard.PATH_MAX)

    def test_commands_that_change_nothing_are_not_read_per_world(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        command = guards + "".join(f"ls x{k}; " for k in range(1000)) + "chmod -R u+w ./x"
        self.assertLess(self.count_calls("_assignments", command), 100)

    def test_nested_texts_past_max_depth_are_not_read(self):
        deep = "chown -R me /etc"
        for _ in range(guard.MAX_DEPTH + 1):
            deep = f"echo $({deep})"
        self.assert_allowed(deep)

    def test_one_nested_text_repeated_in_many_directories_is_read_once_each(self):
        guards = "".join(f"if {c}; then cd {c}; fi; " for c in "abcd")
        words = " ".join(f"w{i}" for i in range(1000))
        text = f'sh -c "chmod -R u+w ./x {words}"'
        # Once in each of the 16 directories, not once per repeat.
        self.assertLess(self.count_calls("_scan", guards + "; ".join([text] * 200)), 40)

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
