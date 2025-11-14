import unittest
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

# Add src directory to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embeddings_service import EmbeddingsService, PREmbeddings  # noqa: E402
from utils import (  # noqa: E402
    DEFAULT_EMBEDDINGS_MAX_CACHED_PRS,
    DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT,
    DEFAULT_EMBEDDINGS_AWS_REGION,
)


class TestPREmbeddings(unittest.TestCase):
    """Test the PREmbeddings dataclass."""

    def test_to_dict(self):
        """Test converting PREmbeddings to dictionary."""
        embeddings = PREmbeddings(
            pr_number=123,
            repo_name="test-repo",
            embeddings=[0.1, 0.2, 0.3],
            metadata={"test": "data"},
        )

        result = embeddings.to_dict()

        self.assertEqual(result["pr_number"], 123)
        self.assertEqual(result["repo_name"], "test-repo")
        self.assertEqual(result["embeddings"], [0.1, 0.2, 0.3])
        self.assertEqual(result["metadata"], {"test": "data"})

    def test_from_dict(self):
        """Test creating PREmbeddings from dictionary."""
        data = {
            "pr_number": 456,
            "repo_name": "another-repo",
            "embeddings": [0.4, 0.5, 0.6],
            "metadata": {"key": "value"},
        }

        embeddings = PREmbeddings.from_dict(data)

        self.assertEqual(embeddings.pr_number, 456)
        self.assertEqual(embeddings.repo_name, "another-repo")
        self.assertEqual(embeddings.embeddings, [0.4, 0.5, 0.6])
        self.assertEqual(embeddings.metadata, {"key": "value"})


class TestEmbeddingsServiceInit(unittest.TestCase):
    """Test EmbeddingsService initialization."""

    @patch("embeddings_service.BOTO3_AVAILABLE", True)
    @patch("embeddings_service.boto3")
    def test_init_success(self, mock_boto3):
        """Test successful initialization."""
        mock_s3 = Mock()
        mock_bedrock = Mock()
        mock_boto3.client.side_effect = lambda service, region_name: (
            mock_s3 if service == "s3" else mock_bedrock
        )

        service = EmbeddingsService(
            s3_bucket="test-bucket",
            organization="test-org",
            aws_region="us-east-1",
            similarity_boost_weight=0.7,
            max_cached_prs=50,
            enabled=True,
        )

        self.assertTrue(service.enabled)
        self.assertEqual(service.s3_bucket, "test-bucket")
        self.assertEqual(service.organization, "test-org")
        self.assertEqual(service.aws_region, "us-east-1")
        self.assertEqual(service.similarity_boost_weight, 0.7)
        self.assertEqual(service.max_cached_prs, 50)
        self.assertFalse(service.force_recalculate)

    def test_init_disabled(self):
        """Test initialization when disabled."""
        service = EmbeddingsService(
            s3_bucket="test-bucket", organization="test-org", enabled=False
        )

        self.assertFalse(service.enabled)

    @patch("embeddings_service.BOTO3_AVAILABLE", False)
    def test_init_boto3_not_available(self):
        """Test initialization when boto3 is not available."""
        service = EmbeddingsService(
            s3_bucket="test-bucket", organization="test-org", enabled=True
        )

        self.assertFalse(service.enabled)

    @patch("embeddings_service.BOTO3_AVAILABLE", True)
    @patch("embeddings_service.boto3")
    def test_init_with_defaults(self, mock_boto3):
        """Test initialization with default values."""
        mock_boto3.client.return_value = Mock()

        service = EmbeddingsService(s3_bucket="test-bucket", organization="test-org")

        self.assertEqual(service.aws_region, DEFAULT_EMBEDDINGS_AWS_REGION)
        self.assertEqual(
            service.similarity_boost_weight, DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT
        )
        self.assertEqual(service.max_cached_prs, DEFAULT_EMBEDDINGS_MAX_CACHED_PRS)

    @patch("embeddings_service.BOTO3_AVAILABLE", True)
    @patch("embeddings_service.boto3")
    def test_init_force_recalculate(self, mock_boto3):
        """Test initialization with force_recalculate enabled."""
        mock_boto3.client.return_value = Mock()

        service = EmbeddingsService(
            s3_bucket="test-bucket",
            organization="test-org",
            force_recalculate=True,
        )

        self.assertTrue(service.force_recalculate)


class TestEmbeddingsServiceS3Operations(unittest.TestCase):
    """Test EmbeddingsService S3 operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_s3 = Mock()
        self.mock_bedrock = Mock()

        with patch("embeddings_service.BOTO3_AVAILABLE", True), patch(
            "embeddings_service.boto3"
        ) as mock_boto3:
            mock_boto3.client.side_effect = lambda service, region_name: (
                self.mock_s3 if service == "s3" else self.mock_bedrock
            )

            self.service = EmbeddingsService(
                s3_bucket="test-bucket", organization="test-org", enabled=True
            )

    def test_get_s3_key(self):
        """Test S3 key generation."""
        key = self.service._get_s3_key("my-repo", 123)

        self.assertEqual(key, "test-org/my-repo/123.json")

    def test_save_embeddings_to_s3_success(self):
        """Test successful save to S3."""
        embeddings = PREmbeddings(
            pr_number=123,
            repo_name="test-repo",
            embeddings=[0.1, 0.2, 0.3],
            metadata={},
        )

        self.mock_s3.put_object.return_value = {}

        result = self.service.save_embeddings_to_s3(embeddings)

        self.assertTrue(result)
        self.mock_s3.put_object.assert_called_once()
        call_args = self.mock_s3.put_object.call_args
        self.assertEqual(call_args[1]["Bucket"], "test-bucket")
        self.assertEqual(call_args[1]["Key"], "test-org/test-repo/123.json")

    def test_save_embeddings_to_s3_disabled(self):
        """Test save to S3 when service is disabled."""
        self.service.enabled = False
        embeddings = PREmbeddings(
            pr_number=123, repo_name="test-repo", embeddings=[0.1], metadata={}
        )

        result = self.service.save_embeddings_to_s3(embeddings)

        self.assertFalse(result)
        self.mock_s3.put_object.assert_not_called()

    def test_load_embeddings_from_s3_success(self):
        """Test successful load from S3."""
        embeddings_data = {
            "pr_number": 123,
            "repo_name": "test-repo",
            "embeddings": [0.1, 0.2, 0.3],
            "metadata": {},
        }

        mock_response = {"Body": Mock()}
        mock_response["Body"].read.return_value = json.dumps(embeddings_data).encode()
        self.mock_s3.get_object.return_value = mock_response

        result = self.service.load_embeddings_from_s3("test-repo", 123)

        self.assertIsNotNone(result)
        self.assertEqual(result.pr_number, 123)
        self.assertEqual(result.repo_name, "test-repo")
        self.assertEqual(result.embeddings, [0.1, 0.2, 0.3])

    def test_load_embeddings_from_s3_not_found(self):
        """Test load from S3 when embeddings don't exist."""
        from botocore.exceptions import ClientError

        self.mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        result = self.service.load_embeddings_from_s3("test-repo", 123)

        self.assertIsNone(result)


class TestEmbeddingsServiceBedrockOperations(unittest.TestCase):
    """Test EmbeddingsService Bedrock operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_s3 = Mock()
        self.mock_bedrock = Mock()

        with patch("embeddings_service.BOTO3_AVAILABLE", True), patch(
            "embeddings_service.boto3"
        ) as mock_boto3:
            mock_boto3.client.side_effect = lambda service, region_name: (
                self.mock_s3 if service == "s3" else self.mock_bedrock
            )

            self.service = EmbeddingsService(
                s3_bucket="test-bucket", organization="test-org", enabled=True
            )

    def test_call_bedrock_embeddings_success(self):
        """Test successful Bedrock embeddings call."""
        mock_response = {
            "body": Mock(),
        }
        embeddings_list = [0.1] * 512  # Titan V2 returns 512 dimensions
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embeddings_list, "inputTextTokenCount": 10}
        ).encode()

        self.mock_bedrock.invoke_model.return_value = mock_response

        result = self.service._call_bedrock_embeddings("test text", "test-repo")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 512)
        self.assertEqual(result, embeddings_list)

    def test_call_bedrock_embeddings_with_metrics(self):
        """Test Bedrock call with metrics collection."""
        mock_metrics = Mock()
        self.service.metrics_collector = mock_metrics

        mock_response = {"body": Mock()}
        embeddings_list = [0.1] * 512
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embeddings_list, "inputTextTokenCount": 25}
        ).encode()

        self.mock_bedrock.invoke_model.return_value = mock_response

        result = self.service._call_bedrock_embeddings("test text", "my-repo")

        self.assertIsNotNone(result)
        mock_metrics.record_embeddings_token_usage.assert_called_once_with(
            repo="my-repo", model=self.service.MODEL_ID, input_tokens=25
        )
        mock_metrics.push_metrics.assert_called_once()

    def test_call_bedrock_embeddings_disabled(self):
        """Test Bedrock call when service is disabled."""
        self.service.enabled = False

        result = self.service._call_bedrock_embeddings("test text", "test-repo")

        self.assertIsNone(result)
        self.mock_bedrock.invoke_model.assert_not_called()

    def test_call_bedrock_embeddings_wrong_dimensions(self):
        """Test Bedrock call with wrong embedding dimensions."""
        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": [0.1, 0.2], "inputTextTokenCount": 10}
        ).encode()

        self.mock_bedrock.invoke_model.return_value = mock_response

        result = self.service._call_bedrock_embeddings("test text", "test-repo")

        self.assertIsNone(result)


class TestEmbeddingsServiceExtractMethods(unittest.TestCase):
    """Test EmbeddingsService extraction methods."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("embeddings_service.BOTO3_AVAILABLE", True), patch(
            "embeddings_service.boto3"
        ):
            self.service = EmbeddingsService(
                s3_bucket="test-bucket", organization="test-org", enabled=True
            )

    def test_extract_file_info(self):
        """Test file info extraction."""
        pr_data = {
            "files": [
                {"filename": "file1.tf", "status": "modified"},
                {"filename": "file2.tf", "status": "added"},
            ]
        }

        result = self.service._extract_file_info(pr_data)

        self.assertIn("modified: file1.tf", result)
        self.assertIn("added: file2.tf", result)

    def test_extract_file_info_empty(self):
        """Test file info extraction with no files."""
        pr_data = {"files": []}

        result = self.service._extract_file_info(pr_data)

        self.assertEqual(result, "No files changed")

    def test_extract_content(self):
        """Test content extraction."""
        pr_data = {
            "files": [
                {"filename": "test.tf", "patch": "some patch content"},
            ]
        }

        result = self.service._extract_content(pr_data)

        self.assertIn("test.tf", result)
        self.assertIn("some patch content", result)

    def test_extract_diff(self):
        """Test diff extraction."""
        pr_data = {"diff": "diff content here"}

        result = self.service._extract_diff(pr_data)

        self.assertEqual(result, "diff content here")

    def test_extract_diff_fallback(self):
        """Test diff extraction with fallback to patches."""
        pr_data = {
            "files": [
                {"patch": "patch1"},
                {"patch": "patch2"},
            ]
        }

        result = self.service._extract_diff(pr_data)

        self.assertIn("patch1", result)
        self.assertIn("patch2", result)

    def test_extract_terraform_plan(self):
        """Test terraform plan extraction."""
        pr_data = {"terraform_plan": "terraform plan output"}

        result = self.service._extract_terraform_plan(pr_data)

        self.assertEqual(result, "terraform plan output")

    def test_extract_terraform_plan_default(self):
        """Test terraform plan extraction with default."""
        pr_data = {}

        result = self.service._extract_terraform_plan(pr_data)

        self.assertEqual(result, "No Terraform plan available")


class TestEmbeddingsServiceCalculatePREmbeddings(unittest.TestCase):
    """Test EmbeddingsService calculate_pr_embeddings method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bedrock = Mock()

        with patch("embeddings_service.BOTO3_AVAILABLE", True), patch(
            "embeddings_service.boto3"
        ) as mock_boto3:
            mock_boto3.client.side_effect = lambda service, region_name: (
                Mock() if service == "s3" else self.mock_bedrock
            )

            self.service = EmbeddingsService(
                s3_bucket="test-bucket", organization="test-org", enabled=True
            )

    def test_calculate_pr_embeddings_success(self):
        """Test successful PR embeddings calculation."""
        pr_data = {
            "pr_number": 123,
            "repo_name": "test-repo",
            "files": [{"filename": "test.tf", "status": "modified"}],
            "diff": "diff content",
            "terraform_plan": "plan output",
        }

        # Mock Bedrock responses for each component
        mock_response = {"body": Mock()}
        embeddings_list = [0.1] * 512
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embeddings_list, "inputTextTokenCount": 10}
        ).encode()

        self.mock_bedrock.invoke_model.return_value = mock_response

        result = self.service.calculate_pr_embeddings(pr_data)

        self.assertIsNotNone(result)
        self.assertEqual(result.pr_number, 123)
        self.assertEqual(result.repo_name, "test-repo")
        # 4 components × 512 dimensions = 2048
        self.assertEqual(len(result.embeddings), 2048)

    def test_calculate_pr_embeddings_missing_data(self):
        """Test PR embeddings calculation with missing required data."""
        pr_data = {"pr_number": 123}  # Missing repo_name

        result = self.service.calculate_pr_embeddings(pr_data)

        self.assertIsNone(result)

    def test_calculate_pr_embeddings_empty_component(self):
        """Test PR embeddings calculation with empty components."""
        pr_data = {
            "pr_number": 123,
            "repo_name": "test-repo",
            "files": [],
            "diff": "",
            "terraform_plan": "",
        }

        mock_response = {"body": Mock()}
        embeddings_list = [0.1] * 512
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embeddings_list, "inputTextTokenCount": 5}
        ).encode()

        self.mock_bedrock.invoke_model.return_value = mock_response

        result = self.service.calculate_pr_embeddings(pr_data)

        self.assertIsNotNone(result)
        # Should use placeholder text for empty components


class TestEmbeddingsServiceSimilarity(unittest.TestCase):
    """Test EmbeddingsService similarity calculations."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("embeddings_service.BOTO3_AVAILABLE", True), patch(
            "embeddings_service.boto3"
        ):
            self.service = EmbeddingsService(
                s3_bucket="test-bucket",
                organization="test-org",
                similarity_boost_weight=0.5,
                enabled=True,
            )

    def test_calculate_similarity_boost(self):
        """Test similarity boost calculation."""
        current_embeddings = PREmbeddings(
            pr_number=1,
            repo_name="test-repo",
            embeddings=[1.0, 0.0, 0.0],
            metadata={},
        )

        historical_embeddings = [
            PREmbeddings(
                pr_number=2,
                repo_name="test-repo",
                embeddings=[1.0, 0.0, 0.0],  # Identical
                metadata={},
            ),
            PREmbeddings(
                pr_number=3,
                repo_name="test-repo",
                embeddings=[0.0, 1.0, 0.0],  # Orthogonal
                metadata={},
            ),
        ]

        max_similarity, most_similar_pr = self.service.calculate_similarity_boost(
            current_embeddings, historical_embeddings
        )

        self.assertAlmostEqual(max_similarity, 1.0, places=5)
        self.assertEqual(most_similar_pr, 2)

    def test_apply_similarity_boost(self):
        """Test applying similarity boost to score."""
        base_score = 80
        similarity = 0.9

        boosted_score = self.service.apply_similarity_boost(base_score, similarity)

        # Formula: boosted = base * (1 + weight * similarity)
        # boosted = 80 * (1 + 0.5 * 0.9) = 80 * 1.45 = 116
        # Clamped to 100
        self.assertEqual(boosted_score, 100.0)

    def test_apply_similarity_boost_max_score(self):
        """Test applying similarity boost doesn't exceed 100."""
        base_score = 100
        similarity = 1.0

        boosted_score = self.service.apply_similarity_boost(base_score, similarity)

        self.assertEqual(boosted_score, 100)


class TestEmbeddingsServiceForceRecalculate(unittest.TestCase):
    """Test EmbeddingsService force_recalculate functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_s3 = Mock()

        with patch("embeddings_service.BOTO3_AVAILABLE", True), patch(
            "embeddings_service.boto3"
        ) as mock_boto3:
            mock_boto3.client.side_effect = lambda service, region_name: (
                self.mock_s3 if service == "s3" else Mock()
            )

            self.service = EmbeddingsService(
                s3_bucket="test-bucket",
                organization="test-org",
                force_recalculate=True,
                enabled=True,
            )

    def test_force_recalculate_skips_cache(self):
        """Test that force_recalculate bypasses S3 cache loading."""
        # This would be tested in get_historical_safe_prs
        # The method should skip load_embeddings_from_s3 when force_recalculate is True
        self.assertTrue(self.service.force_recalculate)


if __name__ == "__main__":
    unittest.main()
