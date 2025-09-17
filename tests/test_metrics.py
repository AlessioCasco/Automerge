#!/usr/bin/env python3
"""
Tests for metrics functionality.
"""

import unittest
from unittest.mock import Mock, patch

from src.metrics import AutomergeMetrics


class TestAutomergeMetrics(unittest.TestCase):
    """Test cases for AutomergeMetrics class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pushgateway_url = "http://test-pushgateway:9091"
        self.metrics = AutomergeMetrics(self.pushgateway_url, job_name="test-automerge")

    def test_init_with_pushgateway(self):
        """Test initialization with pushgateway URL."""
        metrics = AutomergeMetrics(self.pushgateway_url, job_name="test-job")
        self.assertEqual(metrics.pushgateway_url, self.pushgateway_url)
        self.assertEqual(metrics.job_name, "test-job")
        self.assertIsNotNone(metrics.registry)
        self.assertIsNotNone(metrics.input_tokens_gauge)
        self.assertIsNotNone(metrics.output_tokens_gauge)

    def test_init_without_pushgateway(self):
        """Test initialization without pushgateway URL."""
        metrics = AutomergeMetrics(None, job_name="test-job")
        self.assertIsNone(metrics.pushgateway_url)
        self.assertEqual(metrics.job_name, "test-job")
        self.assertIsNotNone(metrics.registry)

    def test_record_token_usage(self):
        """Test recording token usage metrics."""
        repo = "test-repo"
        model = "claude-sonnet-4"
        engine = "claude-code"
        input_tokens = 100
        output_tokens = 50

        # Mock the gauge labels method
        with patch.object(self.metrics.input_tokens_gauge, "labels") as mock_input_labels, \
             patch.object(self.metrics.output_tokens_gauge, "labels") as mock_output_labels:

            mock_input_labels.return_value.set = Mock()
            mock_output_labels.return_value.set = Mock()

            self.metrics.record_token_usage(repo, model, engine, input_tokens, output_tokens)

            # Verify input tokens gauge was called
            mock_input_labels.assert_called_once_with(
                repo=repo,
                model=model,
                engine=engine
            )
            mock_input_labels.return_value.set.assert_called_once_with(input_tokens)

            # Verify output tokens gauge was called
            mock_output_labels.assert_called_once_with(
                repo=repo,
                model=model,
                engine=engine
            )
            mock_output_labels.return_value.set.assert_called_once_with(output_tokens)

    def test_record_token_usage_with_exception(self):
        """Test recording token usage with exception handling."""
        repo = "test-repo"
        model = "claude-sonnet-4"
        engine = "claude-code"
        input_tokens = 100
        output_tokens = 50

        # Mock the gauge to raise an exception
        with patch.object(self.metrics.input_tokens_gauge, "labels", side_effect=Exception("Test error")):
            # Should not raise exception
            self.metrics.record_token_usage(repo, model, engine, input_tokens, output_tokens)

    @patch("src.metrics.push_to_gateway")
    def test_push_metrics_success(self, mock_push_to_gateway):
        """Test successful metrics push."""
        self.metrics.push_metrics()
        mock_push_to_gateway.assert_called_once_with(
            self.pushgateway_url,
            job=self.metrics.job_name,
            registry=self.metrics.registry
        )

    @patch("src.metrics.push_to_gateway")
    def test_push_metrics_failure(self, mock_push_to_gateway):
        """Test metrics push failure handling."""
        mock_push_to_gateway.side_effect = Exception("Push failed")

        # Should not raise exception
        self.metrics.push_metrics()

    def test_push_metrics_no_pushgateway(self):
        """Test push metrics when no pushgateway URL is configured."""
        metrics = AutomergeMetrics(None, job_name="test-job")

        with patch("src.metrics.push_to_gateway") as mock_push_to_gateway:
            metrics.push_metrics()
            mock_push_to_gateway.assert_not_called()

    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        # Mock the gauge collect method
        mock_sample = Mock()
        mock_sample.labels = {
            "repo": "test-repo",
            "model": "claude-sonnet-4",
            "engine": "claude-code"
        }
        mock_sample.value = 100

        mock_metric = Mock()
        mock_metric.samples = [mock_sample]

        with patch.object(self.metrics.input_tokens_gauge, "collect", return_value=[mock_metric]), \
             patch.object(self.metrics.output_tokens_gauge, "collect", return_value=[mock_metric]):

            summary = self.metrics.get_metrics_summary()

            self.assertIn("input_tokens", summary)
            self.assertIn("output_tokens", summary)
            self.assertIn("test-repo_claude-sonnet-4_claude-code", summary["input_tokens"])
            self.assertIn("test-repo_claude-sonnet-4_claude-code", summary["output_tokens"])

    def test_get_metrics_summary_with_exception(self):
        """Test getting metrics summary with exception handling."""
        with patch.object(self.metrics.input_tokens_gauge, "collect", side_effect=Exception("Test error")):
            summary = self.metrics.get_metrics_summary()
            self.assertEqual(summary, {"input_tokens": {}, "output_tokens": {}})


class TestMetricsIntegration(unittest.TestCase):
    """Test integration of metrics with other components."""

    def setUp(self):
        """Set up test fixtures."""
        self.pushgateway_url = "http://test-pushgateway:9091"
        self.metrics = AutomergeMetrics(self.pushgateway_url, job_name="test-automerge")

    def test_metrics_labels_format(self):
        """Test that metrics labels are properly formatted."""
        repo = "test-repo"
        model = "claude-sonnet-4"
        engine = "github-copilot"  # Test with hyphenated engine name

        with patch.object(self.metrics.input_tokens_gauge, "labels") as mock_input_labels, \
             patch.object(self.metrics.output_tokens_gauge, "labels") as mock_output_labels:

            mock_input_labels.return_value.set = Mock()
            mock_output_labels.return_value.set = Mock()

            self.metrics.record_token_usage(repo, model, engine, 100, 50)

            # Verify labels are correctly formatted
            mock_input_labels.assert_called_once_with(
                repo="test-repo",
                model="claude-sonnet-4",
                engine="github-copilot"
            )

    def test_metrics_with_special_characters(self):
        """Test metrics with special characters in repo/model names."""
        repo = "test-repo_with-special.chars"
        model = "claude-sonnet-4"
        engine = "claude-code"

        with patch.object(self.metrics.input_tokens_gauge, "labels") as mock_input_labels, \
             patch.object(self.metrics.output_tokens_gauge, "labels") as mock_output_labels:

            mock_input_labels.return_value.set = Mock()
            mock_output_labels.return_value.set = Mock()

            self.metrics.record_token_usage(repo, model, engine, 100, 50)

            # Should handle special characters gracefully
            mock_input_labels.assert_called_once_with(
                repo="test-repo_with-special.chars",
                model="claude-sonnet-4",
                engine="claude-code"
            )


if __name__ == "__main__":
    unittest.main()
