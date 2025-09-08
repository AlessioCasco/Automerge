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
        """Get terraform plans from GitHub status checks instead of comments.

        Args:
            pull_req_url: URL of the pull request
            terraform_user: GitHub username of the terraform user (default: tl-terraform)

        Returns:
            Combined terraform plan text from all atlantis/plan status checks or None if no plans found
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"🔍 Starting terraform plan extraction from status checks for {pull_req_url}")

        # Extract repo and PR number from the URL
        # URL format: https://api.github.com/repos/owner/repo/pulls/123 or /issues/123
        url_parts = pull_req_url.split("/")
        if len(url_parts) < 7 or url_parts[-2] not in ["pulls", "issues"]:
            logger.error(f"   ❌ Invalid PR URL format: {pull_req_url}")
            return None

        repo_name = url_parts[-3]
        pr_number = url_parts[-1]

        # Convert issues URL to pulls URL for API calls
        if url_parts[-2] == "issues":
            logger.debug("   🔄 Converting issues URL to pulls URL")
            pull_req_url = pull_req_url.replace("/issues/", "/pulls/")

        logger.debug(f"   📍 Extracted repo: {repo_name}, PR: {pr_number}")

        # Get PR details first to extract statuses_url
        pr_url = f"{self.base_repos_url}{repo_name}/pulls/{pr_number}"
        logger.debug(f"   🔗 Fetching PR details: {pr_url}")

        response = requests.get(pr_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            logger.error(f"   ❌ Failed to fetch PR details: {response.status_code}")
            return None

        pr_data = json.loads(response.text)

        # Get statuses_url from PR data
        statuses_url = pr_data.get("statuses_url")
        if not statuses_url:
            logger.error("   ❌ No statuses_url found in PR data")
            return None

        logger.debug(f"   🔗 Fetching status checks from: {statuses_url}")

        # Fetch status checks from statuses_url
        response = requests.get(statuses_url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            logger.error(f"   ❌ Failed to fetch status checks: {response.status_code}")
            return None

        status_checks = json.loads(response.text)
        logger.debug(f"   📊 Found {len(status_checks)} status checks")

        # Filter status checks for atlantis/plan context with environment/project info
        atlantis_plan_checks = []

        for check in status_checks:
            state_success = check.get("state", "") == "success"
            context = check.get("context", "")
            if state_success and context.startswith("atlantis/plan: "):
                # Extract environment/project info from context
                element = context.replace("atlantis/plan: ", "").strip()
                check["environment_info"] = self._extract_environment_info(element)
                atlantis_plan_checks.append(check)
                logger.debug(f"   ✅ Found atlantis/plan check: {context} -> {check['environment_info']}")

        logger.debug(f"   🏗️  Found {len(atlantis_plan_checks)} atlantis/plan status checks")

        if not atlantis_plan_checks:
            logger.debug("   ❌ No atlantis/plan status checks found")
            return None

        # Collect plans from all atlantis/plan status checks
        all_plans = []

        for i, check in enumerate(atlantis_plan_checks):
            context = check.get("context", "unknown")
            target_url = check.get("target_url")
            state = check.get("state", "unknown")
            environment_info = check.get("environment_info", {})

            logger.debug(f"   🔍 Processing check {i+1}/{len(atlantis_plan_checks)}: {context}")
            logger.debug(f"      State: {state}, Environment: {environment_info.get('environment', 'unknown')}")
            logger.debug(f"      Project: {environment_info.get('project', 'unknown')}, Target URL: {target_url}")

            if not target_url:
                logger.debug(f"      ❌ No target_url found for {context}")
                continue

            # Fetch plan from Atlantis URL
            plan_content = self._fetch_plan_from_atlantis_url(target_url, context)
            if plan_content:
                all_plans.append({
                    "context": context,
                    "content": plan_content,
                    "url": target_url,
                    "environment_info": environment_info
                })
                logger.debug(f"      ✅ Successfully fetched plan for {context} ({len(plan_content)} chars)")
            else:
                logger.debug(f"      ❌ Failed to fetch plan for {context}")

        if not all_plans:
            logger.debug("   ❌ No plans successfully fetched from any atlantis/plan status checks")
            return None

        # Combine all plans
        combined_plan = self._combine_multiple_plans(all_plans)
        logger.info(f"   📋 Combined {len(all_plans)} plans, total length: {len(combined_plan)} characters")

        return combined_plan

    def _extract_environment_info(self, element: str) -> Dict[str, str]:
        """Extract environment and project information from atlantis/plan context element.

        Args:
            element: The element part after "atlantis/plan:" (e.g., "dev", "prod", "project-dev", "project-prod")

        Returns:
            Dictionary with environment and project information
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"      🔍 Extracting environment info from: '{element}'")

        # Common environment patterns
        dev_patterns = ["dev", "development", "test"]
        prod_patterns = ["prod", "production", "sandbox"]

        element_lower = element.lower()

        # Determine environment
        environment = "unknown"
        if any(pattern in element_lower for pattern in dev_patterns):
            environment = "development"
        elif any(pattern in element_lower for pattern in prod_patterns):
            environment = "production"
        else:
            # Default to development if no clear production indicators
            environment = "development"

        # Extract project name (everything before environment indicators)
        project = element
        for pattern in dev_patterns + prod_patterns:
            if pattern in element_lower:
                project = element_lower.split(pattern)[0].strip("-")
                break

        if not project:
            project = element

        result = {
            "environment": environment,
            "project": project,
            "original_element": element
        }

        logger.debug(f"      📋 Extracted: {result}")
        return result

    def _fetch_plan_from_atlantis_url(self, target_url: str, context: str) -> Optional[str]:
        """Fetch Terraform plan from Atlantis URL.

        Args:
            target_url: Atlantis job URL (e.g., https://atlantis.truelayer.cloud/jobs/58c5a09b-f21c-4801-8afb-2d0678623e63)
            context: Status check context for logging

        Returns:
            Terraform plan content or None if fetch fails
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"      🌐 Fetching plan from Atlantis URL: {target_url}")

        try:
            # Fetch the Atlantis job page
            response = requests.get(target_url, timeout=DEFAULT_TIMEOUT)

            if response.status_code != 200:
                logger.debug(f"      ❌ Failed to fetch Atlantis URL: {response.status_code}")
                return None

            # Parse the HTML content to extract the plan
            plan_content = self._extract_plan_from_atlantis_html(response.text, context)

            if plan_content:
                logger.debug(f"      ✅ Successfully extracted plan from Atlantis ({len(plan_content)} chars)")
                return plan_content
            else:
                logger.debug("      ❌ No plan content found in Atlantis response")
                return None

        except Exception as e:
            logger.debug(f"      ❌ Exception fetching from Atlantis URL: {str(e)}")
            return None

    def _extract_plan_from_atlantis_html(self, html_content: str, context: str) -> Optional[str]:
        """Extract Terraform plan from Atlantis HTML response.

        Args:
            html_content: HTML content from Atlantis job page
            context: Status check context for logging

        Returns:
            Extracted Terraform plan content or None if not found
        """
        import re
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"      🔧 Extracting plan from Atlantis HTML for {context}")

        # Look for Terraform plan in various formats within the HTML
        # Atlantis typically shows plans in <pre> tags or within specific divs

        # Pattern 1: Look for <pre> tags containing Terraform plan
        pre_pattern = r"<pre[^>]*>(.*?)</pre>"
        pre_matches = re.findall(pre_pattern, html_content, re.DOTALL | re.IGNORECASE)

        for match in pre_matches:
            # Clean HTML entities and check if it looks like a Terraform plan
            cleaned_content = self._clean_html_content(match)
            if self._is_terraform_plan(cleaned_content):
                logger.debug("      ✅ Found Terraform plan in <pre> tag")
                return cleaned_content

        # Pattern 2: Look for Terraform plan in divs with specific classes
        div_pattern = r'<div[^>]*class="[^"]*plan[^"]*"[^>]*>(.*?)</div>'
        div_matches = re.findall(div_pattern, html_content, re.DOTALL | re.IGNORECASE)

        for match in div_matches:
            cleaned_content = self._clean_html_content(match)
            if self._is_terraform_plan(cleaned_content):
                logger.debug("      ✅ Found Terraform plan in <div> tag")
                return cleaned_content

        # Pattern 3: Look for Terraform plan summary pattern
        plan_summary_pattern = r"Plan: \d+ to add, \d+ to change, \d+ to destroy\."
        if re.search(plan_summary_pattern, html_content):
            logger.debug("      ✅ Found Terraform plan summary pattern")
            # Extract a larger context around the plan summary
            context_pattern = r"(.{0,2000}Plan: \d+ to add, \d+ to change, \d+ to destroy\.){0,2000}"
            match = re.search(context_pattern, html_content, re.DOTALL)
            if match:
                cleaned_content = self._clean_html_content(match.group(1))
                return cleaned_content

        logger.debug("      ❌ No Terraform plan found in Atlantis HTML")
        return None

    def _clean_html_content(self, content: str) -> str:
        """Clean HTML content and extract text.

        Args:
            content: Raw HTML content

        Returns:
            Cleaned text content
        """
        import re

        # Remove HTML tags
        cleaned = re.sub(r"<[^>]+>", "", content)

        # Decode HTML entities
        html_entities = {
            "&lt;": "<",
            "&gt;": ">",
            "&amp;": "&",
            "&quot;": '"',
            "&#39;": "'",
            "&nbsp;": " "
        }

        for entity, char in html_entities.items():
            cleaned = cleaned.replace(entity, char)

        # Clean up whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _is_terraform_plan(self, content: str) -> bool:
        """Check if content looks like a Terraform plan.

        Args:
            content: Text content to check

        Returns:
            True if content appears to be a Terraform plan
        """
        import re

        # Check for Terraform plan indicators
        terraform_indicators = [
            r"Terraform will perform the following actions:",
            r"Plan: \d+ to add, \d+ to change, \d+ to destroy\.",
            r'resource "',
            r"# \w+ will be",
            r'~ resource "',
            r'\+ resource "',
            r'- resource "'
        ]

        content_lower = content.lower()
        matches = sum(1 for pattern in terraform_indicators if re.search(pattern, content_lower))

        # Consider it a Terraform plan if we find at least 2 indicators
        return matches >= 2

    def _combine_multiple_plans(self, plans: List[Dict[str, Any]]) -> str:
        """Combine multiple Terraform plans into a single text with environment information.

        Args:
            plans: List of plan dictionaries with context, content, url, and environment_info

        Returns:
            Combined plan text with environment and project information
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"      🔗 Combining {len(plans)} plans")

        combined_parts = []

        for i, plan in enumerate(plans):
            context = plan.get("context", f"plan_{i}")
            content = plan.get("content", "")
            environment_info = plan.get("environment_info", {})

            environment = environment_info.get("environment", "unknown")
            project = environment_info.get("project", "unknown")
            original_element = environment_info.get("original_element", context)

            # Add detailed header for each plan with environment info
            combined_parts.append(f"\n=== Terraform Plan: {original_element} ===")
            combined_parts.append(f"Environment: {environment}")
            combined_parts.append(f"Project: {project}")
            combined_parts.append(f"Context: {context}")
            combined_parts.append("=" * 50)
            combined_parts.append(content)
            combined_parts.append("=" * 50)
            combined_parts.append(f"=== End Plan: {original_element} ===\n")

        combined_text = "\n".join(combined_parts)
        logger.debug(f"      📋 Combined plan total length: {len(combined_text)} characters")

        return combined_text

    def _extract_plan_from_details(self, comment_body: str) -> str:
        """Extract Terraform plan content from <details> block.

        Args:
            comment_body: Full comment body

        Returns:
            Extracted plan content or empty string if not found
        """
        import re
        import logging
        logger = logging.getLogger(__name__)

        logger.debug("   🔧 Extracting plan from <details> block")
        logger.debug(f"      Comment body length: {len(comment_body)} characters")

        # Look for <details> block with plan content
        details_pattern = r"<details><summary>Show Output</summary>\s*```(?:diff|hcl|terraform)?\s*(.*?)```\s*</details>"
        match = re.search(details_pattern, comment_body, re.DOTALL)

        if match:
            extracted_content = match.group(1).strip()
            logger.debug(f"      ✅ Found <details> block, extracted {len(extracted_content)} characters")
            logger.debug(f"      Preview: {extracted_content[:200]}{'...' if len(extracted_content) > 200 else ''}")
            return extracted_content

        logger.debug("      ❌ No <details> block found with pattern")

        # If no details block, look for plan summary at the end
        plan_summary_pattern = r"Plan: \d+ to add, \d+ to change, \d+ to destroy\."
        if re.search(plan_summary_pattern, comment_body):
            logger.debug("      ✅ Found plan summary pattern, returning full comment body")
            return comment_body

        logger.debug("      ❌ No plan summary pattern found either")
        return ""

    def _collect_plan_parts(self, all_comments: List[Dict[str, Any]], start_index: int) -> List[Dict[str, Any]]:
        """Collect all parts of a multi-comment Terraform plan.

        Args:
            all_comments: All terraform comments sorted by creation date (newest first)
            start_index: Index of the main plan comment

        Returns:
            List of plan parts in chronological order (oldest first)
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"   🔗 Collecting plan parts starting from index {start_index}")

        plan_parts = []

        # Start with the main plan comment
        main_comment = all_comments[start_index]
        plan_parts.append(main_comment)
        logger.debug(f"      📋 Added main plan comment from {main_comment.get('created_at', 'unknown')}")

        # Check if the main comment indicates continuation
        comment_body = main_comment.get("body", "")
        has_continuation_warning = "Warning: Output length greater than max comment size. Continued in next comment." in comment_body

        if has_continuation_warning:
            logger.debug("      ⚠️  Found continuation warning in main comment")

            # Look for continuation comments that come before this one in the sorted array
            # Since comments are sorted newest first, continuation comments come before the main comment
            for i in range(start_index - 1, -1, -1):
                comment = all_comments[i]
                comment_body = comment.get("body", "")
                created_at = comment.get("created_at", "unknown")

                logger.debug(f"      🔍 Checking comment {i} from {created_at}")
                logger.debug(f"         Preview: {comment_body[:100]}{'...' if len(comment_body) > 100 else ''}")

                # Check if this is a continuation comment
                if comment_body.startswith("Continued plan output from previous comment."):
                    logger.debug("      ✅ Found continuation comment!")
                    plan_parts.append(comment)
                else:
                    # If we find a non-continuation comment, stop looking
                    # This means we've reached the end of this plan
                    logger.debug("      🛑 Found non-continuation comment, stopping search")
                    break
        else:
            logger.debug("      📋 No continuation warning found, single comment plan")

        # Sort plan parts by creation date (oldest first for proper order)
        plan_parts.sort(key=lambda x: x.get("created_at", ""))
        logger.debug(f"   📅 Collected {len(plan_parts)} plan parts in chronological order")

        return plan_parts

    def _combine_plan_parts(self, plan_parts: List[Dict[str, Any]]) -> str:
        """Combine multiple plan parts into a single plan text.

        Args:
            plan_parts: List of plan parts in chronological order

        Returns:
            Combined plan text
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.debug(f"   🔧 Combining {len(plan_parts)} plan parts")

        combined_parts = []

        for i, part in enumerate(plan_parts):
            comment_body = part.get("body", "")
            created_at = part.get("created_at", "unknown")

            logger.debug(f"      📋 Processing part {i+1}/{len(plan_parts)} from {created_at}")

            if i == 0:
                # First part: extract from <details> block or use full body
                plan_content = self._extract_plan_from_details(comment_body)
                if plan_content:
                    logger.debug(f"         ✅ Extracted from <details> block ({len(plan_content)} chars)")
                    combined_parts.append(plan_content)
                else:
                    logger.debug(f"         📋 Using full comment body ({len(comment_body)} chars)")
                    combined_parts.append(comment_body)
            else:
                # Continuation parts: remove the continuation header
                if comment_body.startswith("Continued plan output from previous comment."):
                    # Remove the continuation header and any leading whitespace
                    continuation_content = comment_body[len("Continued plan output from previous comment."):].strip()
                    logger.debug(f"         ✅ Removed continuation header, content length: {len(continuation_content)} chars")
                    combined_parts.append(continuation_content)
                else:
                    # Fallback: use the full comment body
                    logger.debug(f"         📋 Using full continuation comment body ({len(comment_body)} chars)")
                    combined_parts.append(comment_body)

        # Join all parts with newlines
        combined_plan = "\n".join(combined_parts)
        logger.debug(f"   📋 Final combined plan length: {len(combined_plan)} characters")

        return combined_plan

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
