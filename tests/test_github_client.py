import unittest
import json
import sys
import os
from unittest.mock import patch, call
import requests

# Add src directory to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from github_client import GitHubClient  # noqa: E402
from utils import (  # noqa: E402
    DEFAULT_TIMEOUT,
    MERGEABLE_STATE_TIMEOUT,
    GITHUB_API_VERSION,
    GITHUB_ACCEPT_HEADER
)


class MockResponse:
    """Mock response class for HTTP requests."""

    def __init__(self, json_data, status_code, headers=None):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data) if json_data is not None else ""
        self.headers = headers or {}

    def json(self):
        if isinstance(self.json_data, Exception):
            raise self.json_data
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class TestGitHubClientInit(unittest.TestCase):
    """Test GitHubClient initialization."""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters."""
        client = GitHubClient("token123", "owner", "user")

        self.assertEqual(client.access_token, "token123")
        self.assertEqual(client.owner, "owner")
        self.assertEqual(client.github_user, "user")
        self.assertEqual(client.base_repos_url,
                         "https://api.github.com/repos/owner/")

        # Check headers
        expected_headers = {
            "Authorization": "Bearer token123",
            "Accept": GITHUB_ACCEPT_HEADER,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        self.assertEqual(client.headers, expected_headers)

        # Check console is initialized
        self.assertIsNotNone(client.console)

    def test_init_with_different_tokens(self):
        """Test initialization with different token formats."""
        test_cases = [
            ("ghp_token123", "ghp_token123"),
            ("github_pat_token", "github_pat_token"),
            ("", ""),
            ("token with spaces", "token with spaces")
        ]

        for token, expected in test_cases:
            with self.subTest(token=token):
                client = GitHubClient(token, "owner", "user")
                self.assertEqual(client.access_token, expected)
                self.assertEqual(
                    client.headers["Authorization"], f"Bearer {expected}")


class TestGetPullRequests(unittest.TestCase):
    """Test the get_pull_requests method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.repos = ["repo1", "repo2"]
        self.filters = ["^\\[DEPENDENCIES\\]", "^\\[Dependabot\\]"]

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_pull_requests_success(self, mock_print, mock_get):
        """Test successful pull request retrieval."""
        mock_get.side_effect = [
            MockResponse([
                {"title": "[DEPENDENCIES] Update lib", "number": 1},
                {"title": "Other PR", "number": 2},
                {"title": "[Dependabot] Bump version", "number": 3}
            ], 200),
            MockResponse([
                {"title": "[DEPENDENCIES] Update another", "number": 4},
                {"title": "Manual PR", "number": 5}
            ], 200)
        ]

        result = self.client.get_pull_requests(self.repos, self.filters)

        self.assertEqual(len(result), 3)
        titles = [pr["title"] for pr in result]
        self.assertIn("[DEPENDENCIES] Update lib", titles)
        self.assertIn("[Dependabot] Bump version", titles)
        self.assertIn("[DEPENDENCIES] Update another", titles)
        self.assertNotIn("Other PR", titles)
        self.assertNotIn("Manual PR", titles)

        # Verify API calls
        expected_calls = [
            call("https://api.github.com/repos/owner/repo1/pulls?per_page=100",
                 headers=self.client.headers, timeout=DEFAULT_TIMEOUT),
            call("https://api.github.com/repos/owner/repo2/pulls?per_page=100",
                 headers=self.client.headers, timeout=DEFAULT_TIMEOUT)
        ]
        mock_get.assert_has_calls(expected_calls)

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_pull_requests_no_filters(self, mock_print, mock_get):
        """Test get_pull_requests with no filters."""
        with self.assertRaises(SystemExit) as context:
            self.client.get_pull_requests(self.repos, [])

        self.assertEqual(context.exception.code, 1)
        mock_print.assert_called_with(
            "No filters to match, please provide at least one, exiting")

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_pull_requests_api_error(self, mock_print, mock_get):
        """Test get_pull_requests with API error."""
        mock_get.return_value = MockResponse({"message": "Not Found"}, 404)

        with self.assertRaises(SystemExit) as context:
            self.client.get_pull_requests(self.repos, self.filters)

        self.assertEqual(context.exception.code, 1)

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_pull_requests_network_error(self, mock_print, mock_get):
        """Test get_pull_requests with network error."""
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Network error")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.client.get_pull_requests(self.repos, self.filters)

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_pull_requests_empty_response(self, mock_print, mock_get):
        """Test get_pull_requests with empty response."""
        mock_get.side_effect = [
            MockResponse([], 200),
            MockResponse([], 200)
        ]

        result = self.client.get_pull_requests(self.repos, self.filters)
        self.assertEqual(len(result), 0)

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_pull_requests_complex_regex(self, mock_print, mock_get):
        """Test get_pull_requests with complex regex patterns."""
        complex_filters = [
            "^\\[DEPENDENCIES\\]\\s+Update\\s+\\w+",
            "^\\[Dependabot\\].*bump.*version",
            "^Renovate.*"
        ]

        mock_get.return_value = MockResponse([
            {"title": "[DEPENDENCIES] Update terraform", "number": 1},
            {"title": "[Dependabot] bump package version", "number": 2},
            {"title": "Renovate: Update dependencies", "number": 3},
            {"title": "[DEPENDENCIES]Update without space", "number": 4},
            {"title": "[Dependabot] different format", "number": 5}
        ], 200)

        result = self.client.get_pull_requests(["repo1"], complex_filters)

        # Should match first 3 PRs based on regex patterns
        self.assertEqual(len(result), 3)
        numbers = [pr["number"] for pr in result]
        self.assertIn(1, numbers)
        self.assertIn(2, numbers)
        self.assertIn(3, numbers)


class TestUpdateBranch(unittest.TestCase):
    """Test the update_branch method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pull_req = {
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "number": 123,
            "head": {"repo": {"name": "test-repo"}}
        }

    @patch("requests.put")
    @patch("builtins.print")
    def test_update_branch_success(self, mock_print, mock_put):
        """Test successful branch update."""
        mock_put.return_value = MockResponse({"message": "Updated"}, 202)

        self.client.update_branch([self.pull_req])

        mock_put.assert_called_once_with(
            "https://api.github.com/repos/owner/repo/pulls/123/update-branch",
            headers=self.client.headers,
            timeout=DEFAULT_TIMEOUT
        )

    @patch("requests.put")
    @patch("builtins.print")
    def test_update_branch_api_error(self, mock_print, mock_put):
        """Test update_branch with API error."""
        mock_put.return_value = MockResponse({"message": "Conflict"}, 409)

        with self.assertRaises(SystemExit) as context:
            self.client.update_branch([self.pull_req])

        self.assertEqual(context.exception.code, 1)

    @patch("requests.put")
    @patch("builtins.print")
    def test_update_branch_multiple_prs(self, mock_print, mock_put):
        """Test updating multiple PRs."""
        pr2 = {**self.pull_req, "number": 124,
               "url": "https://api.github.com/repos/owner/repo/pulls/124"}

        mock_put.return_value = MockResponse({"message": "Updated"}, 202)

        self.client.update_branch([self.pull_req, pr2])

        self.assertEqual(mock_put.call_count, 2)

    @patch("requests.put")
    @patch("builtins.print")
    def test_update_branch_network_error(self, mock_print, mock_put):
        """Test update_branch with network error."""
        mock_put.side_effect = requests.exceptions.Timeout("Request timeout")

        with self.assertRaises(requests.exceptions.Timeout):
            self.client.update_branch([self.pull_req])


class TestGetLastComment(unittest.TestCase):
    """Test the get_last_comment method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pr_url = "https://api.github.com/repos/owner/repo/issues/123"

    @patch("requests.get")
    def test_get_last_comment_success(self, mock_get):
        """Test successful comment retrieval."""
        comments = [
            {"id": 1, "body": "First comment"},
            {"id": 2, "body": "Second comment"},
            {"id": 3, "body": "Last comment"}
        ]
        mock_get.return_value = MockResponse(comments, 200)

        result = self.client.get_last_comment(self.pr_url)

        self.assertEqual(result["body"], "Last comment")
        self.assertEqual(result["id"], 3)

    @patch("requests.get")
    def test_get_last_comment_empty(self, mock_get):
        """Test get_last_comment with no comments."""
        mock_get.return_value = MockResponse([], 200)

        result = self.client.get_last_comment(self.pr_url)
        self.assertIsNone(result)

    @patch("requests.get")
    def test_get_last_comment_api_error(self, mock_get):
        """Test get_last_comment with API error."""
        mock_get.return_value = MockResponse({"message": "Not Found"}, 404)

        result = self.client.get_last_comment(self.pr_url)
        self.assertIsNone(result)

    @patch("requests.get")
    def test_get_last_comment_with_pagination(self, mock_get):
        """Test get_last_comment with pagination."""
        # First request returns comments with pagination
        first_response = MockResponse(
            [{"id": 1, "body": "First comment"}],
            200,
            {"Link": '<https://api.github.com/repos/owner/repo/issues/123/comments?page=2>; rel="last"'}
        )

        # Last page request
        last_response = MockResponse([
            {"id": 50, "body": "Comment on last page"},
            {"id": 51, "body": "Very last comment"}
        ], 200)

        mock_get.side_effect = [first_response, last_response]

        result = self.client.get_last_comment(self.pr_url)

        self.assertEqual(result["body"], "Very last comment")
        self.assertEqual(result["id"], 51)
        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.get")
    def test_get_last_comment_pagination_error(self, mock_get):
        """Test get_last_comment when pagination request fails."""
        first_response = MockResponse(
            [{"id": 1, "body": "First comment"}],
            200,
            {"Link": '<https://api.github.com/repos/owner/repo/issues/123/comments?page=2>; rel="last"'}
        )

        mock_get.side_effect = [
            first_response,
            MockResponse({"message": "Server Error"}, 500)
        ]

        result = self.client.get_last_comment(self.pr_url)

        # Should return the first comment when last page fails
        self.assertEqual(result["body"], "First comment")

    @patch("requests.get")
    def test_get_last_comment_network_error(self, mock_get):
        """Test get_last_comment with network error."""
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Network error")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.client.get_last_comment(self.pr_url)


class TestGetMergeableState(unittest.TestCase):
    """Test the get_mergeable_state method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pr_url = "https://api.github.com/repos/owner/repo/pulls/123"

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_mergeable_state_success(self, mock_print, mock_get):
        """Test successful mergeable state retrieval."""
        states = ["clean", "dirty", "blocked", "behind", "unknown"]

        for state in states:
            with self.subTest(state=state):
                mock_get.return_value = MockResponse(
                    {"mergeable_state": state}, 200)

                result = self.client.get_mergeable_state(self.pr_url)
                self.assertEqual(result, state)

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_mergeable_state_api_error(self, mock_print, mock_get):
        """Test get_mergeable_state with API error."""
        mock_get.return_value = MockResponse({"message": "Not Found"}, 404)

        result = self.client.get_mergeable_state(self.pr_url)

        # Should return "unknown" on error
        self.assertEqual(result, "unknown")

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_mergeable_state_missing_field(self, mock_print, mock_get):
        """Test get_mergeable_state when mergeable_state field is missing."""
        mock_get.return_value = MockResponse({"state": "open"}, 200)

        result = self.client.get_mergeable_state(self.pr_url)

        # Should return "unknown" when field is missing
        self.assertEqual(result, "unknown")

    @patch("requests.get")
    @patch("builtins.print")
    def test_get_mergeable_state_network_error(self, mock_print, mock_get):
        """Test get_mergeable_state with network error."""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        result = self.client.get_mergeable_state(self.pr_url)
        self.assertEqual(result, "unknown")


class TestIsApproved(unittest.TestCase):
    """Test the is_approved method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "test_user")
        self.pr_url = "https://api.github.com/repos/owner/repo/pulls/123"

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_true(self, mock_print, mock_get):
        """Test is_approved returns True for approved PR."""
        reviews = [
            {"id": 1, "user": {"login": "other_user"}, "state": "COMMENTED"},
            {"id": 2, "user": {"login": "test_user"}, "state": "APPROVED"}
        ]
        mock_get.return_value = MockResponse(reviews, 200)

        result = self.client.is_approved(self.pr_url)
        self.assertTrue(result)

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_false(self, mock_print, mock_get):
        """Test is_approved returns False for rejected PR."""
        reviews = [
            {"id": 1, "user": {"login": "test_user"}, "state": "CHANGES_REQUESTED"}
        ]
        mock_get.return_value = MockResponse(reviews, 200)

        result = self.client.is_approved(self.pr_url)
        self.assertFalse(result)

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_dismissed(self, mock_print, mock_get):
        """Test is_approved returns 'Dismissed' for dismissed review."""
        reviews = [
            {"id": 1, "user": {"login": "test_user"}, "state": "DISMISSED"}
        ]
        mock_get.return_value = MockResponse(reviews, 200)

        result = self.client.is_approved(self.pr_url)
        self.assertEqual(result, "Dismissed")

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_no_reviews(self, mock_print, mock_get):
        """Test is_approved returns None when no reviews from user."""
        reviews = [
            {"id": 1, "user": {"login": "other_user"}, "state": "APPROVED"}
        ]
        mock_get.return_value = MockResponse(reviews, 200)

        result = self.client.is_approved(self.pr_url)
        self.assertIsNone(result)

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_empty_reviews(self, mock_print, mock_get):
        """Test is_approved with empty reviews list."""
        mock_get.return_value = MockResponse([], 200)

        result = self.client.is_approved(self.pr_url)
        self.assertIsNone(result)

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_api_error(self, mock_print, mock_get):
        """Test is_approved with API error."""
        mock_get.return_value = MockResponse({"message": "Forbidden"}, 403)

        result = self.client.is_approved(self.pr_url)
        self.assertIsNone(result)

    @patch("requests.get")
    @patch("builtins.print")
    def test_is_approved_multiple_reviews_latest_wins(self, mock_print, mock_get):
        """Test is_approved when user has multiple reviews - latest should win."""
        reviews = [
            {"id": 1, "user": {"login": "test_user"}, "state": "APPROVED"},
            {"id": 2, "user": {"login": "test_user"}, "state": "CHANGES_REQUESTED"},
            {"id": 3, "user": {"login": "test_user"}, "state": "APPROVED"}
        ]
        mock_get.return_value = MockResponse(reviews, 200)

        # Should return the last review state (APPROVED)
        result = self.client.is_approved(self.pr_url)
        self.assertTrue(result)


class TestApprove(unittest.TestCase):
    """Test the approve method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pr_url = "https://api.github.com/repos/owner/repo/pulls/123"

    @patch("requests.post")
    @patch("builtins.print")
    def test_approve_success(self, mock_print, mock_post):
        """Test successful PR approval."""
        mock_post.return_value = MockResponse({"id": 123}, 200)

        self.client.approve(self.pr_url)

        mock_post.assert_called_once_with(
            self.pr_url + "/reviews",
            headers=self.client.headers,
            json={"event": "APPROVE"},
            timeout=DEFAULT_TIMEOUT
        )
        mock_print.assert_called_with("PR Approved")

    @patch("requests.post")
    @patch("builtins.print")
    def test_approve_api_error(self, mock_print, mock_post):
        """Test approve with API error."""
        mock_post.return_value = MockResponse({"message": "Forbidden"}, 403)

        with self.assertRaises(SystemExit) as context:
            self.client.approve(self.pr_url)

        self.assertEqual(context.exception.code, 1)

    @patch("requests.post")
    @patch("builtins.print")
    def test_approve_network_error(self, mock_print, mock_post):
        """Test approve with network error."""
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Network error")

        # Should raise SystemExit which wraps the ConnectionError
        with self.assertRaises(SystemExit):
            self.client.approve(self.pr_url)


class TestCommentPullReq(unittest.TestCase):
    """Test the comment_pull_req method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pull_req = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "comments_url": "https://api.github.com/repos/owner/repo/issues/123/comments"
        }

    @patch("requests.post")
    @patch("builtins.print")
    def test_comment_pull_req_no_update(self, mock_print, mock_post):
        """Test commenting without update."""
        mock_post.return_value = MockResponse({"id": 456}, 201)

        self.client.comment_pull_req(
            [self.pull_req], "Test comment", update=False)

        mock_post.assert_called_once_with(
            self.pull_req["comments_url"],
            json={"body": "Test comment"},
            headers=self.client.headers,
            timeout=DEFAULT_TIMEOUT
        )

    @patch.object(GitHubClient, "get_mergeable_state")
    @patch.object(GitHubClient, "update_branch")
    @patch("requests.post")
    @patch("builtins.print")
    def test_comment_pull_req_with_update_behind(self, mock_print, mock_post, mock_update, mock_state):
        """Test commenting with update when PR is behind."""
        mock_post.return_value = MockResponse({"id": 456}, 201)
        # behind -> blocked after update
        mock_state.side_effect = ["behind", "blocked"]

        self.client.comment_pull_req(
            [self.pull_req], "Test comment", update=True)

        mock_update.assert_called_once_with([self.pull_req])
        mock_post.assert_called_once()

    @patch.object(GitHubClient, "get_mergeable_state")
    @patch("requests.post")
    @patch("builtins.print")
    def test_comment_pull_req_timeout(self, mock_print, mock_post, mock_state):
        """Test commenting when mergeable state times out."""
        mock_post.return_value = MockResponse({"id": 456}, 201)
        mock_state.return_value = "unknown"  # Always unknown, will timeout

        with patch("time.time") as mock_time:
            # Simulate timeout
            mock_time.side_effect = [0, MERGEABLE_STATE_TIMEOUT + 1]

            self.client.comment_pull_req(
                [self.pull_req], "Test comment", update=True)

        # Should still post comment even after timeout
        mock_post.assert_not_called()  # Skip PR due to timeout

    @patch("requests.post")
    @patch("builtins.print")
    def test_comment_pull_req_api_error(self, mock_print, mock_post):
        """Test commenting with API error."""
        mock_post.return_value = MockResponse({"message": "Bad Request"}, 400)

        # Should not raise exception, just print error
        self.client.comment_pull_req(
            [self.pull_req], "Test comment", update=False)

        mock_post.assert_called_once()


class TestMergePullReq(unittest.TestCase):
    """Test the merge_pull_req method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pull_req = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123"
        }

    @patch.object(GitHubClient, "get_mergeable_state")
    @patch.object(GitHubClient, "is_approved")
    @patch.object(GitHubClient, "approve")
    @patch("requests.put")
    @patch("builtins.print")
    def test_merge_pull_req_success(self, mock_print, mock_put, mock_approve_method, mock_is_approved, mock_state):
        """Test successful PR merge."""
        mock_state.side_effect = ["clean", "clean"]  # Ready to merge
        mock_is_approved.return_value = True
        mock_put.return_value = MockResponse({"merged": True}, 200)

        self.client.merge_pull_req([self.pull_req])

        mock_put.assert_called_once_with(
            self.pull_req["url"] + "/merge",
            headers=self.client.headers,
            json={"merge_method": "squash"},
            timeout=DEFAULT_TIMEOUT
        )
        mock_approve_method.assert_not_called()  # Already approved

    @patch.object(GitHubClient, "get_mergeable_state")
    @patch.object(GitHubClient, "is_approved")
    @patch.object(GitHubClient, "approve")
    @patch.object(GitHubClient, "update_branch")
    @patch("requests.put")
    @patch("builtins.print")
    def test_merge_pull_req_needs_approval_and_update(self, mock_print, mock_put, mock_update,
                                                      mock_approve_method, mock_is_approved, mock_state):
        """Test merge when PR needs approval and branch update."""
        mock_state.side_effect = [
            "behind", "clean"]  # Behind -> clean after update
        mock_is_approved.return_value = False
        mock_put.return_value = MockResponse({"merged": True}, 200)

        self.client.merge_pull_req([self.pull_req])

        mock_update.assert_called_once_with([self.pull_req])
        mock_approve_method.assert_called_once_with(self.pull_req["url"])
        mock_put.assert_called_once()

    @patch.object(GitHubClient, "get_mergeable_state")
    @patch("requests.put")
    @patch("builtins.print")
    def test_merge_pull_req_timeout(self, mock_print, mock_put, mock_state):
        """Test merge when mergeable state times out."""
        mock_state.return_value = "unknown"  # Always unknown

        with patch("time.time") as mock_time:
            mock_time.side_effect = [0, MERGEABLE_STATE_TIMEOUT + 1]

            self.client.merge_pull_req([self.pull_req])

        mock_put.assert_not_called()  # Should skip due to timeout

    @patch.object(GitHubClient, "get_mergeable_state")
    @patch.object(GitHubClient, "is_approved")
    @patch("requests.put")
    @patch("builtins.print")
    def test_merge_pull_req_api_error(self, mock_print, mock_put, mock_is_approved, mock_state):
        """Test merge with API error."""
        mock_state.return_value = "clean"
        mock_is_approved.return_value = True
        mock_put.return_value = MockResponse({"message": "Conflict"}, 409)

        with self.assertRaises(SystemExit) as context:
            self.client.merge_pull_req([self.pull_req])

        self.assertEqual(context.exception.code, 1)


class TestProcessDismissedPrs(unittest.TestCase):
    """Test the process_dismissed_prs method."""

    def setUp(self):
        self.client = GitHubClient("token", "owner", "user")
        self.pull_req = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123"
        }

    @patch.object(GitHubClient, "merge_pull_req")
    @patch.object(GitHubClient, "approve")
    @patch.object(GitHubClient, "get_last_comment")
    @patch("builtins.print")
    def test_process_dismissed_prs_no_changes(self, mock_print, mock_comment, mock_approve, mock_merge):
        """Test processing dismissed PR with no changes."""
        mock_comment.return_value = {
            "body": "No changes. Your infrastructure matches the configuration"}

        self.client.process_dismissed_prs([self.pull_req])

        mock_approve.assert_called_once_with(self.pull_req["url"])
        mock_merge.assert_called_once_with([self.pull_req])

    @patch.object(GitHubClient, "merge_pull_req")
    @patch.object(GitHubClient, "approve")
    @patch.object(GitHubClient, "get_last_comment")
    @patch("builtins.print")
    def test_process_dismissed_prs_with_changes(self, mock_print, mock_comment, mock_approve, mock_merge):
        """Test processing dismissed PR with changes."""
        mock_comment.return_value = {
            "body": "Plan: 1 to add, 0 to change, 0 to destroy."}

        self.client.process_dismissed_prs([self.pull_req])

        mock_approve.assert_called_once_with(self.pull_req["url"])
        mock_merge.assert_not_called()
