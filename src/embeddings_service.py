"""
Embeddings service for PR similarity analysis using Amazon Bedrock Titan Embeddings.

This module handles:
- Calculation of embeddings for PR components (files, content, diff, terraform plan)
- Storage and retrieval of embeddings from S3
- Similarity comparison between PRs using cosine similarity
- Caching logic to avoid recalculating embeddings
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from .utils import (
        DEFAULT_EMBEDDINGS_MAX_CACHED_PRS,
        DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT,
        DEFAULT_EMBEDDINGS_AWS_REGION,
    )
except ImportError:
    from utils import (
        DEFAULT_EMBEDDINGS_MAX_CACHED_PRS,
        DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT,
        DEFAULT_EMBEDDINGS_AWS_REGION,
    )

logger = logging.getLogger(__name__)


@dataclass
class PREmbeddings:
    """Container for PR embeddings data."""

    pr_number: int
    repo_name: str
    embeddings: List[float]
    metadata: Dict[str, any]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "PREmbeddings":
        """Create from dictionary."""
        return cls(**data)


class EmbeddingsService:
    """Service for managing PR embeddings using Amazon Bedrock and S3."""

    # Bedrock model configuration
    MODEL_ID = "amazon.titan-embed-text-v2:0"
    EMBEDDING_DIMENSIONS = 512

    # Component weights for concatenation
    COMPONENT_ORDER = ["file_names_paths", "content", "diff", "terraform_plan"]

    def __init__(
        self,
        s3_bucket: str,
        organization: str,
        aws_region: str = DEFAULT_EMBEDDINGS_AWS_REGION,
        similarity_boost_weight: float = DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT,
        max_cached_prs: int = DEFAULT_EMBEDDINGS_MAX_CACHED_PRS,
        enabled: bool = True,
        force_recalculate: bool = False,
        metrics_collector=None,
    ):
        """
        Initialize the embeddings service.

        Args:
            s3_bucket: S3 bucket name for storing embeddings
            organization: GitHub organization name (e.g., "TrueLayer")
            aws_region: AWS region for S3 and Bedrock
            similarity_boost_weight: Weight for similarity boost in score calculation
            max_cached_prs: Maximum number of PRs to cache per repository
            enabled: Whether embeddings service is enabled
            force_recalculate: If True, bypass cache and recalculate all embeddings (debug mode)
            metrics_collector: AutomergeMetrics instance for recording token usage
        """
        self.enabled = enabled
        if not enabled:
            logger.info("Embeddings service is disabled")
            return

        if not BOTO3_AVAILABLE:
            logger.error("boto3 is not installed. Install it with: pip install boto3")
            self.enabled = False
            return

        self.s3_bucket = s3_bucket
        self.organization = organization
        self.aws_region = aws_region
        self.similarity_boost_weight = similarity_boost_weight
        self.max_cached_prs = max_cached_prs
        self.force_recalculate = force_recalculate
        self.metrics_collector = metrics_collector

        if force_recalculate:
            logger.warning(
                "⚠️  Force recalculate mode enabled - will bypass cache and recalculate all embeddings"
            )

        # Initialize AWS clients
        try:
            self.s3_client = boto3.client("s3", region_name=aws_region)
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name=aws_region
            )
            logger.info(
                f"Initialized embeddings service with bucket: {s3_bucket}, region: {aws_region}"
            )
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            self.enabled = False

    def _get_s3_key(self, repo_name: str, pr_number: int) -> str:
        """Generate S3 key for a PR's embeddings file."""
        return f"{self.organization}/{repo_name}/{pr_number}.json"

    def _call_bedrock_embeddings(
        self, text: str, repo_name: str = "unknown"
    ) -> Optional[List[float]]:
        """
        Call Amazon Bedrock to generate embeddings for text.

        Args:
            text: Input text to generate embeddings for
            repo_name: Repository name for metrics tracking

        Returns:
            List of floats representing the embedding vector, or None on error
        """
        if not self.enabled:
            return None

        try:
            # Prepare request body for Titan Embeddings v2
            request_body = {
                "inputText": text,
                "dimensions": self.EMBEDDING_DIMENSIONS,
                "normalize": True,  # Normalize for cosine similarity
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            embeddings = response_body.get("embedding", [])

            # Extract token count from response
            input_token_count = response_body.get("inputTextTokenCount", 0)

            # Record metrics if collector is available
            if self.metrics_collector and input_token_count > 0:
                self.metrics_collector.record_embeddings_token_usage(
                    repo=repo_name, model=self.MODEL_ID, input_tokens=input_token_count
                )
                # Push metrics immediately after recording
                self.metrics_collector.push_metrics()

            if len(embeddings) != self.EMBEDDING_DIMENSIONS:
                logger.error(
                    f"Unexpected embedding dimensions: {len(embeddings)} (expected {self.EMBEDDING_DIMENSIONS})"
                )
                return None

            return embeddings

        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return None

    def _extract_file_info(self, pr_data: Dict) -> str:
        """
        Extract file names and paths from PR data.

        Args:
            pr_data: Dictionary containing PR information

        Returns:
            Formatted string with file information
        """
        files = pr_data.get("files", [])
        if not files:
            return "No files changed"

        file_info = []
        for file in files:
            filename = file.get("filename", "unknown")
            status = file.get("status", "modified")
            file_info.append(f"{status}: {filename}")

        return "\n".join(file_info)

    def _extract_content(self, pr_data: Dict) -> str:
        """
        Extract file content from PR data.

        Args:
            pr_data: Dictionary containing PR information

        Returns:
            Formatted string with file content (truncated if too large)
        """
        files = pr_data.get("files", [])
        if not files:
            return "No content available"

        content_parts = []
        max_content_length = 50000  # Limit total content length
        current_length = 0

        for file in files:
            filename = file.get("filename", "unknown")
            patch = file.get("patch", "")

            if current_length + len(patch) > max_content_length:
                content_parts.append(
                    f"[Content truncated at {max_content_length} characters]"
                )
                break

            content_parts.append(f"File: {filename}\n{patch}\n")
            current_length += len(patch)

        return "\n".join(content_parts)

    def _extract_diff(self, pr_data: Dict) -> str:
        """
        Extract git diff from PR data.

        Args:
            pr_data: Dictionary containing PR information

        Returns:
            Formatted string with git diff
        """
        diff = pr_data.get("diff", "")
        if not diff:
            # Fallback to patch from files
            files = pr_data.get("files", [])
            patches = [f.get("patch", "") for f in files if f.get("patch")]
            diff = "\n".join(patches)

        return diff if diff else "No diff available"

    def _extract_terraform_plan(self, pr_data: Dict) -> str:
        """
        Extract Terraform plan from PR data.

        Args:
            pr_data: Dictionary containing PR information

        Returns:
            Formatted string with Terraform plan
        """
        return pr_data.get("terraform_plan", "No Terraform plan available")

    def calculate_pr_embeddings(self, pr_data: Dict) -> Optional[PREmbeddings]:
        """
        Calculate embeddings for a PR by generating embeddings for each component
        and concatenating them.

        Args:
            pr_data: Dictionary containing PR information with keys:
                - pr_number: PR number
                - repo_name: Repository name
                - files: List of changed files
                - diff: Git diff
                - terraform_plan: Terraform plan output

        Returns:
            PREmbeddings object with concatenated embeddings, or None on error
        """
        if not self.enabled:
            return None

        pr_number = pr_data.get("pr_number")
        repo_name = pr_data.get("repo_name")

        if not pr_number or not repo_name:
            logger.error("PR data missing pr_number or repo_name")
            return None

        logger.info(f"Calculating embeddings for PR #{pr_number} in {repo_name}")

        # Extract components
        components = {
            "file_names_paths": self._extract_file_info(pr_data),
            "content": self._extract_content(pr_data),
            "diff": self._extract_diff(pr_data),
            "terraform_plan": self._extract_terraform_plan(pr_data),
        }

        # Calculate embeddings for each component
        component_embeddings = {}
        for component_name in self.COMPONENT_ORDER:
            text = components[component_name]

            # Bedrock requires non-empty text (minLength: 1)
            # Use placeholder if text is empty to ensure consistent embeddings
            # for all PRs without that component (e.g., no terraform plan)
            if not text or len(text.strip()) == 0:
                text = f"No {component_name} available"
                logger.debug(
                    f"Component {component_name} is empty, using placeholder text"
                )

            logger.debug(
                f"Generating embeddings for component: {component_name} ({len(text)} chars)"
            )

            embeddings = self._call_bedrock_embeddings(text, repo_name)
            if embeddings is None:
                logger.error(
                    f"Failed to generate embeddings for component: {component_name}"
                )
                return None

            component_embeddings[component_name] = embeddings

        # Concatenate all embeddings
        concatenated_embeddings = []
        for component_name in self.COMPONENT_ORDER:
            concatenated_embeddings.extend(component_embeddings[component_name])

        logger.info(
            f"Generated embeddings with {len(concatenated_embeddings)} dimensions "
            f"({len(self.COMPONENT_ORDER)} components × {self.EMBEDDING_DIMENSIONS})"
        )

        # Create PREmbeddings object
        pr_embeddings = PREmbeddings(
            pr_number=pr_number,
            repo_name=repo_name,
            embeddings=concatenated_embeddings,
            metadata={
                "component_dimensions": self.EMBEDDING_DIMENSIONS,
                "total_dimensions": len(concatenated_embeddings),
                "components": self.COMPONENT_ORDER,
                "model": self.MODEL_ID,
            },
        )

        return pr_embeddings

    def save_embeddings_to_s3(self, pr_embeddings: PREmbeddings) -> bool:
        """
        Save PR embeddings to S3.

        Args:
            pr_embeddings: PREmbeddings object to save

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            s3_key = self._get_s3_key(pr_embeddings.repo_name, pr_embeddings.pr_number)

            # Convert to JSON
            json_data = json.dumps(pr_embeddings.to_dict(), indent=2)

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json_data.encode("utf-8"),
                ContentType="application/json",
            )

            logger.info(f"Saved embeddings to S3: s3://{self.s3_bucket}/{s3_key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to save embeddings to S3: {e}")
            return False

    def load_embeddings_from_s3(
        self, repo_name: str, pr_number: int
    ) -> Optional[PREmbeddings]:
        """
        Load PR embeddings from S3.

        Args:
            repo_name: Repository name
            pr_number: PR number

        Returns:
            PREmbeddings object if found, None otherwise
        """
        if not self.enabled:
            return None

        try:
            s3_key = self._get_s3_key(repo_name, pr_number)

            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)

            json_data = response["Body"].read().decode("utf-8")
            data = json.loads(json_data)

            logger.info(f"Loaded embeddings from S3: s3://{self.s3_bucket}/{s3_key}")
            return PREmbeddings.from_dict(data)

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.debug(f"Embeddings not found in S3 for PR #{pr_number}")
            else:
                logger.error(f"Failed to load embeddings from S3: {e}")
            return None

    def _list_s3_files_for_repo(self, repo_name: str) -> List[Dict[str, any]]:
        """
        List all embedding files in S3 for a given repository.

        Args:
            repo_name: Repository name

        Returns:
            List of dicts with 'key', 'pr_number', and 'last_modified' for each file
        """
        if not self.enabled:
            return []

        try:
            prefix = f"{self.organization}/{repo_name}/"

            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket, Prefix=prefix
            )

            files = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]
                    # Extract PR number from filename (e.g., "TrueLayer/repo/123.json" -> 123)
                    filename = key.split("/")[-1]
                    if filename.endswith(".json"):
                        try:
                            pr_number = int(filename.replace(".json", ""))
                            files.append(
                                {
                                    "key": key,
                                    "pr_number": pr_number,
                                    "last_modified": obj["LastModified"],
                                }
                            )
                        except ValueError:
                            logger.warning(
                                f"Skipping file with invalid PR number format: {key}"
                            )

            logger.debug(f"Found {len(files)} embedding files in S3 for {repo_name}")
            return files

        except ClientError as e:
            logger.error(f"Failed to list S3 files for {repo_name}: {e}")
            return []

    def _delete_s3_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 key to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
            logger.info(f"Deleted S3 file: s3://{self.s3_bucket}/{s3_key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete S3 file {s3_key}: {e}")
            return False

    def cleanup_s3_cache(
        self, repo_name: str, github_safe_pr_numbers: List[int]
    ) -> Dict[str, int]:
        """
        Clean up S3 cache to keep only embeddings for the PRs that are currently in GitHub.

        GitHub is the source of truth: S3 should only contain embeddings for the most recent
        safe PRs as determined by GitHub.

        Args:
            repo_name: Repository name
            github_safe_pr_numbers: List of PR numbers from GitHub (max 10 most recent)

        Returns:
            Dict with cleanup stats: {'kept': N, 'deleted': N, 'errors': N}
        """
        if not self.enabled:
            return {"kept": 0, "deleted": 0, "errors": 0}

        logger.info(f"Starting S3 cache cleanup for {repo_name}")
        logger.info(f"GitHub safe PRs (source of truth): {github_safe_pr_numbers}")

        # List all files currently in S3 for this repo
        s3_files = self._list_s3_files_for_repo(repo_name)

        if not s3_files:
            logger.info(f"No files in S3 cache for {repo_name}")
            return {"kept": 0, "deleted": 0, "errors": 0}

        # Convert GitHub PR numbers to a set for efficient lookup
        github_pr_set = set(github_safe_pr_numbers[: self.max_cached_prs])

        stats = {"kept": 0, "deleted": 0, "errors": 0}

        # Process each file in S3
        for file_info in s3_files:
            pr_number = file_info["pr_number"]
            s3_key = file_info["key"]

            if pr_number in github_pr_set:
                # This PR is in GitHub's list, keep it
                logger.debug(
                    f"Keeping cached embeddings for PR #{pr_number} (in GitHub list)"
                )
                stats["kept"] += 1
            else:
                # This PR is NOT in GitHub's list, delete it
                logger.info(
                    f"Deleting cached embeddings for PR #{pr_number} (not in GitHub's top {self.max_cached_prs})"
                )
                if self._delete_s3_file(s3_key):
                    stats["deleted"] += 1
                else:
                    stats["errors"] += 1

        logger.info(f"S3 cache cleanup completed for {repo_name}: {stats}")
        return stats

    def get_historical_safe_prs(
        self, repo_name: str, safe_pr_numbers: List[int], github_client=None
    ) -> List[PREmbeddings]:
        """
        Get embeddings for historical safe PRs, using cache when available.

        This method implements the cache synchronization logic:
        1. GitHub is the source of truth for which PRs are the most recent safe PRs
        2. Clean up S3 to remove embeddings for PRs not in GitHub's list
        3. Load cached embeddings for PRs that exist in S3
        4. Calculate and save embeddings for PRs that are missing from S3

        Args:
            repo_name: Repository name
            safe_pr_numbers: List of PR numbers with 'automerge-safe-example' label from GitHub
            github_client: GitHub client instance (needed to fetch PR data for missing embeddings)

        Returns:
            List of PREmbeddings for the safe PRs (loaded from cache or newly calculated)
        """
        if not self.enabled:
            return []

        # Limit to max_cached_prs
        github_safe_prs = safe_pr_numbers[: self.max_cached_prs]

        logger.info(
            f"Processing historical safe PRs for {repo_name}: {github_safe_prs}"
        )

        # Step 1: Clean up S3 cache - GitHub is the source of truth
        cleanup_stats = self.cleanup_s3_cache(repo_name, github_safe_prs)
        logger.info(
            f"Cache cleanup: kept={cleanup_stats['kept']}, deleted={cleanup_stats['deleted']}, errors={cleanup_stats['errors']}"
        )

        # Step 2: Load cached embeddings and identify missing ones
        historical_embeddings = []
        missing_pr_numbers = []

        # If force_recalculate is enabled, treat all PRs as missing to bypass cache
        if self.force_recalculate:
            logger.info(
                "🔄 Force recalculate enabled - skipping cache, will recalculate all embeddings"
            )
            missing_pr_numbers = github_safe_prs.copy()
        else:
            for pr_number in github_safe_prs:
                pr_embeddings = self.load_embeddings_from_s3(repo_name, pr_number)
                if pr_embeddings:
                    historical_embeddings.append(pr_embeddings)
                else:
                    missing_pr_numbers.append(pr_number)
                    logger.info(
                        f"PR #{pr_number} not in cache, will need to calculate embeddings"
                    )

        logger.info(
            f"Loaded {len(historical_embeddings)} cached embeddings, {len(missing_pr_numbers)} missing"
        )

        # Step 3: Calculate and save embeddings for missing PRs (if github_client is available)
        if missing_pr_numbers and github_client:
            logger.info(
                f"Calculating embeddings for {len(missing_pr_numbers)} missing PRs: {missing_pr_numbers}"
            )

            for pr_number in missing_pr_numbers:
                try:
                    # Fetch full PR data from GitHub
                    logger.info(
                        f"Fetching PR #{pr_number} data from GitHub for embeddings calculation"
                    )
                    pr_data = github_client.get_specific_pull_requests(
                        [{"repo": repo_name, "pr_number": pr_number}]
                    )

                    if not pr_data or len(pr_data) == 0:
                        logger.warning(
                            f"Could not fetch PR #{pr_number} from GitHub, skipping"
                        )
                        continue

                    pr = pr_data[0]

                    # Get terraform plan from comments
                    issue_url = pr.get("issue_url")
                    terraform_plan = ""
                    if issue_url:
                        terraform_plan = github_client.get_last_terraform_plan(
                            issue_url
                        ) or ""

                    # Prepare PR data for embeddings
                    pr_embeddings_data = {
                        "pr_number": pr_number,
                        "repo_name": repo_name,
                        "files": pr.get("files", []),
                        "diff": pr.get("diff", ""),
                        "terraform_plan": terraform_plan,
                    }

                    # Calculate embeddings
                    pr_embeddings = self.calculate_pr_embeddings(pr_embeddings_data)

                    if pr_embeddings:
                        # Save to S3
                        if self.save_embeddings_to_s3(pr_embeddings):
                            historical_embeddings.append(pr_embeddings)
                            logger.info(
                                f"Successfully calculated and saved embeddings for PR #{pr_number}"
                            )
                        else:
                            logger.error(
                                f"Failed to save embeddings for PR #{pr_number} to S3"
                            )
                    else:
                        logger.error(
                            f"Failed to calculate embeddings for PR #{pr_number}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing missing embeddings for PR #{pr_number}: {e}",
                        exc_info=True,
                    )

        elif missing_pr_numbers and not github_client:
            logger.warning(
                f"Cannot calculate embeddings for {len(missing_pr_numbers)} missing PRs: GitHub client not available"
            )

        logger.info(
            f"Final result: {len(historical_embeddings)} historical PR embeddings for {repo_name}"
        )
        return historical_embeddings

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two embedding vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity score (0-1)
        """
        if len(vec1) != len(vec2):
            logger.error(f"Vector dimension mismatch: {len(vec1)} vs {len(vec2)}")
            return 0.0

        # Convert to numpy arrays for efficient computation
        a = np.array(vec1)
        b = np.array(vec2)

        # Calculate cosine similarity
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = dot_product / (norm_a * norm_b)

        # Clamp to [0, 1] range (normalized embeddings should already be in this range)
        return max(0.0, min(1.0, similarity))

    def calculate_similarity_boost(
        self,
        current_pr_embeddings: PREmbeddings,
        historical_embeddings: List[PREmbeddings],
    ) -> Tuple[float, Optional[int]]:
        """
        Calculate similarity boost based on comparison with historical safe PRs.

        Args:
            current_pr_embeddings: Embeddings for the current PR
            historical_embeddings: List of embeddings from historical safe PRs

        Returns:
            Tuple of (max_similarity_score, most_similar_pr_number)
        """
        if not self.enabled or not historical_embeddings:
            return 0.0, None

        max_similarity = 0.0
        most_similar_pr = None

        current_vec = current_pr_embeddings.embeddings

        for historical_pr in historical_embeddings:
            similarity = self.cosine_similarity(current_vec, historical_pr.embeddings)

            logger.debug(
                f"Similarity with PR #{historical_pr.pr_number}: {similarity:.4f}"
            )

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_pr = historical_pr.pr_number

        if most_similar_pr:
            logger.info(
                f"Max similarity: {max_similarity:.4f} with PR #{most_similar_pr}"
            )

        return max_similarity, most_similar_pr

    def apply_similarity_boost(
        self, base_confidence_score: float, similarity_score: float
    ) -> float:
        """
        Apply similarity boost to base confidence score.

        Formula: score_finale = score_attuale * (1 + peso_similarità * max_similarity)

        Args:
            base_confidence_score: Original confidence score (0-100)
            similarity_score: Similarity with most similar historical PR (0-1)

        Returns:
            Boosted confidence score (0-100)
        """
        if not self.enabled:
            return base_confidence_score

        boost_multiplier = 1 + (self.similarity_boost_weight * similarity_score)
        boosted_score = base_confidence_score * boost_multiplier

        # Clamp to valid range [0, 100]
        boosted_score = max(0.0, min(100.0, boosted_score))

        logger.info(
            f"Applied similarity boost: {base_confidence_score:.2f} → {boosted_score:.2f} "
            f"(similarity: {similarity_score:.4f}, weight: {self.similarity_boost_weight})"
        )

        return boosted_score
