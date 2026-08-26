import unittest
from unittest.mock import patch, MagicMock
from scripts.lib.pull_request import PullRequest, Review, IssueComment, CheckRun

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

if __name__ == '__main__':
    unittest.main()
