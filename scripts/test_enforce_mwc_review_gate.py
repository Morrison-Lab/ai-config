#!/usr/bin/env python3
"""Test suite for plugins/ai-config/enforce-mwc-review-gate.py.

Exercises the pure `evaluate()` decision function with synthetic PR states,
plus the command-matching and fetch paths in `main()` via stdin/stdout
capture with a mocked `gh`. Includes a regression case reproducing the
state of Lacaedemon/sparta#1427 at merge time (Morrison-Lab/ai-config#2676):
zero formal reviews, a "Needs more work" verdict comment, and a later
demo-diff bot comment that the old gate mistook for the review.
"""
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_SCRIPT = os.path.join(ROOT, "plugins", "ai-config", "enforce-mwc-review-gate.py")


def load_gate():
    spec = importlib.util.spec_from_file_location("enforce_mwc_review_gate", GATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_gate()

HEAD = "8d7864c66c90ce495ae53deeaa8f1e86f3cf18b7"


def comment(body, login="github-actions"):
    return {"author": {"login": login}, "body": body}


def review(login, state):
    return {"author": {"login": login}, "state": state}


def pr(reviews=(), comments=(), checks=(), head=HEAD,
       url="https://github.com/Lacaedemon/sparta/pull/1427"):
    return {
        "reviews": list(reviews),
        "comments": list(comments),
        "statusCheckRollup": list(checks),
        "headRefOid": head,
        "url": url,
    }


NEEDS_WORK_VERDICT = comment(
    "**Claude finished review**\n\n### Verdict\n**Needs more work** --- "
    "max_frames is out of sync with the extended expect window.\n\n"
    f"Reviewed commit: {HEAD}"
)
CLEAN_VERDICT = comment(
    "**Claude finished review**\n\n### Verdict\n**Ready for merge** --- all "
    f"prior findings addressed.\n\nReviewed commit: {HEAD}"
)
DEMO_DIFF = comment(
    "<!-- sparta-website-demo-diff -->\n\n### Demo snapshot diff\n"
    "Per-tick sim state transcripts for every website demo clip."
)
MERGE_CMD = "gh pr merge 1427 -R Lacaedemon/sparta --squash"


class TestEvaluate(unittest.TestCase):
    def test_sparta_1427_regression_denied(self):
        """Zero reviews + Needs-more-work verdict + later demo-diff comment."""
        state = pr(comments=[NEEDS_WORK_VERDICT, DEMO_DIFF])
        decision = gate.evaluate(MERGE_CMD, state)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("not clean", decision["reason"])

    def test_formal_review_presence_does_not_satisfy(self):
        """A Copilot COMMENTED review must not neutralize a dirty verdict."""
        state = pr(
            reviews=[review("copilot-pull-request-reviewer[bot]", "COMMENTED")],
            comments=[NEEDS_WORK_VERDICT, DEMO_DIFF],
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_clean_verdict_allows(self):
        state = pr(comments=[NEEDS_WORK_VERDICT, CLEAN_VERDICT])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_verdict_order_latest_wins(self):
        state = pr(comments=[CLEAN_VERDICT, NEEDS_WORK_VERDICT])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_claude_finished_task_comment_does_not_shadow_verdict(self):
        """A later non-review `**Claude finished` comment (no ### Verdict
        heading) must not shadow the real verdict or classify at all."""
        task = comment(
            "**Claude finished @user's task** --- that helper is approved "
            "usage; no findings there."
        )
        state = pr(comments=[NEEDS_WORK_VERDICT, task])
        decision = gate.evaluate(MERGE_CMD, state)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("not clean", decision["reason"])

    def test_claude_finished_task_comment_alone_is_no_verdict(self):
        task = comment("**Claude finished @user's task** --- approved usage.")
        decision = gate.evaluate(MERGE_CMD, pr(comments=[task]))
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("no review verdict", decision["reason"])

    def test_negated_approvals_deny(self):
        for phrase in ("Cannot approve yet; blocking issues remain.",
                       "I don't approve this change.",
                       "This PR is not approved.",
                       "Unapproved pending fixes.",
                       "I disapprove of this approach."):
            body = comment(f"**Claude finished review**\n\n### Verdict\n{phrase}")
            decision = gate.evaluate(MERGE_CMD, pr(comments=[body]))
            self.assertEqual(decision["decision"], "deny", phrase)

    def test_stale_clean_verdict_denied(self):
        stale = comment(
            "**Claude finished review**\n\n### Verdict\n**Ready for merge**\n\n"
            "Reviewed commit: 0123456789abcdef0123456789abcdef01234567"
        )
        state = pr(comments=[stale])
        decision = gate.evaluate(MERGE_CMD, state)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("not the current PR head", decision["reason"])

    def test_last_reviewed_commit_line_governs(self):
        """Prose quoting an earlier round's commit must not mark the verdict
        stale when the footer names the head."""
        body = comment(
            "**Claude finished review**\n\n### Verdict\n**Ready for merge** "
            "--- round 1 (Reviewed commit: 0123456789abcdef0123456789abcdef01234567) "
            f"is superseded.\n\nReviewed commit: {HEAD}"
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, pr(comments=[body]))["decision"], "allow")

    def test_clean_verdict_without_sha_line_allows(self):
        no_sha = comment("**Claude finished review**\n\n### Verdict\n**Ready for merge**")
        state = pr(comments=[no_sha])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_no_reviews_no_verdict_denied(self):
        decision = gate.evaluate(MERGE_CMD, pr(comments=[DEMO_DIFF]))
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("no review verdict", decision["reason"])

    def test_ambiguous_verdict_fails_closed(self):
        vague = comment("**Claude finished review**\n\n### Verdict\nInteresting change.")
        self.assertEqual(gate.evaluate(MERGE_CMD, pr(comments=[vague]))["decision"], "deny")

    def test_human_approval_allows(self):
        state = pr(reviews=[review("d-morrison", "APPROVED")])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_human_changes_requested_denies_despite_clean_verdict(self):
        state = pr(
            reviews=[review("d-morrison", "CHANGES_REQUESTED")],
            comments=[CLEAN_VERDICT],
        )
        decision = gate.evaluate(MERGE_CMD, state)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("CHANGES_REQUESTED", decision["reason"])

    def test_human_commented_review_does_not_approve(self):
        state = pr(reviews=[review("d-morrison", "COMMENTED")])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_bot_suffix_login_ignored_but_botlike_human_counts(self):
        """`talbot` is a human: their CHANGES_REQUESTED must deny even with a
        clean bot verdict present."""
        state = pr(
            reviews=[review("talbot", "CHANGES_REQUESTED")],
            comments=[CLEAN_VERDICT],
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")
        state2 = pr(reviews=[review("talbot", "APPROVED")])
        self.assertEqual(gate.evaluate(MERGE_CMD, state2)["decision"], "allow")

    def test_dismissed_in_place_clears(self):
        """GitHub mutates a dismissed review's state to DISMISSED in place."""
        state = pr(
            reviews=[review("d-morrison", "DISMISSED")],
            comments=[CLEAN_VERDICT],
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_dismissed_trailing_entry_also_clears(self):
        state = pr(
            reviews=[review("d-morrison", "CHANGES_REQUESTED"),
                     review("d-morrison", "DISMISSED")],
            comments=[CLEAN_VERDICT],
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_later_approval_supersedes_changes_requested(self):
        state = pr(reviews=[review("d-morrison", "CHANGES_REQUESTED"),
                            review("d-morrison", "APPROVED")])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_red_ci_denies_even_with_approval(self):
        state = pr(
            reviews=[review("d-morrison", "APPROVED")],
            checks=[{"name": "Validate & test", "conclusion": "FAILURE"}],
        )
        decision = gate.evaluate(MERGE_CMD, state)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("Validate & test", decision["reason"])

    def test_pending_ci_denies(self):
        state = pr(comments=[CLEAN_VERDICT],
                   checks=[{"name": "demo", "status": "IN_PROGRESS"}])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_admin_flag_denied_outright(self):
        decision = gate.evaluate(
            "gh pr merge 1427 -R Lacaedemon/sparta --squash --admin",
            pr(reviews=[review("d-morrison", "APPROVED")]),
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("--admin", decision["reason"])

    def test_blockquoted_verdict_does_not_shadow(self):
        """An ARD reply quoting the review's verdict section (blockquoted)
        must not become the governing verdict."""
        ard_reply = comment(
            "**Claude finished @user's task** --- replying to the review:\n"
            "> ### Verdict\n> **Ready for merge**\n\nAddressed inline."
        )
        state = pr(comments=[NEEDS_WORK_VERDICT, ard_reply])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_human_authored_verdict_comment_ignored(self):
        """Only reviewer logins can author the governing verdict; a comment
        under the user's own login cannot self-approve."""
        fake = comment("### Verdict\n**Ready for merge**", login="dem-extra1")
        decision = gate.evaluate(MERGE_CMD, pr(comments=[fake]))
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("non-reviewer login", decision["reason"])

    def test_suffixed_bot_login_verdict_counts(self):
        clean = comment("### Verdict\n**Ready for merge**", login="claude[bot]")
        self.assertEqual(gate.evaluate(MERGE_CMD, pr(comments=[clean]))["decision"], "allow")

    def test_reviewer_bot_approval_is_not_human_approval(self):
        """GraphQL reports bot logins bare (no [bot] suffix); a coderabbitai
        APPROVED review must not read as a human approval over a
        Needs-more-work verdict."""
        state = pr(
            reviews=[review("coderabbitai", "APPROVED")],
            comments=[NEEDS_WORK_VERDICT],
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_contraction_negations_deny(self):
        for phrase in ("This isn't ready for merge.",
                       "This isn't approved.",
                       "This shouldn't be approved.",
                       "I wouldn't approve this.",
                       "This cannot yet be approved."):
            body = comment(f"**Claude finished review**\n\n### Verdict\n{phrase}")
            decision = gate.evaluate(MERGE_CMD, pr(comments=[body]))
            self.assertEqual(decision["decision"], "deny", phrase)

    def test_sha_above_heading_still_checked_for_staleness(self):
        body = comment(
            "**Claude finished review**\n\n"
            "Reviewed commit: 0123456789abcdef0123456789abcdef01234567\n\n"
            "### Verdict\n**Ready for merge**"
        )
        decision = gate.evaluate(MERGE_CMD, pr(comments=[body]))
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("not the current PR head", decision["reason"])

    def test_fenced_verdict_does_not_shadow(self):
        """A trusted-login comment quoting the verdict format in a code fence
        must not supersede a real not-clean verdict."""
        fenced = comment(
            "Addressed all items. The reviewer's format is:\n"
            "```\n### Verdict\n**Ready for merge**\n```"
        )
        state = pr(comments=[NEEDS_WORK_VERDICT, fenced])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_human_not_clean_verdict_denies(self):
        """A human self-review verdict counts in the deny direction: it
        supersedes an older clean bot verdict."""
        human = comment("### Verdict\n**Needs more work** --- regression found.",
                        login="d-morrison")
        state = pr(comments=[CLEAN_VERDICT, human])
        decision = gate.evaluate(MERGE_CMD, state)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("not clean", decision["reason"])

    def test_human_approval_does_not_override_not_clean_verdict(self):
        """Disagreement among reviews is not fully clean (ai-config#2274):
        a standing Needs-more-work verdict vetoes even a human APPROVED."""
        state = pr(
            reviews=[review("d-morrison", "APPROVED")],
            comments=[NEEDS_WORK_VERDICT],
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_human_approval_allows_when_verdict_absent_or_ambiguous(self):
        state = pr(reviews=[review("d-morrison", "APPROVED")],
                   comments=[DEMO_DIFF])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_status_context_state_field_gates_ci(self):
        """Classic commit statuses carry `state`, not conclusion/status."""
        for state_val in ("FAILURE", "ERROR", "PENDING"):
            state = pr(comments=[CLEAN_VERDICT],
                       checks=[{"context": "ci/legacy", "state": state_val}])
            self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"],
                             "deny", state_val)
        ok = pr(comments=[CLEAN_VERDICT],
                checks=[{"context": "ci/legacy", "state": "SUCCESS"}])
        self.assertEqual(gate.evaluate(MERGE_CMD, ok)["decision"], "allow")

    def test_hyphenated_reviewed_commit_checked_for_staleness(self):
        body = comment(
            "**Claude finished review**\n\n### Verdict\n**Ready for merge**\n\n"
            "Reviewed-Commit: 0123456789abcdef0123456789abcdef01234567"
        )
        decision = gate.evaluate(MERGE_CMD, pr(comments=[body]))
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("not the current PR head", decision["reason"])

    def test_headline_outranks_later_prose(self):
        """'Ready for merge' headline with prose mentioning a resolved
        wasn't-ready concern must classify clean."""
        body = comment(
            "**Claude finished review**\n\n### Verdict\n"
            "**Ready for merge**\n"
            "The concern that this wasn't ready is resolved.\n\n"
            f"Reviewed commit: {HEAD}"
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, pr(comments=[body]))["decision"], "allow")

    def test_graphql_merge_mutation_denied(self):
        decision = gate.evaluate(
            "gh api graphql -f query='mutation { mergePullRequest(input: {}) }'",
            pr(comments=[CLEAN_VERDICT]),
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("GraphQL", decision["reason"])

    def test_untrusted_verdict_cannot_launder_standing_veto(self):
        """A later non-reviewer comment with a bare ### Verdict heading must
        not supersede a trusted Needs-more-work verdict -- with or without a
        human approval on file (round-4 veto-laundering case)."""
        stray = comment("### Verdict\n**Ready for merge**", login="dem-extra1")
        vague = comment("### Verdict\nSee discussion above.", login="dem-extra1")
        for later in (stray, vague):
            state = pr(
                reviews=[review("d-morrison", "APPROVED")],
                comments=[NEEDS_WORK_VERDICT, later],
            )
            self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"],
                             "deny", later["body"])

    def test_untrusted_clean_does_not_shadow_trusted_clean(self):
        """A later ARD summary with a ### Verdict heading must not flip a
        legitimately clean trusted verdict into a deny."""
        stray = comment("### Verdict\n**Ready for merge**", login="dem-extra1")
        state = pr(comments=[CLEAN_VERDICT, stray])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_unclosed_fence_in_trusted_verdict_fails_ambiguous(self):
        """An unpaired fence swallowing the reviewer's own not-clean verdict
        must not read as verdict-free (which could resurrect an older clean
        verdict); it classifies ambiguous and denies."""
        swallowed = comment(
            "**Claude finished review**\n\n```\n### Verdict\n"
            "**Needs more work**\n\nno closing fence follows\n```extra\n"
        )
        state = pr(comments=[CLEAN_VERDICT, swallowed])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "deny")

    def test_inline_code_span_mention_does_not_reclassify(self):
        """A trusted follow-up merely mentioning the `### Verdict` marker in
        prose must not demote a standing clean verdict to ambiguous."""
        mention = comment(
            "Formatting note: reviews end with a `### Verdict` section."
        )
        state = pr(comments=[CLEAN_VERDICT, mention])
        self.assertEqual(gate.evaluate(MERGE_CMD, state)["decision"], "allow")

    def test_verdict_section_isolated_from_findings_prose(self):
        """A 'needs more work' mention in findings prose above the verdict
        heading must not flip a clean verdict."""
        body = comment(
            "**Claude finished review**\n\nRound 1 said this needs more work; "
            "that is now addressed.\n\n### Verdict\n**Ready for merge**\n\n"
            f"Reviewed commit: {HEAD}"
        )
        self.assertEqual(gate.evaluate(MERGE_CMD, pr(comments=[body]))["decision"], "allow")


def gh_result(rc=0, stdout="", stderr=""):
    return MagicMock(returncode=rc, stdout=stdout, stderr=stderr)


class TestMain(unittest.TestCase):
    def run_main(self, payload, view=None, comments=None, side_effect=None):
        """Run main() with `gh` mocked: first call is `gh pr view`, second is
        the paginated comments fetch."""
        stdout = io.StringIO()
        if side_effect is None:
            state = view if view is not None else pr()
            view_payload = {k: state[k] for k in
                            ("url", "reviews", "statusCheckRollup", "headRefOid")}
            side_effect = [
                gh_result(stdout=json.dumps(view_payload)),
                gh_result(stdout=json.dumps(comments if comments is not None
                                            else state["comments"])),
            ]
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
             patch.object(sys, "stdout", stdout), \
             patch.object(gate.subprocess, "run", side_effect=side_effect) as run_mock:
            gate.main()
        return json.loads(stdout.getvalue()), run_mock

    def payload(self, cmd, name="run_command"):
        return {"toolCall": {"name": name, "args": {"CommandLine": cmd, "Cwd": "."}}}

    def test_non_run_command_allowed(self):
        decision, run_mock = self.run_main(self.payload("x", name="send_message"))
        self.assertEqual(decision["decision"], "allow")
        run_mock.assert_not_called()

    def test_non_merge_command_allowed(self):
        decision, run_mock = self.run_main(self.payload("git status"))
        self.assertEqual(decision["decision"], "allow")
        run_mock.assert_not_called()

    def test_git_merge_origin_main_not_gated(self):
        """Syncing main INTO the branch is the mandated direction; the gate
        must not block it (it cannot merge into main)."""
        decision, run_mock = self.run_main(self.payload("git merge origin/main"))
        self.assertEqual(decision["decision"], "allow")
        run_mock.assert_not_called()

    def test_chained_merge_denied(self):
        base = "gh pr merge 5 -R o/r"
        for cmd in (f"gh pr create; {base}", f"true && {base}",
                    f"{base} || true", f"echo hi | {base}",
                    f"true & {base}", f"{base} --subject $(cat t)",
                    f"{base}\ngit push"):
            decision, _ = self.run_main(self.payload(cmd), side_effect=[])
            self.assertEqual(decision["decision"], "deny", cmd)

    def test_gh_api_merge_resolves_pr_from_url(self):
        """The API route must gate the PR named in the URL, not the
        checked-out branch's PR."""
        decision, run_mock = self.run_main(
            self.payload("gh api repos/Lacaedemon/sparta/pulls/1427/merge -X PUT"),
            view=pr(comments=[NEEDS_WORK_VERDICT]),
        )
        self.assertEqual(decision["decision"], "deny")
        view_cmd = run_mock.call_args_list[0][0][0]
        self.assertIn("1427", view_cmd)
        self.assertIn("--repo", view_cmd)
        self.assertIn("Lacaedemon/sparta", view_cmd)

    def test_flags_before_number_resolves_target(self):
        """`gh pr merge --squash 1427 -R o/r` must gate #1427, not the
        checked-out branch's PR."""
        decision, run_mock = self.run_main(
            self.payload("gh pr merge --squash 1427 -R Lacaedemon/sparta"),
            view=pr(comments=[NEEDS_WORK_VERDICT]),
        )
        self.assertEqual(decision["decision"], "deny")
        view_cmd = run_mock.call_args_list[0][0][0]
        self.assertIn("1427", view_cmd)

    def test_null_toolcall_fields_do_not_crash(self):
        for payload in ({"toolCall": None},
                        {"toolCall": {"name": "run_command", "args": None}},
                        {"toolCall": {"name": "run_command",
                                      "args": {"CommandLine": None}}}):
            stdout = io.StringIO()
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                 patch.object(sys, "stdout", stdout):
                gate.main()
            decision = json.loads(stdout.getvalue())
            self.assertEqual(decision["decision"], "allow", payload)

    def test_malformed_stdin_fails_closed(self):
        stdout = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO("not json")), \
             patch.object(sys, "stdout", stdout):
            gate.main()
        self.assertEqual(json.loads(stdout.getvalue())["decision"], "deny")

    def test_graphql_merge_denied_via_main_without_gh_call(self):
        """The GraphQL denial must be reachable from main()'s trigger, and
        must not depend on fetching any PR state."""
        for mutation in ("mergePullRequest", "enablePullRequestAutoMerge"):
            cmd = ("gh api graphql -f query='mutation {{ "
                   "{}(input: {{}}) }}'").format(mutation)
            decision, run_mock = self.run_main(self.payload(cmd), side_effect=[])
            self.assertEqual(decision["decision"], "deny", mutation)
            run_mock.assert_not_called()

    def test_placeholder_api_merge_gated_via_cwd(self):
        """gh api repos/{owner}/{repo}/pulls/N/merge must be gated, resolving
        the PR from Cwd (no --repo flag) exactly as gh itself would."""
        decision, run_mock = self.run_main(
            self.payload("gh api repos/{owner}/{repo}/pulls/1427/merge -X PUT"),
            view=pr(comments=[NEEDS_WORK_VERDICT]),
        )
        self.assertEqual(decision["decision"], "deny")
        view_cmd = run_mock.call_args_list[0][0][0]
        self.assertIn("1427", view_cmd)
        self.assertNotIn("--repo", view_cmd)

    def test_inherited_flag_between_group_and_subcommand_gated(self):
        """gh accepts -R between the command group and the subcommand."""
        for cmd in ("gh pr -R Lacaedemon/sparta merge 1427 --squash",
                    "gh pr --repo Lacaedemon/sparta merge 1427"):
            decision, run_mock = self.run_main(
                self.payload(cmd), view=pr(comments=[NEEDS_WORK_VERDICT]))
            self.assertEqual(decision["decision"], "deny", cmd)
            view_cmd = run_mock.call_args_list[0][0][0]
            self.assertIn("1427", view_cmd)
            run_mock.reset_mock()

    def test_merge_word_as_search_term_not_gated(self):
        """A non-merge gh pr subcommand mentioning 'merge' as data must not
        trigger the gate."""
        for cmd in ("gh pr list -R o/r --search merge",
                    "gh pr view 5 -R o/r --json mergeable"):
            decision, run_mock = self.run_main(self.payload(cmd))
            self.assertEqual(decision["decision"], "allow", cmd)
            run_mock.assert_not_called()

    def test_substitution_wrapped_merge_denied(self):
        """A merge wrapped in command substitution or a subshell must still
        register and be denied by the chain check."""
        base = "gh pr merge 5 -R o/r"
        backtick = chr(96)
        # side_effect=[] makes any gh call fail loudly: these four must be
        # denied by the chain check alone, before any state fetch.
        for cmd in (f"VAR=$({base})", f"VAR={backtick}{base}{backtick}",
                    f"echo $({base})", f"({base})"):
            decision, _ = self.run_main(self.payload(cmd), side_effect=[])
            self.assertEqual(decision["decision"], "deny", cmd)
            self.assertIn("chained", decision["reason"], cmd)
        # An absolute-path gh is a plain merge: it resolves and gates PR 5.
        decision, run_mock = self.run_main(
            self.payload(f"/opt/homebrew/bin/{base} --squash"),
            view=pr(comments=[NEEDS_WORK_VERDICT]),
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("5", run_mock.call_args_list[0][0][0])

    def test_gh_stack_merge_gated(self):
        decision, _ = self.run_main(
            self.payload("gh stack merge 7 -R o/r"),
            view=pr(comments=[NEEDS_WORK_VERDICT]),
        )
        self.assertEqual(decision["decision"], "deny")

    def test_gh_view_failure_denies(self):
        decision, _ = self.run_main(self.payload(MERGE_CMD),
                                    side_effect=[gh_result(rc=1, stderr="boom")])
        self.assertEqual(decision["decision"], "deny")

    def test_comments_fetch_failure_denies(self):
        state = pr(comments=[CLEAN_VERDICT])
        view_payload = {k: state[k] for k in
                        ("url", "reviews", "statusCheckRollup", "headRefOid")}
        decision, _ = self.run_main(
            self.payload(MERGE_CMD),
            side_effect=[gh_result(stdout=json.dumps(view_payload)),
                         gh_result(rc=1, stderr="rate limited")],
        )
        self.assertEqual(decision["decision"], "deny")

    def test_comments_fetched_via_paginated_rest(self):
        _, run_mock = self.run_main(
            self.payload(MERGE_CMD), view=pr(comments=[CLEAN_VERDICT]))
        api_cmd = run_mock.call_args_list[1][0][0]
        self.assertIn("api", api_cmd)
        self.assertIn("--paginate", api_cmd)
        self.assertIn("repos/Lacaedemon/sparta/issues/1427/comments", api_cmd)

    def test_multi_page_comments_merged_latest_governs(self):
        """--paginate emits one JSON array per page; the last page's verdict
        must govern."""
        state = pr()
        view_payload = {k: state[k] for k in
                        ("url", "reviews", "statusCheckRollup", "headRefOid")}
        pages = (json.dumps([NEEDS_WORK_VERDICT]) + "\n"
                 + json.dumps([CLEAN_VERDICT]))
        decision, _ = self.run_main(
            self.payload(MERGE_CMD),
            side_effect=[gh_result(stdout=json.dumps(view_payload)),
                         gh_result(stdout=pages)],
        )
        self.assertEqual(decision["decision"], "allow")

    def test_repo_flag_forwarded(self):
        _, run_mock = self.run_main(
            self.payload("gh pr merge 9 -R Morrison-Lab/ai-config --squash"),
            view=pr(comments=[CLEAN_VERDICT],
                    url="https://github.com/Morrison-Lab/ai-config/pull/9"),
        )
        view_cmd = run_mock.call_args_list[0][0][0]
        self.assertIn("--repo", view_cmd)
        self.assertIn("Morrison-Lab/ai-config", view_cmd)
        self.assertIn("9", view_cmd)

    def test_clean_verdict_end_to_end_allows(self):
        decision, _ = self.run_main(
            self.payload(MERGE_CMD), view=pr(comments=[CLEAN_VERDICT]))
        self.assertEqual(decision["decision"], "allow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
