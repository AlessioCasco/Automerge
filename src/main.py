#!/usr/bin/env python3

import argparse
import sys
import os
import logging

# Set up logger
logger = logging.getLogger(__name__)

try:
    from .config import load_and_validate_config
    from .github_client import GitHubClient
    from .pr_processor import PRProcessor
    from .embeddings_service import EmbeddingsService
    from .metrics import AutomergeMetrics
    from .utils import (
        DEFAULT_EMBEDDINGS_MAX_CACHED_PRS,
        DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT,
        DEFAULT_EMBEDDINGS_AWS_REGION,
    )
except ImportError:
    # If relative imports fail, try absolute imports (when run as script)
    from config import load_and_validate_config
    from github_client import GitHubClient
    from pr_processor import PRProcessor
    from embeddings_service import EmbeddingsService
    from metrics import AutomergeMetrics
    from utils import (
        DEFAULT_EMBEDDINGS_MAX_CACHED_PRS,
        DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT,
        DEFAULT_EMBEDDINGS_AWS_REGION,
    )


def main():
    """Main entry point for the automerge application."""
    try:
        # Init parser for the arguments
        parser = argparse.ArgumentParser(
            prog="Automerge",
            description="GitHub PR auto-merger",
            epilog="Thanks for flying automerge",
        )
        parser.add_argument(
            "--config_file",
            type=str,
            default="./config.json",
            help="JSON file holding the GitHub access token, default is ./config.json",
        )
        parser.add_argument(
            "--force",
            default=False,
            action="store_true",
            help="Skip all regex and plan every PR",
        )
        parser.add_argument(
            "--approve_all",
            action="store_true",
            default=False,
            help="Approves all PRs that match the filters in the config",
        )
        parser.add_argument(
            "--log_level",
            type=str,
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Set logging level (DEBUG, INFO, WARNING, ERROR)",
        )
        args = parser.parse_args()

        # Set logging level from CLI argument or environment variable
        log_level = os.environ.get("LOG_LEVEL", args.log_level).upper()
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

        # Configure logging format
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Load and validate configuration
        config = load_and_validate_config(args.config_file)

        # Extract info from config
        access_token = config["access_token"]
        owner = config["owner"]
        github_user = config["github_user"]
        repos = config["repos"]
        filters = config["filters"]

        # Initialize GitHub client
        github_client = GitHubClient(access_token, owner, github_user)

        # Initialize metrics collector if pushgateway URL is configured
        metrics_collector = None
        pushgateway_url = config.get("metrics_pushgateway_url")
        if pushgateway_url:
            metrics_collector = AutomergeMetrics(pushgateway_url, job_name="automerge")
            logger.info(
                f"Initialized metrics collector with pushgateway: {pushgateway_url}"
            )

        # Initialize embeddings service if configured
        embeddings_config = config.get("embeddings", {})
        embeddings_service = None
        if embeddings_config.get("enabled", False):
            embeddings_service = EmbeddingsService(
                s3_bucket=embeddings_config.get("s3_bucket", ""),
                organization=owner,
                aws_region=embeddings_config.get(
                    "aws_region", DEFAULT_EMBEDDINGS_AWS_REGION
                ),
                similarity_boost_weight=embeddings_config.get(
                    "similarity_boost_weight", DEFAULT_EMBEDDINGS_SIMILARITY_BOOST_WEIGHT
                ),
                max_cached_prs=embeddings_config.get(
                    "max_cached_prs", DEFAULT_EMBEDDINGS_MAX_CACHED_PRS
                ),
                enabled=True,
                force_recalculate=embeddings_config.get("force_recalculate", False),
                metrics_collector=metrics_collector,
            )
            logger.info("Embeddings service initialized")
        else:
            logger.info("Embeddings service disabled")

        # Get all repos pull requests
        all_pulls = github_client.get_pull_requests(repos, filters)

        # Get test PRs if configured
        test_prs = config.get("test_prs", [])
        if test_prs:
            logger.info(f"Found {len(test_prs)} test PRs configured")
            test_pulls = github_client.get_specific_pull_requests(test_prs)
        else:
            test_pulls = []

        if args.approve_all:
            logger.info("Only Approving Now")
            github_client.approve_all_prs(all_pulls)
            sys.exit(0)

        # Initialize PR processor
        pr_processor = PRProcessor(github_client, config, embeddings_service)

        # Process test PRs first (if AI is enabled)
        if test_pulls and config.get("enable_ai_confidence_score", False):
            pr_processor.process_test_prs(test_prs)

        # Process regular pull requests
        pr_processor.process_prs(all_pulls, args.force)

        logger.info("All done, exiting")

    except KeyboardInterrupt:
        logger.info("Exiting by user request")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
