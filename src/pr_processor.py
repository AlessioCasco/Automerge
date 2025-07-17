#!/usr/bin/env python3

import re
from typing import Dict, List, Any, Tuple, Optional

from github_client import GitHubClient
from utils import (
    LABEL_AUTOMERGE_IGNORE,
    LABEL_AUTOMERGE_NO_PROJECT,
    LABEL_AUTOMERGE_CONFLICT,
    COMMENT_ATLANTIS_PLAN,
    COMMENT_ATLANTIS_UNLOCK,
    COMMENT_IGNORE_AUTOMERGE,
    COMMENT_CLOSE_NEW_VERSION,
    COMMENT_NO_PROJECT,
    format_pr_info,
)


class PRProcessor:
    """Handles PR processing and categorization logic."""
    
    def __init__(self, github_client: GitHubClient):
        """Initialize PR processor.
        
        Args:
            github_client: GitHub client instance
        """
        self.github_client = github_client
        
        # Compile regex patterns for efficiency
        self.regexp_pr_diff = re.compile(
            r"Plan: [0-9]* to add, [0-9]* to change, [0-9]* to destroy.|Changes to Outputs")
        self.regexp_pr_no_changes = re.compile(
            r"No changes. Your infrastructure matches the configuration|Apply complete!")
        self.regexp_pr_ignore = re.compile(
            r"This PR will be ignored by automerge")
        self.regexp_pr_error = re.compile(
            r"Plan Error|Plan Failed|Continued plan output from previous comment.|via the Atlantis UI|All Atlantis locks for this PR have been unlocked and plans discarded|Renovate will not automatically rebase this PR|Apply Failed|Apply Error")
        self.regexp_pr_still_working = re.compile(r"atlantis plan|atlantis apply")
        self.regexp_pr_no_project = re.compile(r"Ran Plan for 0 projects")
        self.regexp_new_version = re.compile(r"A newer version of")

    def create_pr_lists(self, all_pull_req: List[Dict[str, Any]], force: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Categorize pull requests into different lists based on their state.
        
        Args:
            all_pull_req: List of all pull requests to process
            force: Whether to force planning of all PRs
            
        Returns:
            Tuple of (no_comments, with_diffs, no_changes, error, to_be_closed) lists
        """
        list_no_comments = []
        list_with_diffs = []
        list_no_changes = []
        list_error = []
        list_to_be_closed = []

        for pull_req in all_pull_req:
            last_comment = self.github_client.get_last_comment(pull_req["issue_url"])

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
                    self.github_client.set_label_to_pull_request([pull_req], LABEL_AUTOMERGE_NO_PROJECT)
                    continue

                print(f"{format_pr_info(pull_req)}: *** Not match, please check why!!!***")

        return (list_no_comments, list_with_diffs, list_no_changes, list_error, list_to_be_closed)

    def process_prs(self, all_pulls: List[Dict[str, Any]], force: bool) -> None:
        """Process all pull requests based on their categorization.
        
        Args:
            all_pulls: List of all pull requests to process
            force: Whether to force planning of all PRs
        """
        pr_list_no_comments, pr_with_diffs, pr_list_no_changes, pr_list_error, list_to_be_closed = self.create_pr_lists(
            all_pulls, force)

        if pr_list_no_changes:
            print("\nMerging what's possible\n")
            self.github_client.merge_pull_req(pr_list_no_changes)

        if pr_with_diffs:
            print("\nUnlocking PR\n")
            self.github_client.multi_comments_pull_req(pr_with_diffs, COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
            self.github_client.set_label_to_pull_request(pr_with_diffs, LABEL_AUTOMERGE_IGNORE)

        if pr_list_no_comments or pr_list_error:
            print("\n\nCommenting to plan PRs\n")
            for pr in pr_list_no_comments + pr_list_error:
                mergeable_state = self.github_client.get_mergeable_state(pr["url"])
                if mergeable_state == "dirty":
                    print(f"{format_pr_info(pr)} Is dirty, there are conflicts, ignoring...")
                    self.github_client.multi_comments_pull_req([pr], COMMENT_ATLANTIS_UNLOCK, COMMENT_IGNORE_AUTOMERGE)
                    self.github_client.set_label_to_pull_request([pr], LABEL_AUTOMERGE_CONFLICT)
                    continue
                self.github_client.comment_pull_req([pr], COMMENT_ATLANTIS_PLAN)

        if list_to_be_closed:
            print("\nClosing old PRs\n")
            self.github_client.multi_comments_pull_req(list_to_be_closed, COMMENT_CLOSE_NEW_VERSION, COMMENT_ATLANTIS_UNLOCK)
            self.github_client.close_pull_requests(list_to_be_closed) 