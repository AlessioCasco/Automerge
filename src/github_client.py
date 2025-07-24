#!/usr/bin/env python3

import json
import re
import time
from typing import Dict, List, Optional, Any, Union

import requests
from rich.console import Console

try:
    from .utils import (
        DEFAULT_TIMEOUT,
        MERGEABLE_STATE_TIMEOUT,
        GITHUB_API_VERSION,
        GITHUB_ACCEPT_HEADER,
    )
except ImportError:
    from utils import (
        DEFAULT_TIMEOUT,
        MERGEABLE_STATE_TIMEOUT,
        GITHUB_API_VERSION,
        GITHUB_ACCEPT_HEADER,
    )


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, access_token: str, owner: str, github_user: str):
        """Initialize GitHub client.

        Args:
            access_token: GitHub access token
            owner: Repository owner
            github_user: GitHub username for the token
        """
        self.access_token = access_token
        self.owner = owner
        self.github_user = github_user
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": GITHUB_ACCEPT_HEADER,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        self.base_repos_url = f"https://api.github.com/repos/{owner}/"
        self.console = Console()

    def get_pull_requests(self, repos: List[str], filters: List[str]) -> List[Dict[str, Any]]:
        """Get all pull requests that match the filter in the title.

        Args:
            repos: List of repositories to check
            filters: Regex patterns used to filter pull request titles

        Returns:
            List of pull requests that match the filters

        Raises:
            SystemExit: If no filters provided or API call fails
        """
        dependency_prs = []

        # Check that we have at least one filter
        if not filters:
            print("No filters to match, please provide at least one, exiting")
            raise SystemExit(1)

        for repo in repos:
            pr_url = self.base_repos_url + repo + "/pulls?per_page=100"

            print(f"Fetching all PR's from {repo}")

            response = requests.get(
                pr_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
            if response.status_code != 200:
                print(
                    f"Failed to get pull request. \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
                raise SystemExit(1)

            pull_requests = json.loads(response.text)

            # Filter pull requests by title
            for pr in pull_requests:
                for filter_pattern in filters:
                    if re.match(filter_pattern, pr["title"]):
                        dependency_prs.append(pr)

        print("All pull requests fetched\n")
        return dependency_prs

    def update_branch(self, pull_req_list: List[Dict[str, Any]]) -> None:
        """Update a branch.

        Args:
            pull_req_list: List of pull requests to update

        Raises:
            SystemExit: If API call fails
        """
        for pull_req in pull_req_list:
            update_url = pull_req["url"] + "/update-branch"
            print(f"Updating PR Number: {pull_req['number']} in repo {pull_req['head']['repo']['name']}")

            response = requests.put(
                update_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
            if response.status_code != 202:
                print(
                    f"Failed to update branch in pull request {pull_req['number']} in repo {pull_req['head']['repo']['name']} \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
                raise SystemExit(1)

    def get_last_comment(self, pull_req_url: str) -> Optional[Dict[str, Any]]:
        """Get the last comment from a given pull request.

        Args:
            pull_req_url: URL of the pull request

        Returns:
            The last comment from the pull request or None if no comments
        """
        comments_url = pull_req_url + "/comments?per_page=50"
        response = requests.get(
            comments_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            return None
        comments = json.loads(response.text)

        # Handle pagination using headers
        if "Link" in response.headers:
            links = response.headers["Link"].split(", ")
            for link in links:
                if 'rel="last"' in link:
                    last_page_url = link[link.index("<") + 1: link.index(">")]
                    last_page_response = requests.get(
                        last_page_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
                    if last_page_response.status_code == 200:
                        last_page_comments = json.loads(
                            last_page_response.text)
                        if last_page_comments:
                            return last_page_comments[-1]

        if comments:
            return comments[-1]
        return None

    def get_mergeable_state(self, url: str) -> str:
        """Get the mergeable state of the PR.

        Args:
            url: URL to use for the API call

        Returns:
            Mergeable state of the pull request
        """
        response = requests.get(
            url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            print(
                f"Failed to get info for pull request \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
        return json.loads(response.text)["mergeable_state"]

    def is_approved(self, url: str) -> Optional[Union[bool, str]]:
        """Check if PR is approved already.

        Args:
            url: URL to use for the API call

        Returns:
            True if approved, False if not approved, None if no review found, "Dismissed" if dismissed
        """
        response = requests.get(
            url + "/reviews", headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            print(
                f"Failed to get check if pull request is approved \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")

        for pr in json.loads(response.text):
            # Checking only if our user approves it
            if pr["user"]["login"] == self.github_user:
                if pr["state"] == "APPROVED":
                    return True
                elif pr["state"] == "DISMISSED":
                    return "Dismissed"
                else:
                    return False
        return None

    def approve(self, url: str) -> None:
        """Approve a pull request.

        Args:
            url: URL to use for the API call

        Raises:
            SystemExit: If API call fails
        """
        response = requests.post(
            url + "/reviews",
            headers=self.headers,
            json={"event": "APPROVE"},
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code != 200:
            print(
                f"Failed to approve pull request \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
            raise SystemExit(1)
        print("PR Approved")

    def comment_pull_req(
        self,
        pull_req: List[Dict[str, Any]],
        comment: str,
        update: bool = True,
    ) -> None:
        """Write a comment in the PR.

        Args:
            pull_req: List of pull requests to comment on
            comment: Comment string to write
            update: Whether to update the branch before commenting
        """
        comment_data = {
            "body": comment,
        }

        for pr in pull_req:
            pr_url_4_comments = pr["comments_url"]
            skip_pr = False

            if update:
                mergeable_state = self.get_mergeable_state(pr["url"])
                print(f"\n*** PR {pr['number']} ***\n")

                # Setting a timer for the mergeable state
                timeout = time.time() + MERGEABLE_STATE_TIMEOUT
                with self.console.status("[bold green]Waiting for mergeable state to return..."):
                    while mergeable_state == "unknown":
                        mergeable_state = self.get_mergeable_state(pr["url"])
                        if time.time() > timeout:
                            skip_pr = True
                            print("Timeout expired, moving on...")
                            break
                        time.sleep(1)

                if skip_pr:
                    print(
                        f"PR {pr['number']}: Timeout expired waiting for state to be green at step 1, skipping")
                    continue

                if mergeable_state == "behind":
                    print(f"PR {pr['number']} is behind, updating branch")
                    self.update_branch([pr])

                # Wait for all checks to pass
                with self.console.status("[bold green]Waiting for all checks to pass..."):
                    while mergeable_state != "blocked":
                        mergeable_state = self.get_mergeable_state(pr["url"])
                        if time.time() > timeout:
                            skip_pr = True
                            print("Timeout expired, moving on...")
                            break
                        time.sleep(4)

                if skip_pr:
                    print(
                        f"PR {pr['number']}: Timeout expired waiting for state to be green at step 2, skipping")
                    continue

            response = requests.post(
                pr_url_4_comments,
                json=comment_data,
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT)
            if response.status_code != 201:
                print(
                    f"Failed to add comment to pull request {pr['number']} \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")

            print(f"PR {pr['number']} Commented")

    def multi_comments_pull_req(self, pull_req: List[Dict[str, Any]], comment1: str, comment2: str) -> None:
        """Append two comments to the PR.

        Args:
            pull_req: List of pull requests to comment on
            comment1: First comment string to append
            comment2: Second comment string to append
        """
        self.comment_pull_req(pull_req, comment1, update=False)
        time.sleep(4)
        self.comment_pull_req(pull_req, comment2, update=False)

    def set_label_to_pull_request(self, pull_req: List[Dict[str, Any]], label: str) -> None:
        """Set a label to a PR.

        Args:
            pull_req: List of pull requests to label
            label: Label to set
        """
        for pr in pull_req:
            label_url = pr["issue_url"] + "/labels"

            response = requests.post(
                label_url,
                json=[label],
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                print(
                    f"Failed to set label {label} to pull request {pr['number']} \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")

            print(f"PR {pr['number']} Label set")

    def close_pull_requests(self, pull_req_list: List[Dict[str, Any]]) -> None:
        """Close the specified pull requests.

        Args:
            pull_req_list: List of pull requests to be closed
        """
        for pull_req in pull_req_list:
            url = pull_req["issue_url"]
            print(url)
            response = requests.patch(
                url,
                headers=self.headers,
                json={"state": "closed"},
                timeout=DEFAULT_TIMEOUT,
            )
            if response.status_code != 200:
                print(f"Failed to close PR: {pull_req['title']}")
            else:
                print(f"Closed PR: {pull_req['title']}")

    def merge_pull_req(self, pull_req: List[Dict[str, Any]]) -> None:
        """Merge pull requests.

        Args:
            pull_req: List of pull requests to merge

        Raises:
            SystemExit: If merge operation fails
        """
        for pr in pull_req:
            skip_pr = False

            mergeable_state = self.get_mergeable_state(pr["url"])
            print(f"\n*** PR {pr['number']} ***\n")

            # Setting a timer for the mergeable state
            timeout = time.time() + MERGEABLE_STATE_TIMEOUT
            with self.console.status("[bold green]Waiting for mergeable state to return..."):
                while mergeable_state == "unknown":
                    mergeable_state = self.get_mergeable_state(pr["url"])
                    if time.time() > timeout:
                        skip_pr = True
                        print("Timeout expired, moving on...")
                        break
                    time.sleep(1)

            if skip_pr:
                print(
                    f"PR {pr['number']}: Timeout expired waiting for state to be green, skipping")
                continue

            if mergeable_state == "behind":
                print(f"PR {pr['number']} is behind, updating branch")
                self.update_branch([pr])

            if not self.is_approved(pr["url"]):
                print(f"PR {pr['number']} Needs approving...")
                self.approve(pr["url"])
            else:
                print(f"PR {pr['number']} Approved already")

            timeout = time.time() + MERGEABLE_STATE_TIMEOUT
            with self.console.status("[bold green]Waiting for checks to pass..."):
                while mergeable_state != "clean":
                    mergeable_state = self.get_mergeable_state(pr["url"])
                    if time.time() > timeout:
                        skip_pr = True
                        print("Timeout expired, moving on...")
                        break
                    time.sleep(1)

            if skip_pr:
                print(
                    f"PR {pr['number']}: Timeout expired waiting for state to be green, skipping")
                continue

            print(f"PR {pr['number']} merging now")
            response = requests.put(
                pr["url"] + "/merge",
                headers=self.headers,
                json={"merge_method": "squash"},
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                print(
                    f"Failed to merge pull request {pr['number']} \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
                raise SystemExit(1)

            print(f"PR {pr['number']} merged!")

    def process_dismissed_prs(self, dismissed_prs: List[Dict[str, Any]]) -> None:
        """Process dismissed PRs by re-approving them and checking if they can be merged.

        Args:
            dismissed_prs: List of dismissed pull requests to process
        """
        for pr in dismissed_prs:
            print(f"\n*** Processing dismissed PR {pr['number']} ***\n")

            # Re-approve the PR
            print(f"PR {pr['number']} was dismissed, re-approving...")
            self.approve(pr["url"])

            # Check if it has no changes and can be merged
            last_comment = self.get_last_comment(pr["issue_url"])
            if last_comment:
                # If last_comment is a list, get the last one
                if isinstance(last_comment, list):
                    last_comment = last_comment[-1] if last_comment else None

            if last_comment and "body" in last_comment:
                no_changes_pattern = re.compile(
                    r"No changes. Your infrastructure matches the configuration|Apply complete!")
                if no_changes_pattern.search(last_comment["body"]):
                    print(
                        f"PR {pr['number']} has no changes after re-approval, merging...")
                    self.merge_pull_req([pr])
                else:
                    print(f"PR {pr['number']} still has changes after re-approval, will be processed in next run.")
            else:
                print(f"PR {pr['number']} has no comments after re-approval, will be processed in next run.")

    def approve_all_prs(self, all_pulls: List[Dict[str, Any]]) -> None:
        """Approve all not approved PRs matching the filters from the config.

        Args:
            all_pulls: List of all pull requests to check
        """
        approved = False
        for pr in all_pulls:
            if not self.is_approved(pr["url"]):
                self.approve(pr["url"])
                approved = True

        if approved:
            print("All completed")
        else:
            print("Nothing to be approved")
