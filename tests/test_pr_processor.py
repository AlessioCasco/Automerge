import unittest
import sys
import os
from unittest.mock import Mock, patch

# Add src directory to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pr_processor import PRProcessor  # noqa: E402
from utils import (  # noqa: E402
    REVIEW_STATE_DISMISSED,
    LABEL_AUTOMERGE_IGNORE,
    LABEL_AUTOMERGE_NO_PROJECT,
    LABEL_AUTOMERGE_CONFLICT,
    COMMENT_ATLANTIS_PLAN,
    COMMENT_ATLANTIS_UNLOCK,
    COMMENT_IGNORE_AUTOMERGE,
    COMMENT_CLOSE_NEW_VERSION
)


class TestPRProcessorInit(unittest.TestCase):
    """Test PRProcessor initialization."""

    def test_init_with_github_client(self):
        """Test PRProcessor initialization with GitHubClient."""
        mock_client = Mock()
        processor = PRProcessor(mock_client)

        self.assertEqual(processor.github_client, mock_client)

        # Check that regex patterns are compiled
        self.assertIsNotNone(processor.regexp_pr_diff)
        self.assertIsNotNone(processor.regexp_pr_no_changes)
        self.assertIsNotNone(processor.regexp_pr_ignore)
        self.assertIsNotNone(processor.regexp_pr_error)
        self.assertIsNotNone(processor.regexp_pr_still_working)
        self.assertIsNotNone(processor.regexp_pr_no_project)
        self.assertIsNotNone(processor.regexp_new_version)

    def test_regex_patterns_compilation(self):
        """Test that all regex patterns are properly compiled."""
        mock_client = Mock()
        processor = PRProcessor(mock_client)

        # Test each regex pattern with sample text
        test_cases = [
            (processor.regexp_pr_diff,
             "Plan: 1 to add, 0 to change, 0 to destroy.", True),
            (processor.regexp_pr_diff, "Changes to Outputs", True),
            (processor.regexp_pr_diff, "No changes found", False),

            (processor.regexp_pr_no_changes,
             "No changes. Your infrastructure matches the configuration", True),
            (processor.regexp_pr_no_changes, "Apply complete!", True),
            (processor.regexp_pr_no_changes, "Plan: 1 to add", False),

            (processor.regexp_pr_ignore, "This PR will be ignored by automerge", True),
            (processor.regexp_pr_ignore, "This will be processed", False),

            (processor.regexp_pr_error, "Plan Error", True),
            (processor.regexp_pr_error, "Plan Failed", True),
            (processor.regexp_pr_error, "Apply Failed", True),
            (processor.regexp_pr_error, "Apply Error", True),
            (processor.regexp_pr_error, "Plan succeeded", False),

            (processor.regexp_pr_still_working, "atlantis plan", True),
            (processor.regexp_pr_still_working, "atlantis apply", True),
            (processor.regexp_pr_still_working, "atlantis unlock", False),

            (processor.regexp_pr_no_project, "Ran Plan for 0 projects", True),
            (processor.regexp_pr_no_project, "Ran Plan for 1 projects", False),

            (processor.regexp_new_version,
             "A newer version of terraform is available", True),
            (processor.regexp_new_version, "Current version is latest", False),
        ]

        for regex, text, should_match in test_cases:
            with self.subTest(regex=regex.pattern, text=text, should_match=should_match):
                result = bool(regex.search(text))
                self.assertEqual(result, should_match)


class TestCreatePRLists(unittest.TestCase):
    """Test the create_pr_lists method."""

    def setUp(self):
        self.mock_client = Mock()
        self.processor = PRProcessor(self.mock_client)

        self.sample_pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123",
            "head": {
                "repo": {
                    "name": "test-repo"
                }
            }
        }

    @patch("builtins.print")
    def test_create_pr_lists_dismissed_pr(self, mock_print):
        """Test categorizing dismissed PR."""
        self.mock_client.is_approved.return_value = REVIEW_STATE_DISMISSED

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(dismissed), 1)
        self.assertEqual(dismissed[0], self.sample_pr)
        self.assertEqual(len(no_comments), 0)
        self.assertEqual(len(with_diffs), 0)
        self.assertEqual(len(no_changes), 0)
        self.assertEqual(len(error), 0)
        self.assertEqual(len(to_be_closed), 0)

        self.mock_client.is_approved.assert_called_once_with(
            self.sample_pr["url"])
        mock_print.assert_called_once()

    @patch("builtins.print")
    def test_create_pr_lists_no_comments(self, mock_print):
        """Test categorizing PR with no comments."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = None

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(no_comments), 1)
        self.assertEqual(no_comments[0], self.sample_pr)
        self.assertEqual(len(dismissed), 0)

        self.mock_client.get_last_comment.assert_called_once_with(
            self.sample_pr["issue_url"])

    @patch("builtins.print")
    def test_create_pr_lists_no_changes(self, mock_print):
        """Test categorizing PR with no changes."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "No changes. Your infrastructure matches the configuration"
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(no_changes), 1)
        self.assertEqual(no_changes[0], self.sample_pr)

    @patch("builtins.print")
    def test_create_pr_lists_force_mode(self, mock_print):
        """Test categorizing PR in force mode."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "Plan: 1 to add, 0 to change, 0 to destroy."
        }

        result = self.processor.create_pr_lists(
            [self.sample_pr], True)  # force=True
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(no_comments), 1)
        self.assertEqual(no_comments[0], self.sample_pr)
        self.assertEqual(len(with_diffs), 0)

    @patch("builtins.print")
    def test_create_pr_lists_with_diffs(self, mock_print):
        """Test categorizing PR with diffs."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "Plan: 1 to add, 0 to change, 0 to destroy."
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(with_diffs), 1)
        self.assertEqual(with_diffs[0], self.sample_pr)

    @patch("builtins.print")
    def test_create_pr_lists_with_error(self, mock_print):
        """Test categorizing PR with error."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "Plan Error: Invalid configuration"
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(error), 1)
        self.assertEqual(error[0], self.sample_pr)

    @patch("builtins.print")
    def test_create_pr_lists_new_version(self, mock_print):
        """Test categorizing PR with new version available."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "A newer version of terraform is available"
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(to_be_closed), 1)
        self.assertEqual(to_be_closed[0], self.sample_pr)

    @patch("builtins.print")
    def test_create_pr_lists_still_working(self, mock_print):
        """Test categorizing PR where Atlantis is still working."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "atlantis plan is running..."
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        # PR should not be in any list when Atlantis is still working
        self.assertEqual(len(no_comments), 0)
        self.assertEqual(len(with_diffs), 0)
        self.assertEqual(len(no_changes), 0)
        self.assertEqual(len(error), 0)
        self.assertEqual(len(to_be_closed), 0)
        self.assertEqual(len(dismissed), 0)

    @patch("builtins.print")
    def test_create_pr_lists_ignore(self, mock_print):
        """Test categorizing PR that should be ignored."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "This PR will be ignored by automerge"
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        # PR should not be in any list when marked to ignore
        self.assertEqual(len(no_comments), 0)
        self.assertEqual(len(with_diffs), 0)
        self.assertEqual(len(no_changes), 0)
        self.assertEqual(len(error), 0)
        self.assertEqual(len(to_be_closed), 0)
        self.assertEqual(len(dismissed), 0)

    @patch("builtins.print")
    def test_create_pr_lists_no_project(self, mock_print):
        """Test categorizing PR with no projects."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "Ran Plan for 0 projects"
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        # PR should not be in any list, but should have label set
        self.assertEqual(len(no_comments), 0)
        self.mock_client.set_label_to_pull_request.assert_called_once_with(
            [self.sample_pr], LABEL_AUTOMERGE_NO_PROJECT)

    @patch("builtins.print")
    def test_create_pr_lists_no_match(self, mock_print):
        """Test categorizing PR that doesn't match any pattern."""
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "body": "Some unknown comment that doesn't match any pattern"
        }

        result = self.processor.create_pr_lists([self.sample_pr], False)
        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        # PR should not be in any list
        self.assertEqual(len(no_comments), 0)
        self.assertEqual(len(with_diffs), 0)
        self.assertEqual(len(no_changes), 0)
        self.assertEqual(len(error), 0)
        self.assertEqual(len(to_be_closed), 0)
        self.assertEqual(len(dismissed), 0)

        # Should print warning message
        mock_print.assert_called()
        self.assertIn("Not match, please check why", str(mock_print.call_args))

    def test_create_pr_lists_multiple_prs(self):
        """Test processing multiple PRs with different states."""
        pr1 = {**self.sample_pr, "number": 1}
        pr2 = {**self.sample_pr, "number": 2}
        pr3 = {**self.sample_pr, "number": 3}

        self.mock_client.is_approved.side_effect = [
            True, True, REVIEW_STATE_DISMISSED]
        self.mock_client.get_last_comment.side_effect = [
            None,  # pr1: no comments
            # pr2: no changes
            {"body": "No changes. Your infrastructure matches the configuration"},
            None   # pr3: won't be called due to dismissed state
        ]

        with patch("builtins.print"):
            result = self.processor.create_pr_lists([pr1, pr2, pr3], False)

        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(no_comments), 1)
        self.assertEqual(no_comments[0]["number"], 1)
        self.assertEqual(len(no_changes), 1)
        self.assertEqual(no_changes[0]["number"], 2)
        self.assertEqual(len(dismissed), 1)
        self.assertEqual(dismissed[0]["number"], 3)


class TestProcessPRs(unittest.TestCase):
    """Test the process_prs method."""

    def setUp(self):
        self.mock_client = Mock()
        self.processor = PRProcessor(self.mock_client)

        self.sample_pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123",
            "head": {
                "repo": {
                    "name": "test-repo"
                }
            }
        }

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_merge_no_changes(self, mock_print, mock_create_lists):
        """Test processing PRs with no changes - should merge."""
        mock_create_lists.return_value = ([], [], [self.sample_pr], [], [], [])

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.merge_pull_req.assert_called_once_with(
            [self.sample_pr])
        mock_print.assert_any_call("\nMerging what's possible\n")

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_process_dismissed(self, mock_print, mock_create_lists):
        """Test processing dismissed PRs."""
        mock_create_lists.return_value = ([], [], [], [], [], [self.sample_pr])

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.process_dismissed_prs.assert_called_once_with([
                                                                       self.sample_pr])
        mock_print.assert_any_call(
            "\nProcessing dismissed PRs - re-approving and checking for merging\n")

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_unlock_with_diffs(self, mock_print, mock_create_lists):
        """Test processing PRs with diffs - should unlock and ignore."""
        mock_create_lists.return_value = ([], [self.sample_pr], [], [], [], [])

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.multi_comments_pull_req.assert_called_once_with(
            [self.sample_pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
        self.mock_client.set_label_to_pull_request.assert_called_once_with(
            [self.sample_pr], LABEL_AUTOMERGE_IGNORE)
        mock_print.assert_any_call("\nUnlocking PR\n")

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_plan_no_comments(self, mock_print, mock_create_lists):
        """Test processing PRs with no comments - should plan."""
        mock_create_lists.return_value = ([self.sample_pr], [], [], [], [], [])
        self.mock_client.get_mergeable_state.return_value = "clean"

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.get_mergeable_state.assert_called_once_with(
            self.sample_pr["url"])
        self.mock_client.comment_pull_req.assert_called_once_with(
            [self.sample_pr], COMMENT_ATLANTIS_PLAN)
        mock_print.assert_any_call("\n\nCommenting to plan PRs\n")

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_plan_error(self, mock_print, mock_create_lists):
        """Test processing PRs with errors - should plan."""
        mock_create_lists.return_value = ([], [], [], [self.sample_pr], [], [])
        self.mock_client.get_mergeable_state.return_value = "clean"

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.comment_pull_req.assert_called_once_with(
            [self.sample_pr], COMMENT_ATLANTIS_PLAN)

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_dirty_state(self, mock_print, mock_create_lists):
        """Test processing PR with dirty state - should ignore with conflict label."""
        mock_create_lists.return_value = ([self.sample_pr], [], [], [], [], [])
        self.mock_client.get_mergeable_state.return_value = "dirty"

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.multi_comments_pull_req.assert_called_once_with(
            [self.sample_pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
        self.mock_client.set_label_to_pull_request.assert_called_once_with(
            [self.sample_pr], LABEL_AUTOMERGE_CONFLICT)
        # Should not call comment_pull_req for planning
        self.mock_client.comment_pull_req.assert_not_called()

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_close_old_prs(self, mock_print, mock_create_lists):
        """Test processing PRs to be closed."""
        mock_create_lists.return_value = ([], [], [], [], [self.sample_pr], [])

        self.processor.process_prs([self.sample_pr], False)

        self.mock_client.multi_comments_pull_req.assert_called_once_with(
            [self.sample_pr], COMMENT_CLOSE_NEW_VERSION, COMMENT_ATLANTIS_UNLOCK)
        self.mock_client.close_pull_requests.assert_called_once_with([
                                                                     self.sample_pr])
        mock_print.assert_any_call("\nClosing old PRs\n")

    @patch.object(PRProcessor, "create_pr_lists")
    @patch("builtins.print")
    def test_process_prs_mixed_scenarios(self, mock_print, mock_create_lists):
        """Test processing multiple PRs with mixed scenarios."""
        pr1 = {**self.sample_pr, "number": 1}
        pr2 = {**self.sample_pr, "number": 2}
        pr3 = {**self.sample_pr, "number": 3}
        pr4 = {**self.sample_pr, "number": 4}

        mock_create_lists.return_value = (
            [pr1],        # no_comments
            [pr2],        # with_diffs
            [pr3],        # no_changes
            [],           # error
            [pr4],        # to_be_closed
            []            # dismissed
        )
        self.mock_client.get_mergeable_state.return_value = "clean"

        self.processor.process_prs([pr1, pr2, pr3, pr4], False)

        # Verify all operations were called
        self.mock_client.merge_pull_req.assert_called_once_with([pr3])
        self.mock_client.multi_comments_pull_req.assert_any_call(
            [pr2], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
        self.mock_client.multi_comments_pull_req.assert_any_call(
            [pr4], COMMENT_CLOSE_NEW_VERSION, COMMENT_ATLANTIS_UNLOCK)
        self.mock_client.comment_pull_req.assert_called_once_with(
            [pr1], COMMENT_ATLANTIS_PLAN)
        self.mock_client.close_pull_requests.assert_called_once_with([pr4])

    @patch.object(PRProcessor, "create_pr_lists")
    def test_process_prs_empty_lists(self, mock_create_lists):
        """Test processing with all empty lists."""
        mock_create_lists.return_value = ([], [], [], [], [], [])

        # Should not raise any exceptions
        self.processor.process_prs([], False)

        # Verify no operations were called
        self.mock_client.merge_pull_req.assert_not_called()
        self.mock_client.process_dismissed_prs.assert_not_called()
        self.mock_client.multi_comments_pull_req.assert_not_called()
        self.mock_client.comment_pull_req.assert_not_called()
        self.mock_client.close_pull_requests.assert_not_called()


class TestPRProcessorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        self.mock_client = Mock()
        self.processor = PRProcessor(self.mock_client)

    def test_create_pr_lists_empty_input(self):
        """Test create_pr_lists with empty input."""
        with patch("builtins.print"):
            result = self.processor.create_pr_lists([], False)

        no_comments, with_diffs, no_changes, error, to_be_closed, dismissed = result

        self.assertEqual(len(no_comments), 0)
        self.assertEqual(len(with_diffs), 0)
        self.assertEqual(len(no_changes), 0)
        self.assertEqual(len(error), 0)
        self.assertEqual(len(to_be_closed), 0)
        self.assertEqual(len(dismissed), 0)

    def test_create_pr_lists_client_exception(self):
        """Test create_pr_lists when GitHubClient methods raise exceptions."""
        sample_pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123",
            "head": {"repo": {"name": "test-repo"}}
        }

        self.mock_client.is_approved.side_effect = Exception("API Error")

        with self.assertRaises(Exception):
            self.processor.create_pr_lists([sample_pr], False)

    def test_process_prs_client_exception(self):
        """Test process_prs when GitHubClient methods raise exceptions."""
        sample_pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123",
            "head": {"repo": {"name": "test-repo"}}
        }

        with patch.object(self.processor, "create_pr_lists") as mock_create_lists:
            mock_create_lists.return_value = ([], [], [sample_pr], [], [], [])
            self.mock_client.merge_pull_req.side_effect = Exception(
                "Merge failed")

            with self.assertRaises(Exception):
                self.processor.process_prs([sample_pr], False)

    @patch("builtins.print")
    def test_comment_body_none(self, mock_print):
        """Test handling when comment body is None."""
        sample_pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123",
            "head": {"repo": {"name": "test-repo"}}
        }

        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {"body": None}

        # Should handle None body gracefully - treating None as empty string should not match patterns
        with self.assertRaises(TypeError):
            # The regex search will fail on None, which is expected behavior
            self.processor.create_pr_lists([sample_pr], False)

    @patch("builtins.print")
    def test_comment_missing_body_key(self, mock_print):
        """Test handling when comment doesn't have body key."""
        sample_pr = {
            "number": 123,
            "url": "https://api.github.com/repos/owner/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/owner/repo/issues/123",
            "head": {"repo": {"name": "test-repo"}}
        }

        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.return_value = {
            "id": 12345}  # No body key

        # Should raise KeyError when trying to access body
        with self.assertRaises(KeyError):
            self.processor.create_pr_lists([sample_pr], False)


class TestPRProcessorIntegration(unittest.TestCase):
    """Integration tests for PRProcessor."""

    def setUp(self):
        self.mock_client = Mock()
        self.processor = PRProcessor(self.mock_client)

    @patch("builtins.print")
    def test_full_workflow_typical_scenario(self, mock_print):
        """Test full workflow with typical scenario."""
        # Create PRs representing different states
        pr_no_comment = {
            "number": 1, "url": "url1", "issue_url": "issue1",
            "head": {"repo": {"name": "repo1"}}
        }
        pr_no_changes = {
            "number": 2, "url": "url2", "issue_url": "issue2",
            "head": {"repo": {"name": "repo2"}}
        }
        pr_with_diffs = {
            "number": 3, "url": "url3", "issue_url": "issue3",
            "head": {"repo": {"name": "repo3"}}
        }

        all_prs = [pr_no_comment, pr_no_changes, pr_with_diffs]

        # Mock client responses
        self.mock_client.is_approved.return_value = True
        self.mock_client.get_last_comment.side_effect = [
            None,  # pr1: no comment
            # pr2: no changes
            {"body": "No changes. Your infrastructure matches the configuration"},
            {"body": "Plan: 1 to add, 0 to change, 0 to destroy."}  # pr3: diffs
        ]
        self.mock_client.get_mergeable_state.return_value = "clean"

        # Execute
        self.processor.process_prs(all_prs, False)

        # Verify expected calls
        self.mock_client.merge_pull_req.assert_called_once_with([
                                                                pr_no_changes])
        self.mock_client.comment_pull_req.assert_called_once_with(
            [pr_no_comment], COMMENT_ATLANTIS_PLAN)
        self.mock_client.multi_comments_pull_req.assert_called_once_with(
            [pr_with_diffs], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
        self.mock_client.set_label_to_pull_request.assert_called_once_with(
            [pr_with_diffs], LABEL_AUTOMERGE_IGNORE)


if __name__ == "__main__":
    unittest.main()
