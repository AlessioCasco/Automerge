#!/usr/bin/env python3

import re
import requests
from typing import Dict, List, Any, Tuple, Optional

try:
    from .github_client import GitHubClient
    from .ai_confidence import AIConfidenceCalculator
    from .utils import (
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
except ImportError:
    from github_client import GitHubClient
    from ai_confidence import AIConfidenceCalculator
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

    def __init__(self, github_client: GitHubClient, config: Dict[str, Any]):
        """Initialize PR processor.

        Args:
            github_client: GitHub client instance
            config: Configuration dictionary
        """
        self.github_client = github_client
        self.config = config

        # Initialize AI confidence calculator if enabled
        self.ai_calculator = None
        if config.get("enable_ai_confidence_score", False):
            self.ai_calculator = AIConfidenceCalculator(
                config["access_token"],
                self.github_client,
                config
            )

        # Compile regex patterns for efficiency
        self.regexp_pr_diff = re.compile(
            r"Plan: [0-9]* to add, [0-9]* to change, [0-9]* to destroy\.|Changes to Outputs")
        self.regexp_pr_no_changes = re.compile(
            r"No changes. Your infrastructure matches the configuration|Apply complete!")
        self.regexp_pr_ignore = re.compile(
            r"This PR will be ignored by automerge")
        self.regexp_pr_error = re.compile(
            r"Plan Error|Plan Failed|Continued plan output from previous comment.|via the Atlantis UI|All Atlantis locks for this PR have been unlocked and plans discarded|Renovate will not automatically rebase this PR|Apply Failed|Apply Error")
        self.regexp_pr_still_working = re.compile(
            r"atlantis plan|atlantis apply")
        self.regexp_pr_no_project = re.compile(r"Ran Plan for 0 projects")
        self.regexp_new_version = re.compile(r"A newer version of")

    def create_pr_lists(self, all_pull_req: List[Dict[str, Any]], force: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
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
            last_comment = self.github_client.get_last_comment(
                pull_req["issue_url"])

            # Check if PR is dismissed and should be re-approved
            approval_status = self.github_client.is_approved(pull_req["url"])
            if approval_status == REVIEW_STATE_DISMISSED:
                list_dismissed.append(pull_req)
                print(f"{format_pr_info(pull_req)}: Dismissed, will re-approve and check for merging.")
                continue

            if not last_comment:
                list_no_comments.append(pull_req)
                print(f"{format_pr_info(pull_req)}: No Comments, new pr.")
                continue

            if self.regexp_pr_no_changes.search(last_comment["body"]):
                list_no_changes.append(pull_req)
                print(f"{format_pr_info(pull_req)}: No changes.")
                continue

            # If --force is enabled, we will plan all PRs to avoid automerge to ignore PRs that had issues
            if force:
                print(f"{format_pr_info(pull_req)}: Will be forced to plan")
                list_no_comments.append(pull_req)
                continue
            else:
                if self.regexp_pr_diff.search(last_comment["body"]):
                    list_with_diffs.append(pull_req)
                    print(f"{format_pr_info(pull_req)}: There are diffs or conflicts.")
                    continue

                if self.regexp_pr_error.search(last_comment["body"]):
                    list_error.append(pull_req)
                    print(f"{format_pr_info(pull_req)}: Has errors.")
                    continue

                if self.regexp_new_version.search(last_comment["body"]):
                    list_to_be_closed.append(pull_req)
                    print(f"{format_pr_info(pull_req)}: {COMMENT_CLOSE_NEW_VERSION}")
                    continue

                if self.regexp_pr_still_working.search(last_comment["body"]):
                    print(f"{format_pr_info(pull_req)}: Atlantis is still working here, ignoring this PR for now.")
                    continue

                if self.regexp_pr_ignore.search(last_comment["body"]):
                    print(f"{format_pr_info(pull_req)}: Will be ignored, there are diffs")
                    continue

                if self.regexp_pr_no_project.search(last_comment["body"]):
                    print(f"{format_pr_info(pull_req)}: {COMMENT_NO_PROJECT}")
                    self.github_client.set_label_to_pull_request(
                        [pull_req], LABEL_AUTOMERGE_NO_PROJECT)
                    continue

                print(f"{format_pr_info(pull_req)}: *** Not match, please check why!!!***")

        return (list_no_comments, list_with_diffs, list_no_changes, list_error, list_to_be_closed, list_dismissed)

    def process_test_prs(self, test_prs: List[Dict[str, Any]]) -> None:
        """Process specific test PRs for AI confidence score analysis.

        Args:
            test_prs: List of test PRs to analyze
        """
        if not self.ai_calculator:
            print("AI confidence score calculation is disabled, skipping test PRs")
            return

        print("\nProcessing test PRs for AI confidence score analysis\n")

        for test_pr in test_prs:
            repo = test_pr["repo"]
            pr_number = test_pr["pr_number"]

            print(f"Analyzing test PR #{pr_number} from {repo}")

            # Get the specific PR
            try:
                pr_url = f"{self.github_client.base_repos_url}{repo}/pulls/{pr_number}"
                response = requests.get(
                    pr_url, headers=self.github_client.headers, timeout=DEFAULT_TIMEOUT)

                if response.status_code != 200:
                    print(f"Failed to fetch PR #{pr_number} from {repo}, skipping...")
                    continue

                pr_data = response.json()

                # Add AI confidence score comment
                self._add_confidence_score_comment(pr_data, None)

                print(f"✅ Successfully analyzed test PR #{pr_number} from {repo}")

            except Exception as e:
                print(f"❌ Error processing test PR #{pr_number} from {repo}: {str(e)}")
                continue

    def _add_confidence_score_comment(self, pr: Dict[str, Any], last_comment: Optional[Dict[str, Any]] = None) -> None:
        """Add AI confidence score comment to PR.

        Args:
            pr: Pull request data
            last_comment: Last comment from the PR (deprecated, kept for compatibility)
        """
        if not self.ai_calculator:
            return

        try:
            # Calculate confidence score
            confidence_score, explanation, is_dev_env, metadata = self.ai_calculator.calculate_confidence_score(pr)

            # Determine environment string
            environment = "Development" if is_dev_env else "Production/Protected"

            # Check if auto-merge should be enabled
            enable_auto_merge = self.config.get("enable_ai_automerge_action", False)
            should_auto_merge = self.ai_calculator.should_auto_merge(confidence_score, is_dev_env, enable_auto_merge)

            auto_merge_status = "✅ Enabled" if should_auto_merge else "❌ Disabled"

            # Format comment with metadata
            comment = COMMENT_CONFIDENCE_SCORE_TEMPLATE.format(
                score=confidence_score,
                explanation=explanation,
                environment=environment,
                auto_merge_status=auto_merge_status,
                provider=metadata.get("provider", "Unknown"),
                model=metadata.get("model", "unknown"),
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0)
            )

            # Check if PR comments are disabled
            disable_comments = self.config.get("disable_pr_comments", False)

            if disable_comments:
                # Only print to terminal
                print(f"\n🤖 AI Confidence Score Analysis for {format_pr_info(pr)}:")
                print(f"   Confidence Score: {confidence_score}%")
                print(f"   Explanation: {explanation}")
                print(f"   Environment: {environment}")
                print(f"   Auto-merge Status: {auto_merge_status}")
                print(f"   AI Provider: {metadata.get('provider', 'Unknown')} ({metadata.get('model', 'unknown')})")
                print(f"   Token Usage: {metadata.get('input_tokens', 0)} input, {metadata.get('output_tokens', 0)} output")
                print("   ---")
                print(f"   *This analysis was performed by {metadata.get('provider', 'Unknown')} AI to assess the safety of automatic merging.*")
            else:
                # Add comment to PR
                self.github_client.comment_pull_req([pr], comment, update=False)

            print(f"{format_pr_info(pr)}: AI Confidence Score {confidence_score}% - {auto_merge_status}")

        except Exception as e:
            # Fallback comment in case of error
            error_comment = COMMENT_CONFIDENCE_SCORE_ERROR.format(
                error=str(e),
                score=50,
                explanation="Fallback calculation due to error",
                environment="Unknown",
                auto_merge_status="❌ Disabled (Error)"
            )

            # Check if PR comments are disabled
            disable_comments = self.config.get("disable_pr_comments", False)

            if disable_comments:
                # Only print to terminal
                print(f"\n🤖 AI Confidence Score Analysis Error for {format_pr_info(pr)}:")
                print(f"   Error: {str(e)}")
                print("   Fallback Score: 50%")
                print("   Explanation: Fallback calculation due to error")
                print("   Environment: Unknown")
                print("   Auto-merge Status: ❌ Disabled (Error)")
                print("   ---")
                print("   *AI analysis failed, using fallback logic.*")
            else:
                # Add comment to PR
                self.github_client.comment_pull_req([pr], error_comment, update=False)

            print(f"{format_pr_info(pr)}: AI Confidence Score Error - {str(e)}")

    def _add_ai_failure_comment(self, pr: Dict[str, Any], reason: str, details: str, recommendation: str) -> None:
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
            print(f"\n🤖 AI Confidence Score Analysis Failed for {format_pr_info(pr)}:")
            print("   Status: ❌ AI Analysis Failed")
            print(f"   Reason: {reason}")
            print(f"   Details: {details}")
            print(f"   Recommendation: {recommendation}")
            print("   ---")
            print("   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*")
        else:
            # Add comment to PR
            failure_comment = COMMENT_CONFIDENCE_SCORE_AI_FAILURE.format(
                reason=reason,
                details=details,
                recommendation=recommendation
            )
            self.github_client.comment_pull_req([pr], failure_comment, update=False)

        print(f"{format_pr_info(pr)}: AI Analysis Failed - {reason}")

    def process_prs(self, all_pulls: List[Dict[str, Any]], force: bool) -> None:
        """Process all pull requests based on their categorization.

        Args:
            all_pulls: List of all pull requests to process
            force: Whether to force planning of all PRs
        """
        pr_list_no_comments, pr_with_diffs, pr_list_no_changes, pr_list_error, list_to_be_closed, list_dismissed = self.create_pr_lists(
            all_pulls, force)

        if pr_list_no_changes:
            print("\nMerging what's possible\n")
            self.github_client.merge_pull_req(pr_list_no_changes)

        if list_dismissed:
            print("\nProcessing dismissed PRs - re-approving and checking for merging\n")
            self.github_client.process_dismissed_prs(list_dismissed)

        if pr_with_diffs:
            print("\nUnlocking PR\n")

            # Process AI analysis for configured repositories
            ai_repos = self.config.get("ai_repos", [])
            enable_ai = self.config.get("enable_ai_confidence_score", False)

            for pr in pr_with_diffs:
                repo_name = pr["head"]["repo"]["name"]

                # Check if this repo is in AI repos list and AI is enabled
                if repo_name in ai_repos and enable_ai and self.ai_calculator:
                    print(f"\n🤖 Processing AI analysis for {format_pr_info(pr)} (AI-enabled repo)")

                    try:
                        # Check if AI comment already exists
                        last_comment = self.github_client.get_last_comment(pr["issue_url"])
                        has_ai_comment = False

                        if last_comment and "AI Confidence Score Analysis" in last_comment.get("body", ""):
                            has_ai_comment = True
                            print("   AI analysis already performed, skipping...")

                        if not has_ai_comment:
                            # Get Terraform plan from comments
                            terraform_plan = self.github_client.get_last_terraform_plan(pr["url"])

                            if not terraform_plan:
                                # No plan found
                                self._add_ai_failure_comment(
                                    pr,
                                    "No Terraform plan found",
                                    "Atlantis has not yet generated a plan for this PR, or the plan has been deleted.",
                                    "Wait for Atlantis to complete the plan or trigger a new plan manually."
                                )
                            else:
                                # Valid plan found - perform AI analysis
                                confidence_score, explanation, is_dev_env, metadata = self.ai_calculator.calculate_confidence_score(pr)

                                # Check if auto-merge should be enabled
                                enable_auto_merge = self.config.get("enable_ai_automerge_action", False)
                                should_auto_merge = self.ai_calculator.should_auto_merge(confidence_score, is_dev_env, enable_auto_merge)

                                # Add AI comment
                                self._add_confidence_score_comment(pr)

                                # Auto-merge if conditions are met
                                if should_auto_merge:
                                    print(f"   🚀 Auto-merging {format_pr_info(pr)} (100% confidence, dev environment)")
                                    self.github_client.merge_pull_req([pr])
                                    continue  # Skip standard unlock process
                                else:
                                    print(f"   📋 Manual merge required for {format_pr_info(pr)} (confidence: {confidence_score}%, dev: {is_dev_env})")

                    except Exception as e:
                        print(f"   ❌ Error during AI analysis for {format_pr_info(pr)}: {str(e)}")
                        # Continue with standard unlock process

                # Standard unlock process (if not auto-merged)
                self.github_client.multi_comments_pull_req(
                    [pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)

                self.github_client.set_label_to_pull_request(
                    [pr], LABEL_AUTOMERGE_IGNORE)

        if pr_list_no_comments or pr_list_error:
            print("\n\nCommenting to plan PRs\n")
            for pr in pr_list_no_comments + pr_list_error:
                mergeable_state = self.github_client.get_mergeable_state(
                    pr["url"])
                if mergeable_state == "dirty":
                    print(
                        f"{format_pr_info(pr)} Is dirty, there are conflicts, ignoring...")
                    self.github_client.multi_comments_pull_req(
                        [pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
                    self.github_client.set_label_to_pull_request(
                        [pr], LABEL_AUTOMERGE_CONFLICT)
                    continue
                self.github_client.comment_pull_req(
                    [pr], COMMENT_ATLANTIS_PLAN)

        if list_to_be_closed:
            print("\nClosing old PRs\n")
            self.github_client.multi_comments_pull_req(
                list_to_be_closed, COMMENT_CLOSE_NEW_VERSION, COMMENT_ATLANTIS_UNLOCK)
            self.github_client.close_pull_requests(list_to_be_closed)
