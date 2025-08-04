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
        self.github_client = GitHubClient(
            self.access_token, "owner", "test_user")

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
                MockResponse(
                    [{"id": 1, "user": {"login": "test_user"}, "state": "DISMISSED"}], 200)
            ]
            # Simulate last comment with no changes
            mock_get_last_comment.return_value = {
                "body": "No changes. Your infrastructure matches the configuration"}
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
                MockResponse(
                    [{"id": 1, "user": {"login": "test_user"}, "state": "DISMISSED"}], 200)
            ]
            mock_get_last_comment.return_value = {
                "body": "Plan: 1 to add, 0 to change, 0 to destroy."}
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
                MockResponse(
                    [{"id": 1, "user": {"login": "test_user"}, "state": "DISMISSED"}], 200)
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

    @patch("requests.get")
    @patch("requests.post")
    @patch("requests.put")
    @patch("builtins.print")
    def test_is_approved_handles_stale_approval(self, mock_print, mock_put, mock_post, mock_get):
        """Test that is_approved correctly handles stale/dismissed approvals."""
        pr = {
            "number": 126,
            "url": "https://api.github.com/repos/owner/repo/pulls/126"
        }

        # Simulate multiple reviews: old approved, then dismissed due to new commits
        reviews = [
            {"id": 1, "user": {"login": "test_user"}, "state": "APPROVED"},
            {"id": 2, "user": {"login": "test_user"}, "state": "DISMISSED"}
        ]

        with patch.object(self.github_client, "get_mergeable_state") as mock_state:
            mock_state.return_value = "clean"
            mock_get.return_value = MockResponse(reviews, 200)
            mock_post.return_value = MockResponse({}, 200)
            mock_put.return_value = MockResponse({"merged": True}, 200)

            # Test the merge_pull_req method which uses is_approved
            self.github_client.merge_pull_req([pr])

            # Should re-approve because latest review is dismissed
            mock_post.assert_called_with(
                "https://api.github.com/repos/owner/repo/pulls/126/reviews",
                headers=self.github_client.headers,
                json={"event": "APPROVE"},
                timeout=10
            )

            # Should print the dismissal message
            print_calls = [str(call) for call in mock_print.call_args_list]
            dismissal_message_found = any(
                "approval was dismissed/stale" in call for call in print_calls)
            self.assertTrue(dismissal_message_found,
                            "Should print dismissal message")

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_latest_review_wins(self, mock_print, mock_get):
        """Test that is_approved uses the latest review state."""
        pr_url = "https://api.github.com/repos/owner/repo/pulls/127"

        # Test case 1: Latest review is approved (should return True)
        reviews_approved_latest = [
            {"id": 1, "user": {"login": "test_user"}, "state": "DISMISSED"},
            {"id": 2, "user": {"login": "test_user"}, "state": "APPROVED"}
        ]

        mock_get.return_value = MockResponse(reviews_approved_latest, 200)
        result = self.github_client.is_approved(pr_url)
        self.assertTrue(result)

        # Test case 2: Latest review is dismissed (should return "Dismissed")
        reviews_dismissed_latest = [
            {"id": 1, "user": {"login": "test_user"}, "state": "APPROVED"},
            {"id": 2, "user": {"login": "test_user"}, "state": "DISMISSED"}
        ]

        mock_get.return_value = MockResponse(reviews_dismissed_latest, 200)
        result = self.github_client.is_approved(pr_url)
        self.assertEqual(result, "Dismissed")

        # Test case 3: Latest review is changes requested (should return False)
        reviews_changes_latest = [
            {"id": 1, "user": {"login": "test_user"}, "state": "APPROVED"},
            {"id": 2, "user": {"login": "test_user"}, "state": "CHANGES_REQUESTED"}
        ]

        mock_get.return_value = MockResponse(reviews_changes_latest, 200)
        result = self.github_client.is_approved(pr_url)
        self.assertFalse(result)
