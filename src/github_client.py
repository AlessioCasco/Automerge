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

        # Check that we have at least one repository
        if not repos:
            print("No repositories configured, skipping pull request processing")
            return dependency_prs

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

    def get_specific_pull_requests(self, test_prs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get specific pull requests for testing purposes.

        Args:
            test_prs: List of test PR configurations with repo and pr_number

        Returns:
            List of pull requests that match the test configuration

        Raises:
            SystemExit: If API call fails
        """
        specific_prs = []

        for test_pr in test_prs:
            repo = test_pr["repo"]
            pr_number = test_pr["pr_number"]

            pr_url = f"{self.base_repos_url}{repo}/pulls/{pr_number}"
            print(f"Fetching specific PR #{pr_number} from {repo}")

            response = requests.get(
                pr_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)

            if response.status_code == 200:
                pr_data = json.loads(response.text)
                specific_prs.append(pr_data)
                print(f"Successfully fetched PR #{pr_number} from {repo}")
            elif response.status_code == 404:
                print(f"PR #{pr_number} not found in {repo}, skipping...")
            else:
                print(
                    f"Failed to get PR #{pr_number} from {repo}. \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
                raise SystemExit(1)

        print(f"Fetched {len(specific_prs)} specific pull requests\n")
        return specific_prs

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

    def get_comments(self, pull_req_url: str) -> List[Dict[str, Any]]:
        """Get all comments from a given pull request.

        Args:
            pull_req_url: URL of the pull request

        Returns:
            List of all comments from the pull request
        """
        comments_url = pull_req_url + "/comments?per_page=100"
        all_comments = []

        while comments_url:
            response = requests.get(
                comments_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
            if response.status_code != 200:
                break

            comments = json.loads(response.text)
            all_comments.extend(comments)

            # Check for pagination
            comments_url = None
            if "Link" in response.headers:
                links = response.headers["Link"].split(", ")
                for link in links:
                    if 'rel="next"' in link:
                        comments_url = link[link.index("<") + 1: link.index(">")]
                        break

        return all_comments

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

    def get_last_terraform_plan(self, pull_req_url: str, terraform_user: str = "tl-terraform") -> Optional[str]:
        """Extract Terraform plan from GitHub comments by the terraform user.

        Args:
            pull_req_url: URL of the pull request
            terraform_user: GitHub username of the terraform user (default: tl-terraform)

        Returns:
            Complete terraform plan text or None if not found
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"🔍 Extracting Terraform plan from comments for {pull_req_url}")

        try:
            # Get comments from the PR
            comments = self.get_comments(pull_req_url)

            if not comments:
                logger.debug("📋 No comments found for PR")
                return None

            # Look for comments from the terraform user that contain Terraform plans
            terraform_plans = []

            for comment in comments:
                user_login = comment.get("user", {}).get("login", "")
                comment_body = comment.get("body", "")

                if user_login == terraform_user and self._is_terraform_plan_comment(comment_body):
                    logger.debug(f"📋 Found Terraform plan comment from {terraform_user}")
                    plan_content = self._extract_plan_from_comment(comment_body)
                    if plan_content:
                        terraform_plans.append(plan_content)

            if terraform_plans:
                # Combine all plans if multiple found
                combined_plan = "\n\n".join(terraform_plans)
                logger.debug(f"📋 Found Terraform plan from {terraform_user}:")
                logger.debug(f"   Plan length: {len(combined_plan)} characters")

                return combined_plan
            else:
                logger.debug(f"📋 No Terraform plan comments found from {terraform_user}")
                return None

        except Exception as e:
            logger.error(f"Error extracting Terraform plan: {e}")
            return None

    def _is_terraform_plan_comment(self, comment_body: str) -> bool:
        """Check if a comment contains a Terraform plan.

        Args:
            comment_body: The comment body text

        Returns:
            True if the comment contains a Terraform plan
        """
        terraform_indicators = [
            "Terraform will perform",
            "Plan:",
            "No changes",
            "to add, ",
            "to change, ",
            "to destroy",
            "Changes to Outputs"
        ]

        comment_lower = comment_body.lower()
        return any(indicator.lower() in comment_lower for indicator in terraform_indicators)

    def _extract_plan_from_comment(self, comment_body: str) -> str:
        """Extract Terraform plan content from a comment.

        Args:
            comment_body: The comment body text

        Returns:
            Extracted Terraform plan content
        """
        import re

        # Pattern 1: Look for code blocks (terraform, hcl, or plain text)
        code_block_patterns = [
            r"```terraform\s*\n(.*?)\n```",
            r"```hcl\s*\n(.*?)\n```",
            r"```\s*\n(.*?)\n```",
            r"```(?:terraform|hcl)?\s*\n(.*?)\n```"
        ]

        for pattern in code_block_patterns:
            code_matches = re.findall(pattern, comment_body, re.DOTALL)
            if code_matches:
                return code_matches[0].strip()

        # Pattern 2: Look for plan content starting with "Plan:" or "Terraform will perform"
        # This pattern captures everything from the start until the end of the comment
        plan_patterns = [
            r"(?:Plan:|Terraform will perform).*",
            r"Terraform will perform.*",
            r"Plan:.*"
        ]

        for pattern in plan_patterns:
            plan_matches = re.findall(pattern, comment_body, re.DOTALL)
            if plan_matches:
                return plan_matches[0].strip()

        # Pattern 3: Look for any content that contains terraform plan indicators
        # Extract everything between the first terraform indicator and the end
        terraform_start_patterns = [
            r"(.*?Terraform will perform.*)",
            r"(.*?Plan:.*)",
            r"(.*?No changes.*)",
            r"(.*?to add,.*to change,.*to destroy.*)"
        ]

        for pattern in terraform_start_patterns:
            matches = re.findall(pattern, comment_body, re.DOTALL)
            if matches:
                return matches[0].strip()

        # Fallback: return the entire comment if it looks like a plan
        if self._is_terraform_plan_comment(comment_body):
            return comment_body.strip()

        return ""

    def get_mergeable_state(self, url: str) -> str:
        """Get the mergeable state of the PR.

        Args:
            url: URL to use for the API call

        Returns:
            Mergeable state of the pull request
        """
        try:
            response = requests.get(
                url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
            if response.status_code != 200:
                print(
                    f"Failed to get info for pull request \n Status code: {response.status_code} \n Reason: {json.loads(response.text)}")
                return "unknown"

            data = json.loads(response.text)
            return data.get("mergeable_state", "unknown")
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            print(f"Error getting mergeable state: {e}")
            return "unknown"

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
            return None

        reviews = json.loads(response.text)
        user_reviews = []

        # Collect all reviews from our user
        for review in reviews:
            if review["user"]["login"] == self.github_user:
                user_reviews.append(review)

        if not user_reviews:
            return None

        # Sort reviews by ID to get the most recent one (GitHub API returns them in chronological order)
        # but we want to be sure we get the latest state
        latest_review = max(user_reviews, key=lambda x: x["id"])

        if latest_review["state"] == "APPROVED":
            return True
        elif latest_review["state"] == "DISMISSED":
            return "Dismissed"
        else:
            return False

    def approve(self, url: str) -> None:
        """Approve a pull request.

        Args:
            url: URL to use for the API call

        Raises:
            SystemExit: If API call fails
        """
        try:
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
        except requests.exceptions.RequestException as e:
            print(f"Network error approving pull request: {e}")
            raise SystemExit(1) from e

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

            approval_status = self.is_approved(pr["url"])
            if not approval_status or approval_status == "Dismissed":
                if approval_status == "Dismissed":
                    print(
                        f"PR {pr['number']} approval was dismissed/stale, re-approving...")
                else:
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
