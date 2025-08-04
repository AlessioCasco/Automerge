import unittest
import sys
import os

# Add src directory to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils import (  # noqa: E402
    format_pr_info,
    format_api_error,
    is_mergeable_state_final,
    should_update_branch,
    is_clean_state,
    is_blocked_state,
    is_dirty_state,
    DEFAULT_TIMEOUT,
    MERGEABLE_STATE_TIMEOUT,
    COMMENT_DELAY,
    GITHUB_API_VERSION,
    GITHUB_ACCEPT_HEADER,
    MERGEABLE_STATE_UNKNOWN,
    MERGEABLE_STATE_BEHIND,
    MERGEABLE_STATE_BLOCKED,
    MERGEABLE_STATE_CLEAN,
    MERGEABLE_STATE_DIRTY,
    REVIEW_STATE_APPROVED,
    REVIEW_STATE_DISMISSED,
    LABEL_AUTOMERGE_IGNORE,
    LABEL_AUTOMERGE_NO_PROJECT,
    LABEL_AUTOMERGE_DISMISSED,
    LABEL_AUTOMERGE_CONFLICT,
    COMMENT_ATLANTIS_PLAN,
    COMMENT_ATLANTIS_UNLOCK,
    COMMENT_IGNORE_AUTOMERGE,
    COMMENT_CLOSE_NEW_VERSION,
    COMMENT_NO_PROJECT,
    MERGE_METHOD_SQUASH
)


class TestConstants(unittest.TestCase):
    """Test that all constants are properly defined."""

    def test_timeout_constants(self):
        """Test timeout constants are properly defined and reasonable."""
        self.assertIsInstance(DEFAULT_TIMEOUT, int)
        self.assertGreater(DEFAULT_TIMEOUT, 0)
        self.assertEqual(DEFAULT_TIMEOUT, 10)

        self.assertIsInstance(MERGEABLE_STATE_TIMEOUT, int)
        self.assertGreater(MERGEABLE_STATE_TIMEOUT, 0)
        self.assertEqual(MERGEABLE_STATE_TIMEOUT, 240)

        self.assertIsInstance(COMMENT_DELAY, int)
        self.assertGreater(COMMENT_DELAY, 0)
        self.assertEqual(COMMENT_DELAY, 4)

    def test_github_api_constants(self):
        """Test GitHub API constants are properly defined."""
        self.assertIsInstance(GITHUB_API_VERSION, str)
        self.assertEqual(GITHUB_API_VERSION, "2022-11-28")

        self.assertIsInstance(GITHUB_ACCEPT_HEADER, str)
        self.assertEqual(GITHUB_ACCEPT_HEADER, "application/vnd.github+json")

    def test_mergeable_state_constants(self):
        """Test mergeable state constants are properly defined."""
        self.assertEqual(MERGEABLE_STATE_UNKNOWN, "unknown")
        self.assertEqual(MERGEABLE_STATE_BEHIND, "behind")
        self.assertEqual(MERGEABLE_STATE_BLOCKED, "blocked")
        self.assertEqual(MERGEABLE_STATE_CLEAN, "clean")
        self.assertEqual(MERGEABLE_STATE_DIRTY, "dirty")

    def test_review_state_constants(self):
        """Test review state constants are properly defined."""
        self.assertEqual(REVIEW_STATE_APPROVED, "APPROVED")
        self.assertEqual(REVIEW_STATE_DISMISSED, "DISMISSED")

    def test_label_constants(self):
        """Test label constants are properly defined."""
        self.assertEqual(LABEL_AUTOMERGE_IGNORE, "automerge_ignore")
        self.assertEqual(LABEL_AUTOMERGE_NO_PROJECT, "automerge_no_project")
        self.assertEqual(LABEL_AUTOMERGE_DISMISSED, "automerge_dismissed")
        self.assertEqual(LABEL_AUTOMERGE_CONFLICT, "automerge_conflict")

    def test_comment_constants(self):
        """Test comment constants are properly defined."""
        self.assertEqual(COMMENT_ATLANTIS_PLAN, "atlantis plan")
        self.assertEqual(COMMENT_ATLANTIS_UNLOCK, "atlantis unlock")
        self.assertEqual(COMMENT_IGNORE_AUTOMERGE,
                         "This PR will be ignored by automerge")
        self.assertEqual(COMMENT_CLOSE_NEW_VERSION,
                         "This PR will be closed since there is a new version of this dependency")
        self.assertEqual(
            COMMENT_NO_PROJECT, "Will be ignored, 0 projects planned, usually due to modules update or no file changed, check and close them yourself please")

    def test_merge_method_constants(self):
        """Test merge method constants are properly defined."""
        self.assertEqual(MERGE_METHOD_SQUASH, "squash")


class TestFormatPrInfo(unittest.TestCase):
    """Test the format_pr_info function."""

    def test_format_pr_info_standard(self):
        """Test formatting PR info with standard data."""
        pr = {
            "number": 123,
            "head": {
                "repo": {
                    "name": "test-repo"
                }
            }
        }

        result = format_pr_info(pr)
        expected = "PR 123 in repo test-repo"
        self.assertEqual(result, expected)

    def test_format_pr_info_different_numbers(self):
        """Test formatting PR info with different PR numbers."""
        test_cases = [
            (1, "test-repo", "PR 1 in repo test-repo"),
            (999, "another-repo", "PR 999 in repo another-repo"),
            (12345, "long-repo-name", "PR 12345 in repo long-repo-name")
        ]

        for pr_number, repo_name, expected in test_cases:
            with self.subTest(pr_number=pr_number, repo_name=repo_name):
                pr = {
                    "number": pr_number,
                    "head": {
                        "repo": {
                            "name": repo_name
                        }
                    }
                }
                result = format_pr_info(pr)
                self.assertEqual(result, expected)

    def test_format_pr_info_special_characters(self):
        """Test formatting PR info with special characters in repo name."""
        pr = {
            "number": 456,
            "head": {
                "repo": {
                    "name": "repo-with-hyphens_and_underscores.dots"
                }
            }
        }

        result = format_pr_info(pr)
        expected = "PR 456 in repo repo-with-hyphens_and_underscores.dots"
        self.assertEqual(result, expected)

    def test_format_pr_info_unicode(self):
        """Test formatting PR info with unicode characters."""
        pr = {
            "number": 789,
            "head": {
                "repo": {
                    "name": "repo-with-unicode-🚀-chars"
                }
            }
        }

        result = format_pr_info(pr)
        expected = "PR 789 in repo repo-with-unicode-🚀-chars"
        self.assertEqual(result, expected)


class TestFormatApiError(unittest.TestCase):
    """Test the format_api_error function."""

    def test_format_api_error_standard(self):
        """Test formatting API error with standard inputs."""
        result = format_api_error(404, "Not Found")
        expected = "Status code: 404 \n Reason: Not Found"
        self.assertEqual(result, expected)

    def test_format_api_error_different_codes(self):
        """Test formatting API error with different status codes."""
        test_cases = [
            (200, "OK", "Status code: 200 \n Reason: OK"),
            (400, "Bad Request", "Status code: 400 \n Reason: Bad Request"),
            (401, "Unauthorized", "Status code: 401 \n Reason: Unauthorized"),
            (403, "Forbidden", "Status code: 403 \n Reason: Forbidden"),
            (500, "Internal Server Error",
             "Status code: 500 \n Reason: Internal Server Error"),
            (502, "Bad Gateway", "Status code: 502 \n Reason: Bad Gateway")
        ]

        for status_code, reason, expected in test_cases:
            with self.subTest(status_code=status_code, reason=reason):
                result = format_api_error(status_code, reason)
                self.assertEqual(result, expected)

    def test_format_api_error_json_response(self):
        """Test formatting API error with JSON response text."""
        json_response = '{"message": "Not Found", "documentation_url": "https://docs.github.com"}'
        result = format_api_error(404, json_response)
        expected = f"Status code: 404 \n Reason: {json_response}"
        self.assertEqual(result, expected)

    def test_format_api_error_empty_reason(self):
        """Test formatting API error with empty reason."""
        result = format_api_error(500, "")
        expected = "Status code: 500 \n Reason: "
        self.assertEqual(result, expected)

    def test_format_api_error_multiline_reason(self):
        """Test formatting API error with multiline reason."""
        multiline_reason = "Error occurred\nAdditional details\nMore info"
        result = format_api_error(400, multiline_reason)
        expected = f"Status code: 400 \n Reason: {multiline_reason}"
        self.assertEqual(result, expected)


class TestMergeableStateFunctions(unittest.TestCase):
    """Test mergeable state utility functions."""

    def test_is_mergeable_state_final(self):
        """Test is_mergeable_state_final function."""
        # Test unknown state (not final)
        self.assertFalse(is_mergeable_state_final("unknown"))

        # Test known states (final)
        final_states = ["behind", "blocked", "clean", "dirty"]
        for state in final_states:
            with self.subTest(state=state):
                self.assertTrue(is_mergeable_state_final(state))

    def test_is_mergeable_state_final_edge_cases(self):
        """Test is_mergeable_state_final with edge cases."""
        # Test empty string
        self.assertTrue(is_mergeable_state_final(""))

        # Test None (will raise TypeError, which is expected behavior)
        with self.assertRaises(TypeError):
            is_mergeable_state_final(None)

        # Test case sensitivity
        self.assertTrue(is_mergeable_state_final("UNKNOWN"))
        self.assertTrue(is_mergeable_state_final("Unknown"))

    def test_should_update_branch(self):
        """Test should_update_branch function."""
        # Test behind state (should update)
        self.assertTrue(should_update_branch("behind"))

        # Test other states (should not update)
        other_states = ["unknown", "blocked", "clean", "dirty"]
        for state in other_states:
            with self.subTest(state=state):
                self.assertFalse(should_update_branch(state))

    def test_should_update_branch_case_sensitivity(self):
        """Test should_update_branch with different cases."""
        # Test case sensitivity
        self.assertFalse(should_update_branch("BEHIND"))
        self.assertFalse(should_update_branch("Behind"))
        self.assertFalse(should_update_branch("behIND"))

    def test_is_clean_state(self):
        """Test is_clean_state function."""
        # Test clean state
        self.assertTrue(is_clean_state("clean"))

        # Test other states
        other_states = ["unknown", "behind", "blocked", "dirty"]
        for state in other_states:
            with self.subTest(state=state):
                self.assertFalse(is_clean_state(state))

    def test_is_clean_state_case_sensitivity(self):
        """Test is_clean_state with different cases."""
        # Test case sensitivity
        self.assertFalse(is_clean_state("CLEAN"))
        self.assertFalse(is_clean_state("Clean"))
        self.assertFalse(is_clean_state("cLEAN"))

    def test_is_blocked_state(self):
        """Test is_blocked_state function."""
        # Test blocked state
        self.assertTrue(is_blocked_state("blocked"))

        # Test other states
        other_states = ["unknown", "behind", "clean", "dirty"]
        for state in other_states:
            with self.subTest(state=state):
                self.assertFalse(is_blocked_state(state))

    def test_is_blocked_state_case_sensitivity(self):
        """Test is_blocked_state with different cases."""
        # Test case sensitivity
        self.assertFalse(is_blocked_state("BLOCKED"))
        self.assertFalse(is_blocked_state("Blocked"))
        self.assertFalse(is_blocked_state("bLOCKED"))

    def test_is_dirty_state(self):
        """Test is_dirty_state function."""
        # Test dirty state
        self.assertTrue(is_dirty_state("dirty"))

        # Test other states
        other_states = ["unknown", "behind", "blocked", "clean"]
        for state in other_states:
            with self.subTest(state=state):
                self.assertFalse(is_dirty_state(state))

    def test_is_dirty_state_case_sensitivity(self):
        """Test is_dirty_state with different cases."""
        # Test case sensitivity
        self.assertFalse(is_dirty_state("DIRTY"))
        self.assertFalse(is_dirty_state("Dirty"))
        self.assertFalse(is_dirty_state("dIRTY"))

    def test_all_state_functions_with_empty_string(self):
        """Test all state functions with empty string."""
        self.assertTrue(is_mergeable_state_final(""))
        self.assertFalse(should_update_branch(""))
        self.assertFalse(is_clean_state(""))
        self.assertFalse(is_blocked_state(""))
        self.assertFalse(is_dirty_state(""))

    def test_all_state_functions_with_invalid_state(self):
        """Test all state functions with invalid state."""
        invalid_state = "invalid_state"

        self.assertTrue(is_mergeable_state_final(invalid_state))
        self.assertFalse(should_update_branch(invalid_state))
        self.assertFalse(is_clean_state(invalid_state))
        self.assertFalse(is_blocked_state(invalid_state))
        self.assertFalse(is_dirty_state(invalid_state))


class TestFunctionReturnTypes(unittest.TestCase):
    """Test that functions return the expected types."""

    def test_format_pr_info_returns_string(self):
        """Test that format_pr_info returns a string."""
        pr = {
            "number": 123,
            "head": {
                "repo": {
                    "name": "test-repo"
                }
            }
        }
        result = format_pr_info(pr)
        self.assertIsInstance(result, str)

    def test_format_api_error_returns_string(self):
        """Test that format_api_error returns a string."""
        result = format_api_error(404, "Not Found")
        self.assertIsInstance(result, str)

    def test_state_functions_return_boolean(self):
        """Test that state functions return boolean values."""
        test_state = "clean"

        self.assertIsInstance(is_mergeable_state_final(test_state), bool)
        self.assertIsInstance(should_update_branch(test_state), bool)
        self.assertIsInstance(is_clean_state(test_state), bool)
        self.assertIsInstance(is_blocked_state(test_state), bool)
        self.assertIsInstance(is_dirty_state(test_state), bool)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_format_pr_info_missing_keys(self):
        """Test format_pr_info with missing dictionary keys."""
        # Missing number
        with self.assertRaises(KeyError):
            format_pr_info({"head": {"repo": {"name": "test"}}})

        # Missing head
        with self.assertRaises(KeyError):
            format_pr_info({"number": 123})

        # Missing repo
        with self.assertRaises(KeyError):
            format_pr_info({"number": 123, "head": {}})

        # Missing name
        with self.assertRaises(KeyError):
            format_pr_info({"number": 123, "head": {"repo": {}}})

    def test_format_pr_info_wrong_types(self):
        """Test format_pr_info with wrong data types."""
        # Number as string (should still work due to f-string formatting)
        pr = {
            "number": "123",
            "head": {
                "repo": {
                    "name": "test-repo"
                }
            }
        }
        result = format_pr_info(pr)
        self.assertEqual(result, "PR 123 in repo test-repo")

        # Name as number (should still work due to f-string formatting)
        pr = {
            "number": 123,
            "head": {
                "repo": {
                    "name": 456
                }
            }
        }
        result = format_pr_info(pr)
        self.assertEqual(result, "PR 123 in repo 456")

    def test_format_api_error_wrong_types(self):
        """Test format_api_error with wrong data types."""
        # Status code as string (should still work due to f-string formatting)
        result = format_api_error("404", "Not Found")
        self.assertEqual(result, "Status code: 404 \n Reason: Not Found")

        # Reason as number (should still work due to f-string formatting)
        result = format_api_error(404, 123)
        self.assertEqual(result, "Status code: 404 \n Reason: 123")


if __name__ == "__main__":
    unittest.main()
