#!/usr/bin/env python3

import os
import re
import logging
import requests
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta, timezone

# Set up logger
logger = logging.getLogger(__name__)

try:
    from .github_client import GitHubClient
    from .ai_confidence import AIConfidenceCalculator, AIServiceError
    from .metrics import AutomergeMetrics
    from .utils import (
        LABEL_AUTOMERGE_IGNORE,
        LABEL_AUTOMERGE_NO_PROJECT,
        LABEL_AUTOMERGE_CONFLICT,
        LABEL_SAFE_FOR_AUTOMERGE,
        COMMENT_ATLANTIS_PLAN,
        COMMENT_ATLANTIS_UNLOCK,
        COMMENT_IGNORE_AUTOMERGE,
        COMMENT_CLOSE_NEW_VERSION,
        COMMENT_NO_PROJECT,
        COMMENT_CONFIDENCE_SCORE_TEMPLATE,
        COMMENT_CONFIDENCE_SCORE_ERROR,
        COMMENT_CONFIDENCE_SCORE_AI_FAILURE,
        format_pr_info,
        REVIEW_STATE_DISMISSED,
        DEFAULT_TIMEOUT,
    )
except ImportError:
    from github_client import GitHubClient
    from ai_confidence import AIConfidenceCalculator, AIServiceError
    from metrics import AutomergeMetrics
    from utils import (
        LABEL_AUTOMERGE_IGNORE,
        LABEL_AUTOMERGE_NO_PROJECT,
        LABEL_AUTOMERGE_CONFLICT,
        COMMENT_ATLANTIS_PLAN,
        COMMENT_ATLANTIS_UNLOCK,
        COMMENT_IGNORE_AUTOMERGE,
        COMMENT_CLOSE_NEW_VERSION,
        COMMENT_NO_PROJECT,
        COMMENT_CONFIDENCE_SCORE_TEMPLATE,
        COMMENT_CONFIDENCE_SCORE_ERROR,
        COMMENT_CONFIDENCE_SCORE_AI_FAILURE,
        format_pr_info,
        REVIEW_STATE_DISMISSED,
        DEFAULT_TIMEOUT,
    )


class PRProcessor:
    """Handles PR processing and categorization logic."""

    def __init__(
        self,
        github_client: GitHubClient,
        config: Dict[str, Any],
        embeddings_service=None,
    ):
        """Initialize PR processor.

        Args:
            github_client: GitHub client instance
            config: Configuration dictionary
            embeddings_service: Optional embeddings service for PR similarity analysis
        """
        self.github_client = github_client
        self.config = config

        # Initialize metrics collector if pushgateway URL is configured
        self.metrics = None
        pushgateway_url = config.get("metrics_pushgateway_url")
        if pushgateway_url:
            self.metrics = AutomergeMetrics(pushgateway_url, job_name="automerge")
            logger.info(
                f"Initialized metrics collector with pushgateway: {pushgateway_url}"
            )
        else:
            logger.debug("No metrics pushgateway URL configured, metrics disabled")

        # Initialize AI confidence calculator if enabled
        self.ai_calculator = None
        if config.get("enable_ai_confidence_score", False):
            self.ai_calculator = AIConfidenceCalculator(
                config["access_token"],
                self.github_client,
                config,
                self.metrics,  # Pass metrics to AI calculator
                embeddings_service,  # Pass embeddings service to AI calculator
            )

        # Compile regex patterns for efficiency
        self.regexp_pr_diff = re.compile(
            r"Plan: [0-9]* to add, [0-9]* to change, [0-9]* to destroy\.|Changes to Outputs"
        )
        self.regexp_pr_no_changes = re.compile(
            r"No changes. Your infrastructure matches the configuration|Apply complete!"
        )
        self.regexp_pr_ignore = re.compile(r"This PR will be ignored by automerge")
        self.regexp_pr_error = re.compile(
            r"Plan Error|Plan Failed|Continued plan output from previous comment.|via the Atlantis UI|All Atlantis locks for this PR have been unlocked and plans discarded|Renovate will not automatically rebase this PR|Apply Failed|Apply Error"
        )
        self.regexp_pr_still_working = re.compile(r"atlantis plan|atlantis apply")
        self.regexp_pr_no_project = re.compile(r"Ran Plan for 0 projects")
        self.regexp_new_version = re.compile(r"A newer version of")

    def create_pr_lists(
        self, all_pull_req: List[Dict[str, Any]], force: bool
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """Categorize pull requests into different lists based on their state.

        Args:
            all_pull_req: List of all pull requests to process
            force: Whether to force planning of all PRs

        Returns:
            Tuple of (no_comments, with_diffs, no_changes, error, to_be_closed, dismissed) lists
        """
        list_no_comments = []
        list_with_diffs = []
        list_no_changes = []
        list_error = []
        list_to_be_closed = []
        list_dismissed = []

        for pull_req in all_pull_req:
            last_comment = self.github_client.get_last_comment(pull_req["issue_url"])

            # Check if PR is dismissed and should be re-approved
            approval_status = self.github_client.is_approved(pull_req["url"])
            if approval_status == REVIEW_STATE_DISMISSED:
                list_dismissed.append(pull_req)
                logger.info(
                    f"{format_pr_info(pull_req)}: Dismissed, will re-approve and check for merging."
                )
                continue

            if not last_comment:
                list_no_comments.append(pull_req)
                logger.info(f"{format_pr_info(pull_req)}: No Comments, new pr.")
                continue

            if self.regexp_pr_no_changes.search(last_comment["body"]):
                list_no_changes.append(pull_req)
                logger.info(f"{format_pr_info(pull_req)}: No changes.")
                continue

            # If --force is enabled, we will plan all PRs to avoid automerge to ignore PRs that had issues
            if force:
                logger.info(f"{format_pr_info(pull_req)}: Will be forced to plan")
                list_no_comments.append(pull_req)
                continue
            else:
                if self.regexp_pr_diff.search(last_comment["body"]):
                    list_with_diffs.append(pull_req)
                    logger.info(
                        f"{format_pr_info(pull_req)}: There are diffs or conflicts."
                    )
                    continue

                if self.regexp_pr_error.search(last_comment["body"]):
                    list_error.append(pull_req)
                    logger.info(f"{format_pr_info(pull_req)}: Has errors.")
                    continue

                if self.regexp_new_version.search(last_comment["body"]):
                    list_to_be_closed.append(pull_req)
                    logger.info(
                        f"{format_pr_info(pull_req)}: {COMMENT_CLOSE_NEW_VERSION}"
                    )
                    continue

                if self.regexp_pr_still_working.search(last_comment["body"]):
                    logger.info(
                        f"{format_pr_info(pull_req)}: Atlantis is still working here, ignoring this PR for now."
                    )
                    continue

                if self.regexp_pr_ignore.search(last_comment["body"]):
                    logger.info(
                        f"{format_pr_info(pull_req)}: Will be ignored, there are diffs"
                    )
                    continue

                if self.regexp_pr_no_project.search(last_comment["body"]):
                    logger.info(f"{format_pr_info(pull_req)}: {COMMENT_NO_PROJECT}")
                    self.github_client.set_label_to_pull_request(
                        [pull_req], LABEL_AUTOMERGE_NO_PROJECT
                    )
                    continue

                logger.warning(
                    f"{format_pr_info(pull_req)}: *** Not match, please check why!!!***"
                )

        return (
            list_no_comments,
            list_with_diffs,
            list_no_changes,
            list_error,
            list_to_be_closed,
            list_dismissed,
        )

    def process_test_prs(self, test_prs: List[Dict[str, Any]]) -> None:
        """Process specific test PRs for AI confidence score analysis.

        Args:
            test_prs: List of test PRs to analyze
        """
        if not self.ai_calculator:
            logger.info(
                "AI confidence score calculation is disabled, skipping test PRs"
            )
            return

        logger.info("Processing test PRs for AI confidence score analysis")

        for test_pr in test_prs:
            repo = test_pr["repo"]
            pr_number = test_pr["pr_number"]

            # Check if AI is disabled for this repository
            if self.github_client.is_ai_disabled_for_repo(repo):
                logger.info(
                    f"🚫 Skipping AI analysis for test PR #{pr_number} from {repo} (AI disabled for repository)"
                )
                continue

            logger.info(f"Analyzing test PR #{pr_number} from {repo}")

            # Get the specific PR
            try:
                pr_url = f"{self.github_client.base_repos_url}{repo}/pulls/{pr_number}"
                response = requests.get(
                    pr_url, headers=self.github_client.headers, timeout=DEFAULT_TIMEOUT
                )

                if response.status_code != 200:
                    logger.warning(
                        f"Failed to fetch PR #{pr_number} from {repo}, skipping..."
                    )
                    continue

                pr_data = response.json()

                # Calculate AI confidence score
                (
                    confidence_score,
                    explanation,
                    is_auto_merge_env,
                    metadata,
                ) = self.ai_calculator.calculate_confidence_score(pr_data)

                # Add AI confidence score comment
                self._add_confidence_score_comment(
                    pr_data,
                    confidence_score=confidence_score,
                    explanation=explanation,
                    is_auto_merge_env=is_auto_merge_env,
                    metadata=metadata,
                )

                logger.info(
                    f"✅ Successfully analyzed test PR #{pr_number} from {repo}"
                )

            except AIServiceError as e:
                logger.error(
                    f"❌ AI Service Error for test PR #{pr_number} from {repo}: {str(e)}"
                )
                # Try to add failure comment to PR
                try:
                    status_code_msg = (
                        f" (HTTP {e.status_code})" if e.status_code else ""
                    )
                    reason = f"Claude Code API Error{status_code_msg}"
                    details = e.error_details if e.error_details else "Unknown error"
                    recommendation = "The AI analysis could not be completed. Please try again later or review manually."
                    self._add_ai_failure_comment(
                        pr_data, reason, details, recommendation
                    )
                except Exception:
                    pass  # If we can't add comment, just log and continue
                continue
            except Exception as e:
                logger.error(
                    f"❌ Unexpected error processing test PR #{pr_number} from {repo}: {str(e)}"
                )
                continue

        # Push metrics to Prometheus Pushgateway if configured
        if self.metrics:
            try:
                self.metrics.push_metrics()
                logger.debug(
                    "Successfully pushed test PR metrics to Prometheus Pushgateway"
                )
            except Exception as e:
                logger.error(
                    f"Failed to push test PR metrics to Prometheus Pushgateway: {e}"
                )

    def _add_confidence_score_comment(
        self,
        pr: Dict[str, Any],
        confidence_score: int,
        explanation: str,
        is_auto_merge_env: bool,
        metadata: Dict[str, Any],
    ) -> None:
        """Add AI confidence score comment to PR.

        Args:
            pr: Pull request data
            confidence_score: Pre-calculated confidence score
            explanation: Pre-calculated explanation
            is_auto_merge_env: Pre-calculated auto-merge environment flag
            metadata: Pre-calculated metadata
        """
        if not self.ai_calculator:
            return

        try:

            # Format the comment using the template
            detected_env = metadata.get("environment", "unknown")
            env_reason = metadata.get("environment_reason", "")
            environment_display = f"{detected_env.title()} (Detected as {detected_env}: {env_reason})" if detected_env != "unknown" else "Unknown"

            # Check if auto-merge should be enabled
            enable_auto_merge = self.config.get("enable_ai_automerge_action", False)
            should_auto_merge = self.ai_calculator.should_auto_merge(
                confidence_score, is_auto_merge_env, enable_auto_merge
            )
            auto_merge_status = "✅ Enabled" if should_auto_merge else "❌ Disabled"

            formatted_comment = COMMENT_CONFIDENCE_SCORE_TEMPLATE.format(
                score=confidence_score,
                explanation=explanation,
                environment=environment_display,
                auto_merge_status=auto_merge_status,
                provider=metadata.get("provider", "Unknown"),
                model=metadata.get("model", "unknown"),
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
            )

            # Check if PR comments are disabled
            disable_comments = self.config.get("disable_pr_comments", False)

            if disable_comments:
                # Only print to terminal
                logger.info(
                    f"🤖 AI Confidence Score Analysis for {format_pr_info(pr)}:"
                )
                logger.info(f"   Comment: {formatted_comment}")
            else:
                # Add comment to PR
                self.github_client.comment_pull_req([pr], formatted_comment, update=False)

            logger.info(
                f"{format_pr_info(pr)}: AI Confidence Score {confidence_score}% - {auto_merge_status}"
            )

            # Apply safe-for-automerge label if score meets threshold
            minimum_score = self.config.get("minimum_confidence_score", 100)
            if confidence_score >= minimum_score:
                existing_labels = [label["name"] for label in pr.get("labels", [])]

                if LABEL_SAFE_FOR_AUTOMERGE not in existing_labels:
                    logger.info(
                        f"   🏷️  Adding '{LABEL_SAFE_FOR_AUTOMERGE}' label (confidence: {confidence_score}% >= {minimum_score}%)"
                    )
                    self.github_client.set_label_to_pull_request(
                        [pr], LABEL_SAFE_FOR_AUTOMERGE
                    )
                else:
                    logger.info(
                        f"   ✅ '{LABEL_SAFE_FOR_AUTOMERGE}' label already present (confidence: {confidence_score}% >= {minimum_score}%)"
                    )

        except Exception as e:
            # Fallback comment in case of error
            error_comment = COMMENT_CONFIDENCE_SCORE_ERROR.format(
                error=str(e),
                score=50,
                explanation="Fallback calculation due to error",
                environment="Unknown",
                auto_merge_status="❌ Disabled (Error)",
            )

            # Check if PR comments are disabled
            disable_comments = self.config.get("disable_pr_comments", False)

            if disable_comments:
                # Only print to terminal
                logger.error(
                    f"🤖 AI Confidence Score Analysis Error for {format_pr_info(pr)}:"
                )
                logger.error(f"   Error: {str(e)}")
                logger.error("   Fallback Score: 50%")
                logger.error("   Explanation: Fallback calculation due to error")
                logger.error("   Environment: Unknown")
                logger.error("   Auto-merge Status: ❌ Disabled (Error)")
                logger.error("   ---")
                logger.error("   *AI analysis failed, using fallback logic.*")
            else:
                # Add comment to PR
                self.github_client.comment_pull_req([pr], error_comment, update=False)

            logger.error(f"{format_pr_info(pr)}: AI Confidence Score Error - {str(e)}")

    def _add_ai_failure_comment(
        self, pr: Dict[str, Any], reason: str, details: str, recommendation: str
    ) -> None:
        """Add AI failure comment to PR when AI analysis cannot be performed.

        Args:
            pr: Pull request data
            reason: Reason for AI failure
            details: Detailed explanation
            recommendation: Recommended action
        """
        # Check if PR comments are disabled
        disable_comments = self.config.get("disable_pr_comments", False)

        if disable_comments:
            # Only print to terminal
            logger.warning(
                f"🤖 AI Confidence Score Analysis Failed for {format_pr_info(pr)}:"
            )
            logger.warning("   Status: ❌ AI Analysis Failed")
            logger.warning(f"   Reason: {reason}")
            logger.warning(f"   Details: {details}")
            logger.warning(f"   Recommendation: {recommendation}")
            logger.warning("   ---")
            logger.warning(
                "   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*"
            )
        else:
            # Add comment to PR
            failure_comment = COMMENT_CONFIDENCE_SCORE_AI_FAILURE.format(
                reason=reason, details=details, recommendation=recommendation
            )
            self.github_client.comment_pull_req([pr], failure_comment, update=False)

        logger.warning(f"{format_pr_info(pr)}: AI Analysis Failed - {reason}")

    def _get_last_ai_comment(self, pr: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get the most recent AI confidence score comment from PR.

        Args:
            pr: Pull request data

        Returns:
            Most recent AI comment dict or None if no AI comments found
        """
        try:
            # Get all comments
            comments_url = pr["issue_url"] + "/comments"
            response = requests.get(
                comments_url,
                headers=self.github_client.headers,
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch comments for {format_pr_info(pr)}")
                return None

            comments = response.json()

            # Find all AI comments (in reverse order, newest first)
            ai_comments = [
                comment
                for comment in reversed(comments)
                if "AI Confidence Score Analysis" in comment.get("body", "")
            ]

            if ai_comments:
                return ai_comments[0]  # Return the most recent one

            return None

        except Exception as e:
            logger.warning(
                f"Error fetching AI comments for {format_pr_info(pr)}: {str(e)}"
            )
            return None

    def _has_recent_valid_ai_comment(
        self, pr: Dict[str, Any], hours: int = 3
    ) -> bool:
        """Check if there's a valid AI comment from the same night (within last N hours).

        This prevents duplicate AI analyses when cronjob runs overlap.
        A valid comment is one that doesn't contain error messages.

        Args:
            pr: Pull request data
            hours: Number of hours to look back (default: 3 hours for same night)

        Returns:
            True if a valid recent AI comment exists, False otherwise
        """
        try:
            # Get all comments
            comments_url = pr["issue_url"] + "/comments"
            response = requests.get(
                comments_url,
                headers=self.github_client.headers,
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                logger.warning(
                    f"Failed to fetch comments for {format_pr_info(pr)} in temporal check"
                )
                return False

            comments = response.json()

            # Get current time
            now = datetime.now(timezone.utc)
            time_threshold = now - timedelta(hours=hours)

            # Check all AI comments in reverse order (newest first)
            for comment in reversed(comments):
                body = comment.get("body", "")
                if "AI Confidence Score Analysis" not in body:
                    continue

                # Check timestamp
                created_at = comment.get("created_at")
                if not created_at:
                    continue

                comment_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

                # If comment is within the time window
                if comment_time >= time_threshold:
                    # Check if it's a valid comment (no errors)
                    error_indicators = [
                        "Error",
                        "attempted relative import",
                        "Failed",
                        "Exception",
                    ]

                    has_errors = any(indicator in body for indicator in error_indicators)

                    if not has_errors:
                        logger.info(
                            f"   ⏰ Found valid AI comment from {comment_time.strftime('%Y-%m-%d %H:%M:%S UTC')} "
                            f"(within last {hours}h), skipping duplicate analysis"
                        )
                        return True

            return False

        except Exception as e:
            logger.warning(
                f"Error in temporal AI comment check for {format_pr_info(pr)}: {str(e)}"
            )
            # If we can't check, err on the side of caution and allow analysis
            return False

    def _extract_score_from_comment(self, comment: Dict[str, Any]) -> Optional[int]:
        """Extract confidence score from AI comment.

        Args:
            comment: Comment dictionary

        Returns:
            Confidence score as integer or None if not found
        """
        import re

        body = comment.get("body", "")

        # Try to extract score with pattern: **Confidence Score:** XX%
        match = re.search(r"\*\*Confidence Score:\*\* (\d+)%", body)
        if match:
            return int(match.group(1))

        return None

    def _extract_most_similar_pr_from_comment(
        self, comment: Dict[str, Any]
    ) -> Optional[int]:
        """Extract most similar PR number from AI comment with similarity boost.

        Args:
            comment: Comment dictionary

        Returns:
            Most similar PR number or None if not found
        """
        import re

        body = comment.get("body", "")

        # Pattern: [Similarity boost applied: XX% → YY%, similar to PR #ZZZ, evaluated N safe example(s)]
        match = re.search(
            r"Similarity boost applied: \d+% → \d+%, similar to PR #(\d+), evaluated \d+ safe example",
            body,
        )
        if match:
            return int(match.group(1))

        return None

    def _files_changed_since_comment(
        self, pr: Dict[str, Any], comment: Dict[str, Any]
    ) -> bool:
        """Check if there were any commits to the PR after the given comment.

        This checks for actual code commits, not just PR updates like comments,
        labels, or reviews. Only returns True if there's at least one commit
        after the comment timestamp.

        Args:
            pr: Pull request data
            comment: Comment to check against

        Returns:
            True if there are commits after the comment, False otherwise
        """
        try:
            comment_created_at = comment.get("created_at")
            if not comment_created_at:
                # If we can't determine comment time, assume files changed
                return True

            # Check for debug environment variable to force AI analysis
            force_analysis = (
                os.environ.get("DEBUG_FORCE_AI_ANALYSIS", "false").lower() == "true"
            )
            if force_analysis:
                logger.info(
                    "   🔧 DEBUG_FORCE_AI_ANALYSIS is enabled, forcing new AI analysis"
                )
                return True

            # Get commits for this PR to check if code actually changed
            commits_url = pr.get("commits_url")
            if not commits_url:
                logger.warning(
                    f"No commits_url found for {format_pr_info(pr)}, assuming files changed"
                )
                return True

            response = requests.get(
                commits_url,
                headers=self.github_client.headers,
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                logger.warning(
                    f"Failed to fetch commits for {format_pr_info(pr)}, assuming files changed"
                )
                return True

            commits = response.json()

            if not commits:
                logger.info("   ℹ️  No commits found in PR")
                return False

            # Parse comment timestamp
            comment_time = datetime.fromisoformat(
                comment_created_at.replace("Z", "+00:00")
            )

            # Check if any commit was made after the comment
            commits_after_comment = []
            for commit in commits:
                commit_date_str = commit.get("commit", {}).get("author", {}).get("date")
                if commit_date_str:
                    commit_time = datetime.fromisoformat(
                        commit_date_str.replace("Z", "+00:00")
                    )
                    if commit_time > comment_time:
                        commits_after_comment.append(
                            {
                                "sha": commit.get("sha", "")[:7],
                                "date": commit_date_str,
                                "message": commit.get("commit", {})
                                .get("message", "")
                                .split("\n")[0][:50],
                            }
                        )

            if commits_after_comment:
                logger.info(
                    f"   📝 Found {len(commits_after_comment)} commit(s) after last AI analysis"
                )
                for c in commits_after_comment[:3]:  # Log first 3
                    logger.info(f"      - {c['sha']}: {c['message']}")
                if len(commits_after_comment) > 3:
                    logger.info(f"      ... and {len(commits_after_comment) - 3} more")
                return True
            else:
                logger.info(
                    f"   ✅ No commits since last AI analysis ({comment_time.isoformat()})"
                )
                return False

        except Exception as e:
            logger.warning(
                f"Error checking file changes for {format_pr_info(pr)}: {str(e)}"
            )
            # On error, assume files changed to be safe
            return True

    def process_prs(self, all_pulls: List[Dict[str, Any]], force: bool) -> None:
        """Process all pull requests based on their categorization.

        Args:
            all_pulls: List of all pull requests to process
            force: Whether to force planning of all PRs
        """
        (
            pr_list_no_comments,
            pr_with_diffs,
            pr_list_no_changes,
            pr_list_error,
            list_to_be_closed,
            list_dismissed,
        ) = self.create_pr_lists(all_pulls, force)

        if pr_list_no_changes:
            logger.info("Merging what's possible")
            self.github_client.merge_pull_req(pr_list_no_changes)

        if list_dismissed:
            logger.info(
                "Processing dismissed PRs - re-approving and checking for merging"
            )
            self.github_client.process_dismissed_prs(list_dismissed)

        if pr_with_diffs:
            logger.info("Unlocking PR")

            # Process AI analysis for configured repositories
            enable_ai = self.config.get("enable_ai_confidence_score", False)

            for pr in pr_with_diffs:
                # Check if this repo is in AI repos list and AI is enabled
                if enable_ai and self.ai_calculator:
                    # Check if AI is disabled for this specific repository
                    repo_name = pr.get("head", {}).get("repo", {}).get("name", "")
                    if repo_name and self.github_client.is_ai_disabled_for_repo(
                        repo_name
                    ):
                        logger.info(
                            f"🚫 Skipping AI analysis for {format_pr_info(pr)} (AI disabled for repository)"
                        )
                        # Continue with standard unlock process
                        self.github_client.multi_comments_pull_req(
                            [pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE
                        )
                        self.github_client.set_label_to_pull_request(
                            [pr], LABEL_AUTOMERGE_IGNORE
                        )
                        continue

                    logger.info(
                        f"🤖 Processing AI analysis for {format_pr_info(pr)} (AI-enabled repo)"
                    )

                    try:
                        # FIRST: Check if there's a recent valid AI comment from same night
                        # This prevents duplicate analyses when cronjob runs overlap
                        if self._has_recent_valid_ai_comment(pr, hours=3):
                            logger.info(
                                f"   ⏭️  Skipping AI analysis for {format_pr_info(pr)} - valid comment already exists from same night"
                            )
                            # Don't continue - let standard unlock process run at line 921+
                        else:
                            # Check if there's a previous AI analysis
                            last_ai_comment = self._get_last_ai_comment(pr)
                            confidence_score = None
                            should_auto_merge = False
                            needs_new_analysis = True

                            if last_ai_comment:
                                # Check if files changed since last analysis
                                files_changed = self._files_changed_since_comment(
                                    pr, last_ai_comment
                                )

                                if not files_changed:
                                    # No changes, but check if most similar PR changed
                                    logger.info("   🔍 Checking if new safe examples are available...")

                                    # Get current most similar PR
                                    current_most_similar = self.ai_calculator.get_most_similar_pr(pr)

                                    # Get previous most similar PR from last comment
                                    previous_most_similar = self._extract_most_similar_pr_from_comment(
                                        last_ai_comment
                                    )

                                    if current_most_similar and previous_most_similar and current_most_similar != previous_most_similar:
                                        # Different similar PR found, re-analyze with new boost
                                        logger.info(
                                            f"   🔄 Found new similar PR #{current_most_similar} (was #{previous_most_similar}), re-analyzing..."
                                        )
                                        needs_new_analysis = True
                                    elif current_most_similar and not previous_most_similar:
                                        # New similar PR found (previously had none)
                                        logger.info(
                                            f"   🆕 Found new similar PR #{current_most_similar} (previously none), re-analyzing..."
                                        )
                                        needs_new_analysis = True
                                    else:
                                        # Same similar PR or no similar PRs, reuse score
                                        confidence_score = self._extract_score_from_comment(
                                            last_ai_comment
                                        )
                                        if confidence_score is not None:
                                            if current_most_similar:
                                                logger.info(
                                                    f"   ♻️  Reusing previous AI analysis (score: {confidence_score}%, similar PR unchanged: #{current_most_similar})"
                                                )
                                            else:
                                                logger.info(
                                                    f"   ♻️  Reusing previous AI analysis (score: {confidence_score}%, no similar PRs)"
                                                )
                                            needs_new_analysis = False
                                        else:
                                            logger.warning(
                                                "   ⚠️  Could not extract score from previous comment, will re-analyze"
                                            )

                            if needs_new_analysis:
                                # Perform new AI analysis (ONE TIME ONLY)
                                logger.info("   🔍 Performing new AI analysis...")
                                (
                                    confidence_score,
                                    explanation,
                                    is_auto_merge_env,
                                    metadata,
                                ) = self.ai_calculator.calculate_confidence_score(pr)

                                # Check if auto-merge should be enabled
                                enable_auto_merge = self.config.get(
                                    "enable_ai_automerge_action", False
                                )
                                should_auto_merge = self.ai_calculator.should_auto_merge(
                                    confidence_score, is_auto_merge_env, enable_auto_merge
                                )

                                # Add AI comment (passing pre-calculated values, no re-calculation)
                                self._add_confidence_score_comment(
                                    pr,
                                    confidence_score=confidence_score,
                                    explanation=explanation,
                                    is_auto_merge_env=is_auto_merge_env,
                                    metadata=metadata,
                                )

                            # Auto-merge if conditions are met (only if new analysis was done)
                            if needs_new_analysis and should_auto_merge:
                                logger.info(
                                    f"   🚀 Auto-merging {format_pr_info(pr)} (confidence: {confidence_score}%, auto-merge environment)"
                                )
                                self.github_client.merge_pull_req([pr])
                                continue  # Skip standard unlock process
                            elif needs_new_analysis:
                                logger.info(
                                    f"   📋 Manual merge required for {format_pr_info(pr)} (confidence: {confidence_score}%)"
                                )

                    except AIServiceError as e:
                        logger.error(
                            f"   ❌ AI Service Error for {format_pr_info(pr)}: {str(e)}"
                        )
                        # Add failure comment to PR with error details
                        status_code_msg = (
                            f" (HTTP {e.status_code})" if e.status_code else ""
                        )
                        reason = f"Claude Code API Error{status_code_msg}"
                        details = (
                            e.error_details if e.error_details else "Unknown error"
                        )
                        recommendation = "The AI analysis could not be completed. This PR will be processed with standard unlock flow. Please review manually."

                        self._add_ai_failure_comment(
                            pr, reason, details, recommendation
                        )
                        # Skip AI analysis and continue with standard unlock process
                    except Exception as e:
                        logger.error(
                            f"   ❌ Unexpected error during AI analysis for {format_pr_info(pr)}: {str(e)}"
                        )
                        # For unexpected errors, add a generic failure comment
                        self._add_ai_failure_comment(
                            pr,
                            "Unexpected Error",
                            str(e),
                            "An unexpected error occurred during AI analysis. Please review manually.",
                        )
                        # Continue with standard unlock process

                # Standard unlock process (if not auto-merged)
                self.github_client.multi_comments_pull_req(
                    [pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE
                )

                self.github_client.set_label_to_pull_request(
                    [pr], LABEL_AUTOMERGE_IGNORE
                )

        if pr_list_no_comments or pr_list_error:
            logger.info("Commenting to plan PRs")
            for pr in pr_list_no_comments + pr_list_error:
                mergeable_state = self.github_client.get_mergeable_state(pr["url"])
                if mergeable_state == "dirty":
                    logger.warning(
                        f"{format_pr_info(pr)} Is dirty, there are conflicts, ignoring..."
                    )
                    self.github_client.multi_comments_pull_req(
                        [pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE
                    )
                    self.github_client.set_label_to_pull_request(
                        [pr], LABEL_AUTOMERGE_CONFLICT
                    )
                    continue
                self.github_client.comment_pull_req([pr], COMMENT_ATLANTIS_PLAN)

        if list_to_be_closed:
            logger.info("Closing old PRs")
            self.github_client.multi_comments_pull_req(
                list_to_be_closed, COMMENT_CLOSE_NEW_VERSION, COMMENT_ATLANTIS_UNLOCK
            )
            self.github_client.close_pull_requests(list_to_be_closed)

        # Push metrics to Prometheus Pushgateway if configured
        if self.metrics:
            try:
                self.metrics.push_metrics()
                logger.debug("Successfully pushed metrics to Prometheus Pushgateway")
            except Exception as e:
                logger.error(f"Failed to push metrics to Prometheus Pushgateway: {e}")
