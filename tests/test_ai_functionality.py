#!/usr/bin/env python3
"""
Unified AI functionality tests for the automerge tool.
Tests AI confidence score calculation, multi-provider support, and related features.
"""

import unittest
import os
from unittest.mock import Mock, patch
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ai_confidence import AIConfidenceCalculator
from pr_processor import PRProcessor
from github_client import GitHubClient


class TestAIFunctionality(unittest.TestCase):
    """Test suite for AI functionality including confidence score calculation and multi-provider support."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_pr_data = {
            "title": "[DEPENDENCIES] Update Terraform provider",
            "body": "This PR updates the Terraform provider to version 5.7.0",
            "head": {"repo": {"name": "terraform-ops"}},
            "base": {"ref": "master"},
            "labels": [{"name": "dependencies"}],
            "issue_url": "https://api.github.com/repos/test/repo/issues/123"
        }

        self.github_config = {
            "access_token": "test_token",
            "enable_ai_confidence_score": True,
            "ai_provider": "github",
            "disable_pr_comments": False,
            "ai_repos": ["terraform-ops", "terraform-k8s"],
            "ai_config": {
                "github": {
                    "api_base": "http://localhost:4141",
                    "model": "claude-sonnet-4"
                },
                "claude-code": {
                    "api_base": "https://api.anthropic.com",
                    "api_key": "test_key",
                    "model": "claude-sonnet-4"
                }
            }
        }

        self.claude_config = {
            "access_token": "test_token",
            "enable_ai_confidence_score": True,
            "ai_provider": "claude-code",
            "disable_pr_comments": False,
            "ai_repos": ["terraform-ops", "terraform-k8s"],
            "ai_config": {
                "github": {
                    "api_base": "http://localhost:4141",
                    "model": "claude-sonnet-4"
                },
                "claude-code": {
                    "api_base": "https://api.anthropic.com",
                    "api_key": "test_key",
                    "model": "claude-sonnet-4"
                }
            }
        }

    def test_ai_calculator_initialization(self):
        """Test AI calculator initialization with different providers."""
        # Test GitHub provider
        calculator = AIConfidenceCalculator("test_token", None, self.github_config)
        self.assertEqual(calculator.ai_config.get("ai_provider"), "github")

        # Test Claude provider
        calculator = AIConfidenceCalculator("test_token", None, self.claude_config)
        self.assertEqual(calculator.ai_config.get("ai_provider"), "claude-code")

    @patch("ai_confidence.requests.post")
    def test_github_copilot_api_call(self, mock_post):
        """Test GitHub Copilot API call via proxy."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 85% - EXPLANATION\nThis is a safe update"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }
        mock_post.return_value = mock_response

        calculator = AIConfidenceCalculator("test_token", None, self.github_config)
        response, metadata = calculator._call_github_copilot_with_metadata("test prompt")

        self.assertIsNotNone(response)
        self.assertEqual(metadata["provider"], "GitHub Copilot")
        self.assertEqual(metadata["model"], "claude-sonnet-4")
        self.assertEqual(metadata["input_tokens"], 100)
        self.assertEqual(metadata["output_tokens"], 50)

    @patch("ai_confidence.requests.post")
    def test_claude_code_api_call(self, mock_post):
        """Test Claude Code API call."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 90% - EXPLANATION\nThis is a very safe update"}],
            "usage": {"input_tokens": 150, "output_tokens": 75}
        }
        mock_post.return_value = mock_response

        calculator = AIConfidenceCalculator("test_token", None, self.claude_config)
        response, metadata = calculator._call_claude_code_with_metadata("test prompt")

        self.assertIsNotNone(response)
        self.assertEqual(metadata["provider"], "Claude Code")
        self.assertEqual(metadata["model"], "claude-sonnet-4")
        self.assertEqual(metadata["input_tokens"], 150)
        self.assertEqual(metadata["output_tokens"], 75)

    @patch("ai_confidence.requests.post")
    def test_ai_response_parsing(self, mock_post):
        """Test AI response parsing with different formats."""
        # Test with "EXPLANATION" keyword
        response_text = "SCORE: 85% - EXPLANATION\nThis is a safe update"
        calculator = AIConfidenceCalculator("test_token", None, self.github_config)
        score, explanation = calculator._parse_ai_response(response_text)

        self.assertEqual(score, 85)
        self.assertIn("safe update", explanation)

        # Test without "EXPLANATION" keyword
        response_text = "SCORE: 90% - This is a very safe update"
        score, explanation = calculator._parse_ai_response(response_text)

        self.assertEqual(score, 90)
        self.assertIn("very safe update", explanation)

    def test_environment_detection(self):
        """Test development vs production environment detection."""
        calculator = AIConfidenceCalculator("test_token", None, self.github_config)

        # Test development environment
        dev_pr = self.sample_pr_data.copy()
        dev_pr["head"]["ref"] = "feature/new-feature"
        dev_pr["base"]["ref"] = "develop"

        is_dev = calculator._is_development_environment(dev_pr)
        self.assertTrue(is_dev)

        # Test production environment
        prod_pr = self.sample_pr_data.copy()
        prod_pr["head"]["ref"] = "hotfix/critical-fix"
        prod_pr["base"]["ref"] = "main"

        is_dev = calculator._is_development_environment(prod_pr)
        self.assertFalse(is_dev)

    @patch("ai_confidence.requests.post")
    def test_confidence_score_calculation_with_metadata(self, mock_post):
        """Test confidence score calculation with metadata."""
        # Mock successful AI response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 85% - EXPLANATION\nThis is a safe update"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }
        mock_post.return_value = mock_response

        # Mock GitHub client for terraform plan extraction
        mock_github_client = Mock()
        mock_github_client.get_last_terraform_plan.return_value = "No changes. Your infrastructure matches the configuration"

        calculator = AIConfidenceCalculator("test_token", mock_github_client, self.github_config)
        score, explanation, is_dev, metadata = calculator.calculate_confidence_score(self.sample_pr_data)

        self.assertEqual(score, 85)
        self.assertIsInstance(explanation, str)
        self.assertIsInstance(is_dev, bool)
        self.assertIsInstance(metadata, dict)
        self.assertIn("provider", metadata)
        self.assertIn("model", metadata)
        self.assertIn("input_tokens", metadata)
        self.assertIn("output_tokens", metadata)

    def test_fallback_confidence_calculation(self):
        """Test fallback confidence calculation when AI is unavailable."""
        calculator = AIConfidenceCalculator("test_token", None, self.github_config)

        # Test with dependency update
        dep_pr = self.sample_pr_data.copy()
        dep_pr["title"] = "[DEPENDENCIES] Update provider"

        score, explanation, is_dev = calculator._fallback_confidence_calculation(
            dep_pr, "No changes. Your infrastructure matches the configuration", True
        )

        self.assertGreater(score, 50)  # Should be higher for dependency updates
        self.assertIsInstance(explanation, str)
        self.assertTrue(is_dev)

    def test_auto_merge_logic(self):
        """Test auto-merge decision logic."""
        calculator = AIConfidenceCalculator("test_token", None, self.github_config)

        # Test auto-merge conditions
        should_merge = calculator.should_auto_merge(100, True, True)  # 100% confidence, dev env, enabled
        self.assertTrue(should_merge)

        should_merge = calculator.should_auto_merge(85, True, True)  # 85% confidence, dev env, enabled
        self.assertFalse(should_merge)

        should_merge = calculator.should_auto_merge(100, False, True)  # 100% confidence, prod env, enabled
        self.assertFalse(should_merge)

        should_merge = calculator.should_auto_merge(100, True, False)  # 100% confidence, dev env, disabled
        self.assertFalse(should_merge)

    @patch("ai_confidence.requests.post")
    def test_error_handling(self, mock_post):
        """Test error handling in AI calls."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        calculator = AIConfidenceCalculator("test_token", None, self.github_config)
        response, metadata = calculator._call_github_copilot_with_metadata("test prompt")

        self.assertIsNone(response)
        self.assertEqual(metadata["provider"], "GitHub Copilot")
        self.assertEqual(metadata["input_tokens"], 0)
        self.assertEqual(metadata["output_tokens"], 0)

    def test_pr_context_extraction(self):
        """Test PR context extraction for AI analysis."""
        calculator = AIConfidenceCalculator("test_token", None, self.github_config)
        context = calculator._extract_pr_context(self.sample_pr_data)

        self.assertIn("PR Title", context)
        self.assertIn("PR Description", context)
        self.assertIn("Repository", context)
        self.assertIn("Base Branch", context)
        self.assertIn("Head Branch", context)
        self.assertIn("Labels", context)

    @patch("ai_confidence.requests.post")
    def test_ssl_verification_disabled(self, mock_post):
        """Test SSL verification can be disabled for development."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 85% - EXPLANATION\nTest"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }
        mock_post.return_value = mock_response

        # Set environment variable to disable SSL verification
        os.environ["DISABLE_SSL_VERIFY"] = "true"

        try:
            calculator = AIConfidenceCalculator("test_token", None, self.claude_config)
            response, metadata = calculator._call_claude_code_with_metadata("test prompt")

            # Verify that verify=False was passed to requests.post
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertIn("verify", call_args[1])
            self.assertFalse(call_args[1]["verify"])

        finally:
            # Clean up environment variable
            os.environ.pop("DISABLE_SSL_VERIFY", None)

    def test_unknown_provider_handling(self):
        """Test handling of unknown AI provider."""
        config_with_unknown = self.github_config.copy()
        config_with_unknown["ai_provider"] = "unknown-provider"

        calculator = AIConfidenceCalculator("test_token", None, config_with_unknown)
        response, metadata = calculator._call_ai_provider_with_metadata("test prompt")

        self.assertIsNone(response)
        self.assertEqual(metadata["provider"], "unknown")
        self.assertEqual(metadata["model"], "none")

    def test_missing_api_key_handling(self):
        """Test handling of missing API key for Claude Code."""
        config_without_key = self.claude_config.copy()
        config_without_key["ai_config"]["claude-code"]["api_key"] = None

        calculator = AIConfidenceCalculator("test_token", None, config_without_key)
        response, metadata = calculator._call_claude_code_with_metadata("test prompt")

        self.assertIsNone(response)
        self.assertEqual(metadata["provider"], "Claude Code")
        self.assertEqual(metadata["input_tokens"], 0)
        self.assertEqual(metadata["output_tokens"], 0)


class TestPRProcessorAI(unittest.TestCase):
    """Test PR processor AI integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "access_token": "test_token",
            "enable_ai_confidence_score": True,
            "ai_provider": "github",
            "ai_repos": ["terraform-ops", "terraform-k8s"],
            "ai_config": {
                "github": {
                    "api_base": "http://localhost:4141",
                    "model": "claude-sonnet-4"
                }
            }
        }

        self.github_client = Mock(spec=GitHubClient)
        self.pr_processor = PRProcessor(self.github_client, self.config)

    @patch("ai_confidence.requests.post")
    def test_ai_comment_generation(self, mock_post):
        """Test AI comment generation with metadata."""
        # Mock successful AI response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 85% - EXPLANATION\nThis is a safe update"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }
        mock_post.return_value = mock_response

        # Mock GitHub client methods
        self.github_client.comment_pull_req = Mock()
        self.github_client.get_last_terraform_plan = Mock(return_value="No changes. Your infrastructure matches the configuration")

        pr_data = {
            "title": "[DEPENDENCIES] Update provider",
            "body": "Safe update",
            "head": {"repo": {"name": "test-repo"}},
            "base": {"ref": "develop"},
            "labels": [],
            "number": 123,
            "issue_url": "https://api.github.com/repos/test/repo/issues/123"
        }

        self.pr_processor._add_confidence_score_comment(pr_data)

        # Verify comment was posted with metadata
        self.github_client.comment_pull_req.assert_called_once()
        comment = self.github_client.comment_pull_req.call_args[0][1]

        self.assertIn("AI Provider", comment)
        self.assertIn("Token Usage", comment)
        self.assertIn("GitHub Copilot", comment)
        self.assertIn("claude-sonnet-4", comment)

    def test_disable_pr_comments_functionality(self):
        """Test that PR comments can be disabled and analysis is printed to terminal only."""
        # Mock successful AI response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 85% - EXPLANATION\nThis is a safe update"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }

        # Create config with comments disabled
        config_with_disabled_comments = self.config.copy()
        config_with_disabled_comments["disable_pr_comments"] = True

        with patch("ai_confidence.requests.post") as mock_post:
            mock_post.return_value = mock_response

            # Mock GitHub client methods
            self.github_client.comment_pull_req = Mock()
            self.github_client.get_last_terraform_plan = Mock(return_value="No changes. Your infrastructure matches the configuration")

            pr_data = {
                "title": "[DEPENDENCIES] Update provider",
                "body": "Safe update",
                "head": {"repo": {"name": "test-repo"}},
                "base": {"ref": "develop"},
                "labels": [],
                "number": 123,
                "issue_url": "https://api.github.com/repos/test/repo/issues/123"
            }

            # Create processor with disabled comments
            processor = PRProcessor(self.github_client, config_with_disabled_comments)
            processor._add_confidence_score_comment(pr_data)

            # Verify comment was NOT posted to PR
            self.github_client.comment_pull_req.assert_not_called()

            # Verify that the analysis was still performed (printed to terminal)
            # The print statements are captured by the test framework
            # We can verify the mock was called to ensure AI analysis happened
            mock_post.assert_called_once()

    def test_ai_failure_comment_functionality(self):
        """Test AI failure comment generation when AI analysis cannot be performed."""
        # Mock GitHub client methods
        self.github_client.comment_pull_req = Mock()

        pr_data = {
            "title": "[DEPENDENCIES] Update provider",
            "body": "Safe update",
            "head": {"repo": {"name": "test-repo"}},
            "base": {"ref": "develop"},
            "labels": [],
            "number": 123,
            "issue_url": "https://api.github.com/repos/test/repo/issues/123"
        }

        # Test AI failure comment
        self.pr_processor._add_ai_failure_comment(
            pr_data,
            "No Terraform plan found",
            "Atlantis has not yet generated a plan for this PR.",
            "Wait for Atlantis to complete the plan."
        )

        # Verify comment was posted
        self.github_client.comment_pull_req.assert_called_once()
        comment = self.github_client.comment_pull_req.call_args[0][1]

        self.assertIn("AI Analysis Failed", comment)
        self.assertIn("No Terraform plan found", comment)
        self.assertIn("Wait for Atlantis to complete the plan", comment)

    def test_ai_integration_in_pr_with_diffs(self):
        """Test AI integration in PR with diffs processing."""
        # Mock successful AI response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "content": [{"text": "SCORE: 100% - EXPLANATION\nThis is a safe update"}],
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }

        # Mock GitHub client methods
        self.github_client.get_last_comment = Mock(return_value={"body": "Changes to Outputs"})
        self.github_client.get_last_terraform_plan = Mock(return_value="Plan: 0 to add, 1 to change, 0 to destroy")
        self.github_client.merge_pull_req = Mock()
        self.github_client.multi_comments_pull_req = Mock()
        self.github_client.is_approved = Mock(return_value=None)

        pr_data = {
            "title": "[DEPENDENCIES] Update provider",
            "body": "Safe update",
            "head": {"repo": {"name": "terraform-ops"}},
            "base": {"ref": "feature/test"},
            "labels": [],
            "number": 123,
            "url": "https://api.github.com/repos/test/repo/pulls/123",
            "issue_url": "https://api.github.com/repos/test/repo/issues/123"
        }

        with patch("ai_confidence.requests.post") as mock_post:
            mock_post.return_value = mock_response

            # Test AI integration in PR with diffs
            self.pr_processor.process_prs([pr_data], False)

            # Verify AI analysis was performed (terraform plan was retrieved)
            self.github_client.get_last_terraform_plan.assert_called()
            # Verify standard unlock was called (since auto-merge didn't happen due to production env)
            self.github_client.multi_comments_pull_req.assert_called_once()


if __name__ == "__main__":
    unittest.main()
