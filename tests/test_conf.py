import os
import sys
import tempfile
import json
from unittest.mock import Mock

# Add src directory to path so tests can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestConstants:
    """Constants used across multiple test modules."""

    DEFAULT_ACCESS_TOKEN = "ghp_test_token_123"
    DEFAULT_OWNER = "test_owner"
    DEFAULT_GITHUB_USER = "test_user"
    DEFAULT_REPO_NAME = "test-repo"

    SAMPLE_PR_TITLE_DEPS = "[DEPENDENCIES] Update terraform"
    SAMPLE_PR_TITLE_DEPENDABOT = "[Dependabot] Bump package version"
    SAMPLE_PR_TITLE_OTHER = "Manual PR update"

    SAMPLE_COMMENT_NO_CHANGES = "No changes. Your infrastructure matches the configuration"
    SAMPLE_COMMENT_WITH_CHANGES = "Plan: 1 to add, 0 to change, 0 to destroy."
    SAMPLE_COMMENT_ERROR = "Plan Error: Invalid configuration"
    SAMPLE_COMMENT_STILL_WORKING = "atlantis plan is running..."
    SAMPLE_COMMENT_IGNORE = "This PR will be ignored by automerge"
    SAMPLE_COMMENT_NO_PROJECT = "Ran Plan for 0 projects"
    SAMPLE_COMMENT_NEW_VERSION = "A newer version of terraform is available"


class MockGitHubClient:
    """Mock GitHub client for testing."""

    def __init__(self, access_token=None, owner=None, github_user=None):
        self.access_token = access_token or TestConstants.DEFAULT_ACCESS_TOKEN
        self.owner = owner or TestConstants.DEFAULT_OWNER
        self.github_user = github_user or TestConstants.DEFAULT_GITHUB_USER
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.base_repos_url = f"https://api.github.com/repos/{self.owner}/"

        # Mock methods
        self.get_pull_requests = Mock(return_value=[])
        self.update_branch = Mock()
        self.get_last_comment = Mock(return_value=None)
        self.get_mergeable_state = Mock(return_value="clean")
        self.is_approved = Mock(return_value=True)
        self.approve = Mock()
        self.comment_pull_req = Mock()
        self.multi_comments_pull_req = Mock()
        self.set_label_to_pull_request = Mock()
        self.close_pull_requests = Mock()
        self.merge_pull_req = Mock()
        self.process_dismissed_prs = Mock()
        self.approve_all_prs = Mock()


class MockResponse:
    """Mock HTTP response for requests."""

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
            import requests
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class TestDataFactory:
    """Factory for creating test data objects."""

    @staticmethod
    def create_pull_request(number=123, title=None, repo_name=None, url=None, issue_url=None):
        """Create a sample pull request dictionary."""
        repo_name = repo_name or TestConstants.DEFAULT_REPO_NAME
        title = title or TestConstants.SAMPLE_PR_TITLE_DEPS
        base_url = f"https://api.github.com/repos/{TestConstants.DEFAULT_OWNER}/{repo_name}"

        return {
            "number": number,
            "title": title,
            "url": url or f"{base_url}/pulls/{number}",
            "issue_url": issue_url or f"{base_url}/issues/{number}",
            "comments_url": f"{base_url}/issues/{number}/comments",
            "head": {
                "repo": {
                    "name": repo_name
                }
            },
            "state": "open"
        }

    @staticmethod
    def create_comment(comment_id=1, body=None, user_login=None):
        """Create a sample comment dictionary."""
        return {
            "id": comment_id,
            "body": body or TestConstants.SAMPLE_COMMENT_NO_CHANGES,
            "user": {
                "login": user_login or TestConstants.DEFAULT_GITHUB_USER
            }
        }

    @staticmethod
    def create_review(review_id=1, state="APPROVED", user_login=None):
        """Create a sample review dictionary."""
        return {
            "id": review_id,
            "state": state,
            "user": {
                "login": user_login or TestConstants.DEFAULT_GITHUB_USER
            }
        }

    @staticmethod
    def create_config(access_token=None, owner=None, github_user=None, repos=None, filters=None):
        """Create a sample configuration dictionary."""
        return {
            "access_token": access_token or TestConstants.DEFAULT_ACCESS_TOKEN,
            "owner": owner or TestConstants.DEFAULT_OWNER,
            "github_user": github_user or TestConstants.DEFAULT_GITHUB_USER,
            "repos": repos or ["repo1", "repo2"],
            "filters": filters or ["^\\[DEPENDENCIES\\]", "^\\[Dependabot\\]"]
        }


class TempConfigFile:
    """Context manager for creating temporary config files."""

    def __init__(self, config_data=None):
        self.config_data = config_data or TestDataFactory.create_config()
        self.temp_file = None
        self.file_path = None

    def __enter__(self):
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False)
        json.dump(self.config_data, self.temp_file)
        self.temp_file.close()
        self.file_path = self.temp_file.name
        return self.file_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path and os.path.exists(self.file_path):
            os.unlink(self.file_path)


class TestFilters:
    """Common filter patterns for testing."""

    DEPENDENCIES_FILTER = "^\\[DEPENDENCIES\\]"
    DEPENDABOT_FILTER = "^\\[Dependabot\\]"
    RENOVATE_FILTER = "^Renovate"
    COMPLEX_DEPENDENCIES_FILTER = "^\\[DEPENDENCIES\\]\\s+Update\\s+\\w+"
    COMPLEX_DEPENDABOT_FILTER = "^\\[Dependabot\\].*bump.*version"

    @classmethod
    def get_default_filters(cls):
        """Get the default set of filters used in tests."""
        return [cls.DEPENDENCIES_FILTER, cls.DEPENDABOT_FILTER]

    @classmethod
    def get_complex_filters(cls):
        """Get complex regex filters for advanced testing."""
        return [
            cls.COMPLEX_DEPENDENCIES_FILTER,
            cls.COMPLEX_DEPENDABOT_FILTER,
            cls.RENOVATE_FILTER
        ]


class AssertionHelpers:
    """Helper methods for common test assertions."""

    @staticmethod
    def assert_pr_in_list(test_case, pr_list, pr_number):
        """Assert that a PR with specific number is in the list."""
        pr_numbers = [pr["number"] for pr in pr_list]
        test_case.assertIn(pr_number, pr_numbers)

    @staticmethod
    def assert_pr_not_in_list(test_case, pr_list, pr_number):
        """Assert that a PR with specific number is not in the list."""
        pr_numbers = [pr["number"] for pr in pr_list]
        test_case.assertNotIn(pr_number, pr_numbers)

    @staticmethod
    def assert_mock_called_with_pr(test_case, mock_method, pr):
        """Assert that a mock method was called with specific PR."""
        mock_method.assert_called()
        call_args = mock_method.call_args
        if call_args[0]:  # Positional arguments
            called_prs = call_args[0][0]
            if isinstance(called_prs, list):
                test_case.assertIn(pr, called_prs)
            else:
                test_case.assertEqual(pr, called_prs)

    @staticmethod
    def assert_headers_correct(test_case, client):
        """Assert that client headers are correctly formatted."""
        expected_headers = {
            "Authorization": f"Bearer {client.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        test_case.assertEqual(client.headers, expected_headers)


def create_sample_pr_scenarios():
    """Create a set of PRs representing different test scenarios."""
    return {
        "no_comments": TestDataFactory.create_pull_request(
            number=1, title="[DEPENDENCIES] Update terraform"
        ),
        "no_changes": TestDataFactory.create_pull_request(
            number=2, title="[Dependabot] Bump version"
        ),
        "with_diffs": TestDataFactory.create_pull_request(
            number=3, title="[DEPENDENCIES] Update ansible"
        ),
        "with_error": TestDataFactory.create_pull_request(
            number=4, title="[Dependabot] Security update"
        ),
        "to_be_closed": TestDataFactory.create_pull_request(
            number=5, title="[DEPENDENCIES] Old version"
        ),
        "dismissed": TestDataFactory.create_pull_request(
            number=6, title="[Dependabot] Previous version"
        ),
        "still_working": TestDataFactory.create_pull_request(
            number=7, title="[DEPENDENCIES] In progress"
        ),
        "ignore": TestDataFactory.create_pull_request(
            number=8, title="[DEPENDENCIES] Manual ignore"
        ),
        "no_project": TestDataFactory.create_pull_request(
            number=9, title="[DEPENDENCIES] Empty project"
        ),
        "no_match": TestDataFactory.create_pull_request(
            number=10, title="[DEPENDENCIES] Unknown state"
        )
    }


def get_sample_comment_scenarios():
    """Get sample comments for different PR states."""
    return {
        "no_changes": TestConstants.SAMPLE_COMMENT_NO_CHANGES,
        "with_changes": TestConstants.SAMPLE_COMMENT_WITH_CHANGES,
        "error": TestConstants.SAMPLE_COMMENT_ERROR,
        "still_working": TestConstants.SAMPLE_COMMENT_STILL_WORKING,
        "ignore": TestConstants.SAMPLE_COMMENT_IGNORE,
        "no_project": TestConstants.SAMPLE_COMMENT_NO_PROJECT,
        "new_version": TestConstants.SAMPLE_COMMENT_NEW_VERSION,
        "unknown": "Some comment that doesn't match any pattern"
    }


def setup_mock_github_responses():
    """Set up common mock responses for GitHub API calls."""
    return {
        "empty_prs": MockResponse([], 200),
        "single_pr": MockResponse([
            TestDataFactory.create_pull_request()
        ], 200),
        "multiple_prs": MockResponse([
            TestDataFactory.create_pull_request(
                1, TestConstants.SAMPLE_PR_TITLE_DEPS),
            TestDataFactory.create_pull_request(
                2, TestConstants.SAMPLE_PR_TITLE_DEPENDABOT),
            TestDataFactory.create_pull_request(
                3, TestConstants.SAMPLE_PR_TITLE_OTHER)
        ], 200),
        "api_error_404": MockResponse({"message": "Not Found"}, 404),
        "api_error_403": MockResponse({"message": "Forbidden"}, 403),
        "api_error_500": MockResponse({"message": "Internal Server Error"}, 500),
        "success_201": MockResponse({"id": 123, "message": "Created"}, 201),
        "success_202": MockResponse({"message": "Accepted"}, 202),
        "mergeable_clean": MockResponse({"mergeable_state": "clean"}, 200),
        "mergeable_dirty": MockResponse({"mergeable_state": "dirty"}, 200),
        "mergeable_behind": MockResponse({"mergeable_state": "behind"}, 200),
        "mergeable_blocked": MockResponse({"mergeable_state": "blocked"}, 200),
        "mergeable_unknown": MockResponse({"mergeable_state": "unknown"}, 200),
        "approved_review": MockResponse([
            TestDataFactory.create_review(state="APPROVED")
        ], 200),
        "dismissed_review": MockResponse([
            TestDataFactory.create_review(state="DISMISSED")
        ], 200),
        "no_reviews": MockResponse([], 200),
        "comments_with_no_changes": MockResponse([
            TestDataFactory.create_comment(
                body=TestConstants.SAMPLE_COMMENT_NO_CHANGES)
        ], 200),
        "comments_with_changes": MockResponse([
            TestDataFactory.create_comment(
                body=TestConstants.SAMPLE_COMMENT_WITH_CHANGES)
        ], 200),
        "no_comments": MockResponse([], 200)
    }


# Pytest fixtures would go here if using pytest instead of unittest
# For unittest, these utilities can be imported and used directly in test classes
