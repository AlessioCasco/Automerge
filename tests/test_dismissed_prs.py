import unittest
import json
import sys
import os
from unittest.mock import patch

# Add src directory to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from github_client import GitHubClient  # noqa: E402

class MockResponse:
    def __init__(self, json_data, status_code, headers=None):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)
        self.headers = headers or {}
    def json(self):
        return self.json_data

class TestDismissedPRs(unittest.TestCase):
    def setUp(self):
        self.access_token = "my_access_token"
        self.github_client = GitHubClient(self.access_token, "owner", "test_user")

    @patch.object(GitHubClient, "merge_pull_req")
    @patch.object(GitHubClient, "get_last_comment")
    @patch("requests.post")
    def test_process_dismissed_pr_with_no_changes(self, mock_post, mock_get_last_comment, mock_merge):
        """Test that a dismissed PR with no changes gets re-approved and merged."""
        pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123"
        }
        # Simulate approval check (DISMISSED)
        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                MockResponse([{"user": {"login": "test_user"}, "state": "DISMISSED"}], 200)
            ]
            # Simulate last comment with no changes
            mock_get_last_comment.return_value = {"body": "No changes. Your infrastructure matches the configuration"}
            mock_post.return_value = MockResponse({}, 200)
            self.github_client.process_dismissed_prs([pr])
            mock_post.assert_called_with(
                "https://api.github.com/repos/owner/repo/pulls/123/reviews",
                headers=self.github_client.headers,
                json={"event": "APPROVE"},
                timeout=10
            )
            mock_merge.assert_called_once_with([pr])

    @patch.object(GitHubClient, "merge_pull_req")
    @patch.object(GitHubClient, "get_last_comment")
    @patch("requests.post")
    def test_process_dismissed_pr_with_changes(self, mock_post, mock_get_last_comment, mock_merge):
        """Test that a dismissed PR with changes gets re-approved but not merged."""
        pr = {
            "number": 124,
            "url": "https://api.github.com/repos/owner/repo/pulls/124",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/124"
        }
        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                MockResponse([{"user": {"login": "test_user"}, "state": "DISMISSED"}], 200)
            ]
            mock_get_last_comment.return_value = {"body": "Plan: 1 to add, 0 to change, 0 to destroy."}
            mock_post.return_value = MockResponse({}, 200)
            self.github_client.process_dismissed_prs([pr])
            mock_post.assert_called_with(
                "https://api.github.com/repos/owner/repo/pulls/124/reviews",
                headers=self.github_client.headers,
                json={"event": "APPROVE"},
                timeout=10
            )
            mock_merge.assert_not_called()

    @patch.object(GitHubClient, "merge_pull_req")
    @patch.object(GitHubClient, "get_last_comment")
    @patch("requests.post")
    def test_process_dismissed_pr_with_no_comments(self, mock_post, mock_get_last_comment, mock_merge):
        """Test that a dismissed PR with no comments gets re-approved but not merged."""
        pr = {
            "number": 125,
            "url": "https://api.github.com/repos/owner/repo/pulls/125",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/125"
        }
        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                MockResponse([{"user": {"login": "test_user"}, "state": "DISMISSED"}], 200)
            ]
            mock_get_last_comment.return_value = None
            mock_post.return_value = MockResponse({}, 200)
            self.github_client.process_dismissed_prs([pr])
            mock_post.assert_called_with(
                "https://api.github.com/repos/owner/repo/pulls/125/reviews",
                headers=self.github_client.headers,
                json={"event": "APPROVE"},
                timeout=10
            )
            mock_merge.assert_not_called()
