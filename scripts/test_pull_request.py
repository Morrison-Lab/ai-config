import json
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.lib.pull_request import PullRequest, Review, IssueComment, CheckRun, ReviewThread

class TestFetchedFieldPlumbing(unittest.TestCase):
    """Every property reading `_data` must have its key REQUESTED from `gh`.

    `gh pr view --json a,b` returns only `a` and `b`, so a property reading an
    unrequested key gets `None` forever and its consumer silently takes the
    wrong branch. That is how `is_draft` shipped inert: the property existed,
    `isDraft` was not in the field list, and the unit test for the consumer
    injected `_data` directly and so never exercised this path at all
    (ai-config#3651 review).

    The fetcher below mimics `gh`'s filtering rather than returning a fixed
    dict, so a property whose key is not requested fails here instead of
    passing on a mock that is more generous than the real command.
    """

    SERVER_SIDE = {
        "headRefOid": "abc", "headRefName": "b", "state": "OPEN",
        "commits": [], "reviewDecision": "", "reviews": [], "comments": [],
        "reviewRequests": [], "isDraft": True,
    }

    def _filtering_fetcher(self, requested):
        def fetch(cmd):
            self.assertIn("--json", cmd, "the fetch must go through --json")
            names = cmd[cmd.index("--json") + 1].split(",")
            requested.extend(names)
            return json.dumps({k: v for k, v in self.SERVER_SIDE.items()
                               if k in names})
        return fetch

    def test_is_draft_survives_the_gh_field_filter(self):
        requested = []
        pr = PullRequest("1", "o/r", fetcher=self._filtering_fetcher(requested))
        self.assertIn("isDraft", requested,
                      "isDraft must be in the --json field list, or is_draft "
                      "reads None for every real PR")
        self.assertTrue(pr.is_draft,
                        "a draft PR must read as a draft after a real fetch")

    def test_a_ready_pr_reads_as_ready(self):
        self.SERVER_SIDE = dict(self.SERVER_SIDE, isDraft=False)
        pr = PullRequest("1", "o/r", fetcher=self._filtering_fetcher([]))
        self.assertFalse(pr.is_draft)


class TestPullRequest(unittest.TestCase):
    def setUp(self):
        self.mock_data = {
            "headRefOid": "abcd123",
            "headRefName": "feat/test-branch",
            "state": "OPEN",
            "commits": [{"committedDate": "2023-10-01T12:00:00Z"}],
            "reviewDecision": "CHANGES_REQUESTED",
            "reviews": [
                {"state": "CHANGES_REQUESTED", "author": {"login": "octocat"}, "submittedAt": "2023-10-02T12:00:00Z"}
            ],
            "comments": [
                {"body": "Looks good", "author": {"login": "friend"}, "createdAt": "2023-10-03T12:00:00Z"}
            ],
            "reviewRequests": [
                {"login": "copilot-pull-request-reviewer"}
            ]
        }
        self.mock_check_runs_data = {
            "check_runs": [
                {"name": "test", "status": "completed", "conclusion": "success", "html_url": "http://example.com/test"}
            ]
        }

    @patch('subprocess.run')
    def test_pull_request_initialization(self, mock_run):
        mock_run.return_value.stdout = '{"headRefOid": "abcd123"}'
        pr = PullRequest("123", "owner/repo")
        self.assertEqual(pr.head_sha, "abcd123")
        mock_run.assert_called_once()

    @patch.object(PullRequest, '_fetch_pr_data')
    def test_properties(self, mock_fetch):
        mock_fetch.return_value = self.mock_data
        pr = PullRequest("123", "owner/repo")
        
        self.assertEqual(pr.head_sha, "abcd123")
        self.assertEqual(pr.branch, "feat/test-branch")
        self.assertEqual(pr.state, "OPEN")
        self.assertEqual(pr.review_decision, "CHANGES_REQUESTED")
        self.assertEqual(pr.commit_date, "2023-10-01T12:00:00Z")
        self.assertEqual(pr.review_requests, [{"login": "copilot-pull-request-reviewer"}])
        self.assertEqual(pr.pending_review_requests, ["copilot-pull-request-reviewer"])
        
        reviews = pr.get_reviews()
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].state, "CHANGES_REQUESTED")
        self.assertEqual(reviews[0].author_login, "octocat")
        
        comments = pr.get_comments()
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].body, "Looks good")
        
    @patch('subprocess.run')
    @patch.object(PullRequest, '_fetch_pr_data')
    def test_get_check_runs(self, mock_fetch, mock_run):
        mock_fetch.return_value = self.mock_data
        mock_run.return_value.stdout = '{"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]}'
        
        pr = PullRequest("123", "owner/repo")
        runs = pr.get_check_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].name, "test")
        self.assertEqual(runs[0].status, "completed")
        self.assertEqual(runs[0].conclusion, "success")
        mock_run.assert_called_once()

    @patch('subprocess.run')
    @patch.object(PullRequest, '_fetch_pr_data')
    def test_get_review_threads(self, mock_fetch, mock_run):
        mock_fetch.return_value = self.mock_data
        graphql_resp = json.dumps({
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread_1",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "path": "src/main.py",
                                    "line": 42
                                },
                                {
                                    "id": "thread_2",
                                    "isResolved": True,
                                    "isOutdated": True,
                                    "path": "src/utils.py",
                                    "line": None
                                }
                            ]
                        }
                    }
                }
            }
        })
        mock_run.return_value.stdout = graphql_resp

        pr = PullRequest("123", "owner/repo")
        threads = pr.get_review_threads()
        self.assertEqual(len(threads), 2)
        self.assertEqual(threads[0].id, "thread_1")
        self.assertFalse(threads[0].is_resolved)
        self.assertFalse(threads[0].is_outdated)
        self.assertEqual(threads[0].path, "src/main.py")
        self.assertEqual(threads[0].line, 42)

        self.assertEqual(threads[1].id, "thread_2")
        self.assertTrue(threads[1].is_resolved)
        self.assertTrue(threads[1].is_outdated)
        self.assertEqual(threads[1].path, "src/utils.py")
        self.assertIsNone(threads[1].line)

    @patch('subprocess.run')
    @patch.object(PullRequest, '_fetch_pr_data')
    def test_get_review_threads_pagination(self, mock_fetch, mock_run):
        mock_fetch.return_value = self.mock_data
        page1 = json.dumps({
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                            "nodes": [{"id": "t1", "isResolved": True, "isOutdated": False, "path": "a.py", "line": 1}]
                        }
                    }
                }
            }
        })
        page2 = json.dumps({
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{"id": "t2", "isResolved": False, "isOutdated": True, "path": "b.py", "line": 2}]
                        }
                    }
                }
            }
        })
        mock_run.side_effect = [MagicMock(stdout=page1), MagicMock(stdout=page2)]

        pr = PullRequest("123", "owner/repo")
        threads = pr.get_review_threads()
        self.assertEqual(len(threads), 2)
        self.assertEqual(threads[0].id, "t1")
        self.assertEqual(threads[1].id, "t2")
        self.assertEqual(mock_run.call_count, 2)
        # Verify second call included cursor
        second_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("-F", second_cmd)
        self.assertIn("cursor=cur1", second_cmd)


if __name__ == '__main__':
    unittest.main()
