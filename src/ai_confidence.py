#!/usr/bin/env python3

import os
import re
import json
import logging
import requests
import urllib3
from typing import Dict, Any, Optional, Tuple

try:
    from .metrics import AutomergeMetrics
    from .embeddings_service import EmbeddingsService
except ImportError:
    from metrics import AutomergeMetrics
    from embeddings_service import EmbeddingsService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get log level from environment variable
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

# Suppress SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default timeout for API calls
DEFAULT_TIMEOUT = 30


class AIConfidenceCalculator:
    """Handles AI-powered confidence score calculation for PRs."""

    def __init__(
        self,
        github_token: str,
        github_client=None,
        ai_config: Dict[str, Any] = None,
        metrics: AutomergeMetrics = None,
        embeddings_service: EmbeddingsService = None,
    ):
        """Initialize AI confidence calculator.

        Args:
            github_token: GitHub access token with Copilot permissions
            github_client: GitHub client instance for API calls
            ai_config: AI configuration dictionary
            metrics: Metrics collector for token usage tracking
            embeddings_service: Embeddings service for PR similarity analysis
        """
        self.github_token = github_token
        self.github_client = github_client
        self.ai_config = ai_config or {}
        self.metrics = metrics
        self.embeddings_service = embeddings_service
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _extract_pr_context(self, pr_data: Dict[str, Any]) -> str:
        """Extract relevant context from PR data.

        Args:
            pr_data: Pull request data

        Returns:
            Formatted context string
        """
        title = pr_data.get("title", "")
        body = pr_data.get("body", "")
        labels = [label["name"] for label in pr_data.get("labels", [])]

        context = f"""PR Title: {title}
PR Description: {body}
Repository: {pr_data.get("head", {}).get("repo", {}).get("name", "N/A")}
Base Branch: {pr_data.get("base", {}).get("ref", "N/A")}
Head Branch: {pr_data.get("head", {}).get("ref", "N/A")}
Labels: {", ".join(labels) if labels else "None"}"""

        return context

    def _extract_terraform_plan(
        self, pr_data: Dict[str, Any], terraform_user: str = "tl-terraform"
    ) -> str:
        """Extract Terraform plan output using GitHubClient.

        Args:
            pr_data: Pull request data
            terraform_user: GitHub username of the terraform user (default: tl-terraform)

        Returns:
            Complete terraform plan text or empty string if not found
        """
        try:
            # Check if github_client is available
            if not self.github_client:
                logger.error(
                    "GitHub client not available for terraform plan extraction"
                )
                return ""

            # Get the issue URL from PR data
            issue_url = pr_data.get("issue_url")
            if not issue_url:
                return ""

            # Use GitHubClient to extract the plan
            plan_content = self.github_client.get_last_terraform_plan(
                issue_url, terraform_user
            )

            if plan_content:
                logger.debug(
                    f"📋 Successfully extracted Terraform plan ({len(plan_content)} characters)"
                )
                return plan_content
            else:
                logger.debug(f"📋 No Terraform plan found from {terraform_user}")
                return ""

        except Exception as e:
            logger.error(f"Error extracting Terraform plan: {e}")
            return ""

    def _call_ai_provider_with_metadata(
        self, prompt: str
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Call AI provider (GitHub Copilot or Claude Code) to get AI response with metadata.

        Args:
            prompt: Prompt to send to the AI

        Returns:
            Tuple of (AI response, metadata)
        """
        provider = self.ai_config.get("ai_provider", "github")

        if provider == "github":
            return self._call_github_copilot_with_metadata(prompt)
        elif provider == "claude-code":
            return self._call_claude_code_with_metadata(prompt)
        else:
            logger.error(f"Unknown AI provider: {provider}")
            return None, {
                "provider": "unknown",
                "model": "none",
                "input_tokens": 0,
                "output_tokens": 0,
            }

    def _call_github_copilot_with_metadata(
        self, prompt: str
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Call GitHub Copilot API via proxy to get AI response with metadata.

        Args:
            prompt: Prompt to send to the AI

        Returns:
            Tuple of (AI response, metadata)
        """
        try:
            # Get configuration from ai_config
            github_config = self.ai_config.get("ai_config", {}).get("github", {})
            api_base = github_config.get("api_base", "http://localhost:4141")
            model = github_config.get("model", "claude-sonnet-4")

            # Use Anthropic compatible endpoint via copilot-api proxy
            url = f"{api_base}/v1/messages"

            payload = {
                "model": model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            }

            # Use different headers for the proxy
            proxy_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Debug logging
            logger.debug("🤖 GitHub Copilot API Call Details:")
            logger.debug(f"   URL: {url}")
            logger.debug(f"   Model: {model}")

            response = requests.post(
                url, headers=proxy_headers, json=payload, timeout=DEFAULT_TIMEOUT
            )

            logger.debug(f"   Response Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()

                # Extract content from Anthropic response format
                content = result.get("content", [{}])[0].get("text", "")
                logger.debug(f"   Extracted Content: {content}")

                # Log usage statistics if available
                usage = result.get("usage", {})
                if usage:
                    logger.debug(f"   Usage: {usage}")

                metadata = {
                    "provider": "GitHub Copilot",
                    "model": model,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "environment": None,  # Will be set by calculate_confidence_score
                    "environment_reason": None,  # Will be set by calculate_confidence_score
                }

                return content, metadata
            else:
                logger.error(
                    f"GitHub Copilot API proxy error: {response.status_code} - {response.text}"
                )
                logger.debug(f"   Error Response: {response.text}")
                return None, {
                    "provider": "GitHub Copilot",
                    "model": model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling GitHub Copilot API proxy: {e}")
            return None, {
                "provider": "GitHub Copilot",
                "model": "unknown",
                "input_tokens": 0,
                "output_tokens": 0,
            }
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing GitHub Copilot API proxy response: {e}")
            logger.debug(
                f"   Raw Response: {response.text if 'response' in locals() else 'N/A'}"
            )
            return None, {
                "provider": "GitHub Copilot",
                "model": "unknown",
                "input_tokens": 0,
                "output_tokens": 0,
            }

    def _call_claude_code_with_metadata(
        self, prompt: str
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Call Claude Code API to get AI response with metadata.

        Args:
            prompt: Prompt to send to the AI

        Returns:
            Tuple of (AI response, metadata)
        """
        try:
            # Get configuration from ai_config
            claude_config = self.ai_config.get("ai_config", {}).get("claude-code", {})
            api_base = claude_config.get("api_base", "https://api.anthropic.com")
            api_key = claude_config.get("api_key")
            model = claude_config.get("model", "claude-sonnet-4")

            if not api_key:
                logger.error("Claude Code API key not provided")
                return None, {
                    "provider": "Claude Code",
                    "model": model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }

            # Use Claude Code API endpoint
            url = f"{api_base}/v1/messages"

            payload = {
                "model": model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            }

            # Use Claude Code headers
            claude_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }

            # Check if we should disable SSL verification (for local development)
            disable_ssl_verify = (
                os.environ.get("DISABLE_SSL_VERIFY", "false").lower() == "true"
            )

            # Debug logging
            logger.debug("🤖 Claude Code API Call Details:")
            logger.debug(f"   URL: {url}")
            logger.debug(f"   Model: {model}")
            logger.debug(f"   SSL Verify: {not disable_ssl_verify}")

            response = requests.post(
                url,
                headers=claude_headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
                verify=not disable_ssl_verify,  # Disable SSL verification if environment variable is set
            )

            logger.debug(f"   Response Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()

                # Extract content from Claude response format
                content = result.get("content", [{}])[0].get("text", "")
                logger.debug(f"   Extracted Content: {content}")

                # Log usage statistics if available
                usage = result.get("usage", {})
                if usage:
                    logger.debug(f"   Usage: {usage}")

                metadata = {
                    "provider": "Claude Code",
                    "model": model,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                }

                return content, metadata
            else:
                logger.error(
                    f"Claude Code API error: {response.status_code} - {response.text}"
                )
                logger.debug(f"   Error Response: {response.text}")
                return None, {
                    "provider": "Claude Code",
                    "model": model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Claude Code API: {e}")
            return None, {
                "provider": "Claude Code",
                "model": "unknown",
                "input_tokens": 0,
                "output_tokens": 0,
            }
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing Claude Code API response: {e}")
            logger.debug(
                f"   Raw Response: {response.text if 'response' in locals() else 'N/A'}"
            )
            return None, {
                "provider": "Claude Code",
                "model": "unknown",
                "input_tokens": 0,
                "output_tokens": 0,
            }

    def _parse_ai_response(self, ai_response: str) -> Tuple[int, str]:
        """Parse AI response to extract confidence score and explanation.

        Args:
            ai_response: Raw AI response

        Returns:
            Tuple of (confidence_score, explanation)
        """
        try:
            # Look for pattern "SCORE: X% - EXPLANATION" followed by explanation
            score_pattern = r"SCORE:\s*(\d+)%\s*-\s*EXPLANATION\s*\n\s*(.+)"
            match = re.search(score_pattern, ai_response.strip(), re.DOTALL)

            if match:
                score = int(match.group(1))
                explanation = match.group(2).strip()
                return score, explanation

            # Fallback: try pattern without "EXPLANATION" keyword
            score_pattern_fallback = r"SCORE:\s*(\d+)%\s*-\s*(.+)"
            match = re.search(score_pattern_fallback, ai_response.strip(), re.DOTALL)

            if match:
                score = int(match.group(1))
                explanation = match.group(2).strip()
                return score, explanation

            # Fallback: try to extract just the number
            number_pattern = r"(\d+)%"
            match = re.search(number_pattern, ai_response)
            if match:
                score = int(match.group(1))
                # Extract everything after the score as explanation
                explanation_start = ai_response.find(f"{score}%")
                if explanation_start != -1:
                    explanation = ai_response[
                        explanation_start + len(f"{score}%") :
                    ].strip()
                    # Remove "EXPLANATION" if present
                    explanation = explanation.replace("EXPLANATION", "").strip()
                    if explanation:
                        return score, explanation

                explanation = ai_response.strip()
                return score, explanation

            # Default fallback
            logger.warning(f"Could not parse AI response: {ai_response}")
            return 50, "Unable to parse AI response"

        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing AI response: {e}")
            return 50, "Error parsing AI response"

    def _detect_environment(self, pr_data: Dict[str, Any]) -> Tuple[str, str]:
        """Detect the environment based on PR title and changed files.

        Uses dual heuristics:
        1. Check PR title for environment keywords (as whole words)
        2. Check changed file paths/names for account-specific patterns

        Args:
            pr_data: Pull request data

        Returns:
            Tuple of (environment_name, detection_reason)
            - environment_name: "development", "sandbox", "production", or "global"
            - detection_reason: explanation of why this environment was detected
        """
        title = pr_data.get("title", "").lower()

        # Get changed files from PR data
        changed_files = []
        if "files" in pr_data:
            changed_files = [f.get("filename", "").lower() for f in pr_data.get("files", [])]

        # Define environment keywords with word boundaries
        env_keywords = {
            "development": {
                "title_keywords": [r"\bdevelopment\b", r"\bdevelop\b", r"\bdev\b"],
                "file_patterns": [r"account[_.-]development", r"account[_.-]dev\b"],
            },
            "sandbox": {
                "title_keywords": [r"\bsandbox\b", r"\bsbx\b"],
                "file_patterns": [r"account[_.-]sandbox", r"account[_.-]sbx\b"],
            },
            "production": {
                "title_keywords": [r"\bproduction\b", r"\bprod\b", r"\bprd\b"],
                "file_patterns": [r"account[_.-]production", r"account[_.-]prod\b", r"account[_.-]prd\b"],
            },
        }

        detected_envs = {}

        # Check title for environment keywords
        for env_name, patterns in env_keywords.items():
            for pattern in patterns["title_keywords"]:
                if re.search(pattern, title):
                    if env_name not in detected_envs:
                        detected_envs[env_name] = []
                    # Extract pattern name without regex boundaries for display
                    pattern_display = pattern.replace(r"\b", "")
                    detected_envs[env_name].append(f"title contains '{pattern_display}'")
                    break

        # Check file paths for environment patterns
        for file_path in changed_files:
            for env_name, patterns in env_keywords.items():
                for pattern in patterns["file_patterns"]:
                    if re.search(pattern, file_path):
                        if env_name not in detected_envs:
                            detected_envs[env_name] = []
                        detected_envs[env_name].append(f"file path matches '{pattern}'")
                        break

        # Determine final environment based on detection results
        if len(detected_envs) == 0:
            # No environment detected
            return "global", "No specific environment detected in PR title or file paths"
        elif len(detected_envs) == 1:
            # Single environment detected
            env_name = list(detected_envs.keys())[0]
            reasons = detected_envs[env_name]
            return env_name, f"Detected as {env_name}: {', '.join(set(reasons))}"
        else:
            # Multiple environments detected - conflict
            env_list = ", ".join(detected_envs.keys())
            return "global", f"Conflicting environments detected ({env_list}), treating as global for safety"

    def _is_auto_merge_environment(self, pr_data: Dict[str, Any]) -> bool:
        """Determine if the PR is targeting an environment that allows auto-merge.

        Args:
            pr_data: Pull request data

        Returns:
            True if environment allows auto-merge, False otherwise
        """
        # Get configured auto-merge environments
        auto_merge_envs = self.ai_config.get("auto_merge_environments", ["development"])

        # Detect environment using new dual heuristics
        detected_env, reason = self._detect_environment(pr_data)

        logger.debug(f"Environment detection: {detected_env} - {reason}")

        # "global" environment is never auto-mergeable (treated as production)
        if detected_env == "global":
            logger.debug("Environment is 'global', auto-merge disabled for safety")
            return False

        # Check if detected environment is in the auto-merge allowed list
        if detected_env.lower() in [env.lower() for env in auto_merge_envs]:
            logger.debug(f"Environment '{detected_env}' allows auto-merge")
            return True

        # Default to False (conservative approach)
        logger.debug(
            f"Environment '{detected_env}' not in auto-merge list: {auto_merge_envs}"
        )
        return False

    def _apply_similarity_boost(
        self, base_score: int, pr_data: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any]]:
        """Apply similarity boost based on historical safe PRs.

        Args:
            base_score: Base confidence score from AI/fallback
            pr_data: Pull request data

        Returns:
            Tuple of (boosted_score, similarity_metadata)
        """
        if not self.embeddings_service or not self.embeddings_service.enabled:
            return base_score, {}

        try:
            repo_name = pr_data.get("head", {}).get("repo", {}).get("name", "")
            pr_number = pr_data.get("number")

            if not repo_name or not pr_number:
                logger.warning("Missing repo_name or pr_number for embeddings")
                return base_score, {}

            logger.info(
                f"🔍 Calculating similarity boost for PR #{pr_number} in {repo_name}"
            )

            # Fetch historical safe PRs from GitHub
            if not self.github_client:
                logger.warning(
                    "GitHub client not available for fetching historical PRs"
                )
                return base_score, {}

            # Get PRs with 'automerge-safe-example' label
            # Use max_cached_prs from embeddings service configuration
            max_prs = self.embeddings_service.max_cached_prs
            safe_prs = self.github_client.get_prs_with_label(
                repo_name, "automerge-safe-example", limit=max_prs
            )

            if not safe_prs:
                logger.info(
                    "No historical safe PRs found - skipping embeddings calculation for current PR"
                )
                return base_score, {
                    "similarity_enabled": True,
                    "historical_prs_found": 0,
                    "embeddings_skipped": True,
                    "skip_reason": "no_historical_prs",
                }

            safe_pr_numbers = [pr.get("number") for pr in safe_prs if pr.get("number")]

            if not safe_pr_numbers:
                logger.info(
                    "No valid PR numbers found in safe PRs - skipping embeddings calculation"
                )
                return base_score, {
                    "similarity_enabled": True,
                    "historical_prs_found": len(safe_prs),
                    "valid_pr_numbers": 0,
                    "embeddings_skipped": True,
                    "skip_reason": "no_valid_pr_numbers",
                }

            logger.info(
                f"Found {len(safe_pr_numbers)} historical safe PRs: {safe_pr_numbers}"
            )

            # Get cached embeddings from S3 and calculate missing ones
            # This also performs S3 cleanup to align with GitHub's list
            historical_embeddings = self.embeddings_service.get_historical_safe_prs(
                repo_name, safe_pr_numbers, self.github_client
            )

            if not historical_embeddings:
                logger.info(
                    "No historical embeddings available - skipping embeddings calculation for current PR"
                )
                return base_score, {
                    "similarity_enabled": True,
                    "historical_prs_found": len(safe_pr_numbers),
                    "historical_embeddings_loaded": 0,
                    "embeddings_skipped": True,
                    "skip_reason": "no_historical_embeddings",
                }

            logger.info(
                f"Loaded {len(historical_embeddings)} cached embeddings from S3"
            )

            # Prepare current PR data for embeddings
            current_pr_data = {
                "pr_number": pr_number,
                "repo_name": repo_name,
                "files": pr_data.get("files", []),
                "diff": pr_data.get("diff", ""),
                "terraform_plan": self._extract_terraform_plan(pr_data),
            }

            # Calculate embeddings for current PR
            current_embeddings = self.embeddings_service.calculate_pr_embeddings(
                current_pr_data
            )

            if not current_embeddings:
                logger.warning("Failed to calculate embeddings for current PR")
                return base_score, {
                    "similarity_enabled": True,
                    "embeddings_calculated": False,
                }

            # Calculate similarity boost
            if historical_embeddings:
                max_similarity, most_similar_pr = (
                    self.embeddings_service.calculate_similarity_boost(
                        current_embeddings, historical_embeddings
                    )
                )

                # Apply boost to score
                boosted_score = self.embeddings_service.apply_similarity_boost(
                    float(base_score), max_similarity
                )

                similarity_metadata = {
                    "similarity_enabled": True,
                    "max_similarity": round(max_similarity, 4),
                    "most_similar_pr": most_similar_pr,
                    "historical_prs_count": len(historical_embeddings),
                    "base_score": base_score,
                    "boosted_score": int(boosted_score),
                }

                logger.info(
                    f"✨ Applied similarity boost: {base_score} → {int(boosted_score)} (similarity: {max_similarity:.4f})"
                )

                return int(boosted_score), similarity_metadata
            else:
                logger.info("No cached embeddings available, skipping similarity boost")
                return base_score, {
                    "similarity_enabled": True,
                    "historical_prs_count": 0,
                }

        except Exception as e:
            logger.error(f"Error applying similarity boost: {e}", exc_info=True)
            return base_score, {"similarity_enabled": True, "error": str(e)}

    def calculate_confidence_score(
        self, pr_data: Dict[str, Any]
    ) -> Tuple[int, str, bool, Dict[str, Any]]:
        """Calculate confidence score for automatic merging.

        Args:
            pr_data: Pull request data

        Returns:
            Tuple of (confidence_score, explanation, is_development_env, metadata)
        """
        try:
            # Extract context
            pr_context = self._extract_pr_context(pr_data)
            plan_output = self._extract_terraform_plan(pr_data)

            # Detect environment using new dual heuristics
            detected_env, env_reason = self._detect_environment(pr_data)
            is_auto_merge_env = self._is_auto_merge_environment(pr_data)

            logger.debug("🔍 PR Analysis Context:")
            logger.debug(f"   PR Title: {pr_data.get('title', 'N/A')}")
            logger.debug(
                f"   Repository: {pr_data.get('head', {}).get('repo', {}).get('name', 'N/A')}"
            )
            logger.debug(f"   Base Branch: {pr_data.get('base', {}).get('ref', 'N/A')}")
            logger.debug(f"   Head Branch: {pr_data.get('head', {}).get('ref', 'N/A')}")
            logger.debug(f"   Detected Environment: {detected_env}")
            logger.debug(f"   Environment Reason: {env_reason}")
            logger.debug(
                f"   Auto-merge: {'Allowed' if is_auto_merge_env else 'Disabled'}"
            )
            logger.debug(
                f"   Plan Output: {plan_output[:200]}{'...' if len(plan_output) > 200 else ''}"
            )

            # Build environment-specific guidance for the AI prompt
            env_guidance = {
                "development": """
**ENVIRONMENT CONTEXT: DEVELOPMENT**
This PR targets a DEVELOPMENT environment, which is used for experimentation and testing.
- Development changes are GENERALLY SAFER and carry lower risk
- Be MORE PERMISSIVE with confidence scores for development environments
- Focus primarily on detecting obviously dangerous changes (e.g., major breaking changes, security issues)
- Minor issues, experimental changes, and refactoring are ACCEPTABLE in development
- Unless there are clear red flags, lean towards HIGHER confidence scores""",
                "sandbox": """
**ENVIRONMENT CONTEXT: SANDBOX**
This PR targets a SANDBOX environment, which is a production-like environment requiring careful review.
- Sandbox is effectively a PRODUCTION environment despite its name
- Apply STRICT SCRUTINY to all changes
- Be CONSERVATIVE with confidence scores
- Even minor issues should lower the confidence score significantly
- Require high certainty that changes are safe before approving""",
                "production": """
**ENVIRONMENT CONTEXT: PRODUCTION**
This PR targets a PRODUCTION environment, requiring MAXIMUM CAUTION.
- Apply the STRICTEST SCRUTINY to all changes
- Be VERY CONSERVATIVE with confidence scores
- Any uncertainty or potential issues should result in LOW confidence scores
- Only the safest, most clearly documented changes should receive high scores""",
                "global": f"""
**ENVIRONMENT CONTEXT: GLOBAL (UNKNOWN OR CONFLICTING)**
{env_reason}
- Treating this as PRODUCTION-level risk for safety
- Apply the STRICTEST SCRUTINY to all changes
- Be VERY CONSERVATIVE with confidence scores
- The inability to clearly identify the environment adds additional risk"""
            }

            env_context = env_guidance.get(detected_env, env_guidance["global"])

            # Build prompt for AI with environment context
            prompt = f"""You are an expert DevOps engineer analyzing pull requests for automatic merging.
            Your task is to assess the risk level of changes and determine if they can be safely merged automatically.

            {env_context}

            Analyze this pull request for automatic merging safety:
            {pr_context}

            Terraform Plan Output:
            {plan_output if plan_output else "No plan output available"}

            Based on the above information, assess the risk level considering BOTH:
            1. The nature of the changes (type, scope, breaking changes, etc.)
            2. The target environment and its risk tolerance

            Consider:
            - Type of changes (provider updates, dependency updates, infrastructure changes, etc.)
            - Presence of breaking changes or major refactoring
            - Impact on infrastructure and services
            - Changelog information if available
            - Terraform plan output analysis (resources created/modified/destroyed)
            - **CRITICALLY: The environment context and its risk tolerance**

            Respond with ONLY: "SCORE: X% - EXPLANATION"
            (Include a brief mention of how the environment influenced your assessment)
            """

            logger.debug("📝 Generated Prompt:")
            logger.debug(f"   Prompt Length: {len(prompt)} characters")
            logger.debug(
                f"   Prompt Preview: {prompt[:500]}{'...' if len(prompt) > 500 else ''}"
            )

            # Call AI and get metadata
            ai_response, metadata = self._call_ai_provider_with_metadata(prompt)

            if ai_response:
                logger.debug("✅ AI Response Received:")
                logger.debug(f"   Response: {ai_response}")

                score, explanation = self._parse_ai_response(ai_response)
                logger.debug("📊 Parsed Results:")
                logger.debug(f"   Confidence Score: {score}%")
                logger.debug(f"   Explanation: {explanation}")

                # Apply similarity boost
                boosted_score, similarity_metadata = self._apply_similarity_boost(
                    score, pr_data
                )
                if similarity_metadata:
                    metadata.update({"similarity": similarity_metadata})
                    if boosted_score != score:
                        explanation += f" [Similarity boost applied: {score}% → {boosted_score}%, similar to PR #{similarity_metadata.get('most_similar_pr')}]"
                score = boosted_score

                # Record token usage metrics
                if self.metrics and metadata:
                    repo_name = (
                        pr_data.get("head", {}).get("repo", {}).get("name", "unknown")
                    )
                    model_name = metadata.get("model", "unknown")
                    engine_name = (
                        metadata.get("provider", "unknown").lower().replace(" ", "-")
                    )
                    input_tokens = metadata.get("input_tokens", 0)
                    output_tokens = metadata.get("output_tokens", 0)

                    self.metrics.record_token_usage(
                        repo=repo_name,
                        model=model_name,
                        engine=engine_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

                    logger.debug(
                        f"📈 Recorded metrics - Repo: {repo_name}, Model: {model_name}, Engine: {engine_name}, "
                        f"Input: {input_tokens}, Output: {output_tokens}"
                    )

                # Add environment information to metadata
                metadata["environment"] = detected_env
                metadata["environment_reason"] = env_reason

                return score, explanation, is_auto_merge_env, metadata
            else:
                # Fallback logic when AI is unavailable
                logger.warning("AI service unavailable, using fallback logic")
                logger.debug("🔄 Using Fallback Logic")

                fallback_score, fallback_explanation, fallback_is_auto_merge = (
                    self._fallback_confidence_calculation(
                        pr_data, plan_output, is_auto_merge_env
                    )
                )

                # Apply similarity boost to fallback score too
                boosted_fallback_score, similarity_metadata = (
                    self._apply_similarity_boost(fallback_score, pr_data)
                )
                if similarity_metadata and boosted_fallback_score != fallback_score:
                    fallback_explanation += f" [Similarity boost applied: {fallback_score}% → {boosted_fallback_score}%, similar to PR #{similarity_metadata.get('most_similar_pr')}]"
                fallback_score = boosted_fallback_score

                fallback_metadata = {
                    "provider": "fallback",
                    "model": "none",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "environment": detected_env,
                    "environment_reason": env_reason,
                }
                if similarity_metadata:
                    fallback_metadata.update({"similarity": similarity_metadata})

                return (
                    fallback_score,
                    fallback_explanation,
                    fallback_is_auto_merge,
                    fallback_metadata,
                )

        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            logger.debug(f"❌ Exception Details: {str(e)}")

            # Try to detect environment even on error
            try:
                detected_env, env_reason = self._detect_environment(pr_data)
            except Exception:
                detected_env, env_reason = "global", "Error detecting environment"

            error_metadata = {
                "provider": "error",
                "model": "none",
                "input_tokens": 0,
                "output_tokens": 0,
                "environment": detected_env,
                "environment_reason": env_reason,
            }
            return (
                0,
                f"Error calculating confidence score: {str(e)}",
                False,
                error_metadata,
            )

    def _fallback_confidence_calculation(
        self, pr_data: Dict[str, Any], plan_output: str, is_auto_merge_env: bool
    ) -> Tuple[int, str, bool]:
        """Fallback confidence calculation when AI is unavailable.

        Args:
            pr_data: Pull request data
            plan_output: Terraform plan output
            is_auto_merge_env: Whether this environment allows auto-merge

        Returns:
            Tuple of (confidence_score, explanation, is_auto_merge_env)
        """
        # Base score starts at 50%
        score = 50
        explanation_parts = []

        # Analyze PR title and description
        title = pr_data.get("title", "").lower()
        body = pr_data.get("body", "").lower()

        # Check for dependency updates (usually safe)
        if any(
            keyword in title
            for keyword in ["dependencies", "dependency", "update", "bump"]
        ):
            score += 20
            explanation_parts.append("Dependency update detected")

        # Check for provider updates (usually safe)
        if any(keyword in title for keyword in ["provider", "terraform"]):
            score += 15
            explanation_parts.append("Provider update detected")

        # Check for breaking changes in description
        if any(
            keyword in body
            for keyword in ["breaking", "breaking change", "deprecated", "removed"]
        ):
            score -= 30
            explanation_parts.append("Breaking changes detected")

        # Analyze Terraform plan output
        if plan_output:
            # Check for no changes (very safe)
            if "No changes" in plan_output:
                score += 25
                explanation_parts.append("No infrastructure changes")

            # Check for destructive changes
            if (
                "destroy" in plan_output.lower()
                or "update" in plan_output.lower()
                or "replace" in plan_output.lower()
            ):
                score -= 40
                explanation_parts.append("Destructive changes detected")

            # Check for resource additions (moderate risk)
            if "to add" in plan_output and "0 to add" not in plan_output:
                score -= 10
                explanation_parts.append("New resources being added")

        # Ensure score is within 0-100 range
        score = max(0, min(100, score))

        # Create explanation
        if explanation_parts:
            explanation = " - ".join(explanation_parts)
        else:
            explanation = "Standard risk assessment"

        return score, explanation, is_auto_merge_env

    def should_auto_merge(
        self, confidence_score: int, is_auto_merge_env: bool, enable_auto_merge: bool
    ) -> bool:
        """Determine if PR should be auto-merged.

        Args:
            confidence_score: AI confidence score (0-100)
            is_auto_merge_env: Whether this environment allows auto-merge
            enable_auto_merge: Whether auto-merge is enabled in config

        Returns:
            True if PR should be auto-merged, False otherwise
        """
        # Get minimum confidence score from config
        minimum_score = self.ai_config.get("minimum_confidence_score", 100)

        # Auto-merge only if:
        # 1. Auto-merge is enabled in config
        # 2. Confidence score meets or exceeds minimum threshold
        # 3. Environment allows auto-merge
        return (
            enable_auto_merge
            and confidence_score >= minimum_score
            and is_auto_merge_env
        )
