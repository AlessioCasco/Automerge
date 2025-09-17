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
except ImportError:
    from metrics import AutomergeMetrics

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

    def __init__(self, github_token: str, github_client=None, ai_config: Dict[str, Any] = None, metrics: AutomergeMetrics = None):
        """Initialize AI confidence calculator.

        Args:
            github_token: GitHub access token with Copilot permissions
            github_client: GitHub client instance for API calls
            ai_config: AI configuration dictionary
            metrics: Metrics collector for token usage tracking
        """
        self.github_token = github_token
        self.github_client = github_client
        self.ai_config = ai_config or {}
        self.metrics = metrics
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
Repository: {pr_data.get('head', {}).get('repo', {}).get('name', 'N/A')}
Base Branch: {pr_data.get('base', {}).get('ref', 'N/A')}
Head Branch: {pr_data.get('head', {}).get('ref', 'N/A')}
Labels: {', '.join(labels) if labels else 'None'}"""

        return context

    def _extract_terraform_plan(self, pr_data: Dict[str, Any], terraform_user: str = "tl-terraform") -> str:
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
                logger.error("GitHub client not available for terraform plan extraction")
                return ""

            # Get the issue URL from PR data
            issue_url = pr_data.get("issue_url")
            if not issue_url:
                return ""

            # Use GitHubClient to extract the plan
            plan_content = self.github_client.get_last_terraform_plan(issue_url, terraform_user)

            if plan_content:
                logger.debug(f"📋 Successfully extracted Terraform plan ({len(plan_content)} characters)")
                return plan_content
            else:
                logger.debug(f"📋 No Terraform plan found from {terraform_user}")
                return ""

        except Exception as e:
            logger.error(f"Error extracting Terraform plan: {e}")
            return ""

    def _call_ai_provider_with_metadata(self, prompt: str) -> Tuple[Optional[str], Dict[str, Any]]:
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
            return None, {"provider": "unknown", "model": "none", "input_tokens": 0, "output_tokens": 0}

    def _call_github_copilot_with_metadata(self, prompt: str) -> Tuple[Optional[str], Dict[str, Any]]:
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
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Use different headers for the proxy
            proxy_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # Debug logging
            logger.debug("🤖 GitHub Copilot API Call Details:")
            logger.debug(f"   URL: {url}")
            logger.debug(f"   Model: {model}")

            response = requests.post(
                url,
                headers=proxy_headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT
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
                    "output_tokens": usage.get("output_tokens", 0)
                }

                return content, metadata
            else:
                logger.error(f"GitHub Copilot API proxy error: {response.status_code} - {response.text}")
                logger.debug(f"   Error Response: {response.text}")
                return None, {"provider": "GitHub Copilot", "model": model, "input_tokens": 0, "output_tokens": 0}

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling GitHub Copilot API proxy: {e}")
            return None, {"provider": "GitHub Copilot", "model": "unknown", "input_tokens": 0, "output_tokens": 0}
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing GitHub Copilot API proxy response: {e}")
            logger.debug(f"   Raw Response: {response.text if 'response' in locals() else 'N/A'}")
            return None, {"provider": "GitHub Copilot", "model": "unknown", "input_tokens": 0, "output_tokens": 0}

    def _call_claude_code_with_metadata(self, prompt: str) -> Tuple[Optional[str], Dict[str, Any]]:
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
                return None, {"provider": "Claude Code", "model": model, "input_tokens": 0, "output_tokens": 0}

            # Use Claude Code API endpoint
            url = f"{api_base}/v1/messages"

            payload = {
                "model": model,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Use Claude Code headers
            claude_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            }

            # Check if we should disable SSL verification (for local development)
            disable_ssl_verify = os.environ.get("DISABLE_SSL_VERIFY", "false").lower() == "true"

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
                verify=not disable_ssl_verify  # Disable SSL verification if environment variable is set
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
                    "output_tokens": usage.get("output_tokens", 0)
                }

                return content, metadata
            else:
                logger.error(f"Claude Code API error: {response.status_code} - {response.text}")
                logger.debug(f"   Error Response: {response.text}")
                return None, {"provider": "Claude Code", "model": model, "input_tokens": 0, "output_tokens": 0}

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Claude Code API: {e}")
            return None, {"provider": "Claude Code", "model": "unknown", "input_tokens": 0, "output_tokens": 0}
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing Claude Code API response: {e}")
            logger.debug(f"   Raw Response: {response.text if 'response' in locals() else 'N/A'}")
            return None, {"provider": "Claude Code", "model": "unknown", "input_tokens": 0, "output_tokens": 0}

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
                    explanation = ai_response[explanation_start + len(f"{score}%"):].strip()
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

    def _is_auto_merge_environment(self, pr_data: Dict[str, Any]) -> bool:
        """Determine if the PR is targeting an environment that allows auto-merge.

        Args:
            pr_data: Pull request data

        Returns:
            True if environment allows auto-merge, False otherwise
        """
        # Get configured auto-merge environments
        auto_merge_envs = self.ai_config.get("auto_merge_environments", ["development"])

        # Check branch name patterns
        base_branch = pr_data.get("base", {}).get("ref", "").lower()
        head_branch = pr_data.get("head", {}).get("ref", "").lower()

        # Define environment patterns mapping
        env_patterns = {
            "development": [
                r"dev", r"development", r"staging", r"test",
                r"feature/", r"hotfix/", r"develop"
            ],
            "sandbox": [
                r"sandbox", r"sbx"
            ],
            "production": [
                r"main", r"master", r"prod", r"production", r"release/"
            ]
        }

        # Check if any configured environment matches
        for env in auto_merge_envs:
            env_lower = env.lower()
            if env_lower in env_patterns:
                patterns = env_patterns[env_lower]
                for pattern in patterns:
                    if re.search(pattern, base_branch) or re.search(pattern, head_branch):
                        logger.debug(f"Environment '{env}' detected for auto-merge (pattern: {pattern})")
                        return True

        # Default to False (conservative approach)
        logger.debug(f"No auto-merge environment detected. Configured: {auto_merge_envs}")
        return False

    def calculate_confidence_score(self, pr_data: Dict[str, Any]) -> Tuple[int, str, bool, Dict[str, Any]]:
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

            # Determine environment
            is_auto_merge_env = self._is_auto_merge_environment(pr_data)

            logger.debug("🔍 PR Analysis Context:")
            logger.debug(f"   PR Title: {pr_data.get('title', 'N/A')}")
            logger.debug(f"   Repository: {pr_data.get('head', {}).get('repo', {}).get('name', 'N/A')}")
            logger.debug(f"   Base Branch: {pr_data.get('base', {}).get('ref', 'N/A')}")
            logger.debug(f"   Head Branch: {pr_data.get('head', {}).get('ref', 'N/A')}")
            logger.debug(f"   Environment: {'Auto-merge Allowed' if is_auto_merge_env else 'Auto-merge Disabled'} (for auto-merge only)")
            logger.debug(f"   Plan Output: {plan_output[:200]}{'...' if len(plan_output) > 200 else ''}")

            # Build prompt for AI - focus only on PR description, changelog, and plan output
            prompt = f"""You are an expert DevOps engineer analyzing pull requests for automatic merging.
            Your task is to assess the risk level of changes and determine if they can be safely merged automatically.
            Consider ONLY the following factors:
            1. PR description and title
            2. Changelog information (if linked or present in description)
            3. Terraform plan output
            DO NOT consider the environment (development vs production) for the confidence score.
            The environment is only used to determine if auto-merge is allowed.
            Analyze this pull request for automatic merging safety:
            {pr_context}
            Terraform Plan Output:
            {plan_output if plan_output else 'No plan output available'}
            Based on the above information, assess the risk level and determine if this PR can be safely merged automatically.
            Consider:
            - Type of changes (provider updates, dependency updates, etc.)
            - Presence of breaking changes
            - Impact on infrastructure
            - Changelog information if available
            - Terraform plan output analysis
            Respond with ONLY: "SCORE: X% - EXPLANATION"
            """

            logger.debug("📝 Generated Prompt:")
            logger.debug(f"   Prompt Length: {len(prompt)} characters")
            logger.debug(f"   Prompt Preview: {prompt[:500]}{'...' if len(prompt) > 500 else ''}")

            # Call AI and get metadata
            ai_response, metadata = self._call_ai_provider_with_metadata(prompt)

            if ai_response:
                logger.debug("✅ AI Response Received:")
                logger.debug(f"   Response: {ai_response}")

                score, explanation = self._parse_ai_response(ai_response)
                logger.debug("📊 Parsed Results:")
                logger.debug(f"   Confidence Score: {score}%")
                logger.debug(f"   Explanation: {explanation}")

                # Record token usage metrics
                if self.metrics and metadata:
                    repo_name = pr_data.get("head", {}).get("repo", {}).get("name", "unknown")
                    model_name = metadata.get("model", "unknown")
                    engine_name = metadata.get("provider", "unknown").lower().replace(" ", "-")
                    input_tokens = metadata.get("input_tokens", 0)
                    output_tokens = metadata.get("output_tokens", 0)

                    self.metrics.record_token_usage(
                        repo=repo_name,
                        model=model_name,
                        engine=engine_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens
                    )

                    logger.debug(f"📈 Recorded metrics - Repo: {repo_name}, Model: {model_name}, Engine: {engine_name}, "
                               f"Input: {input_tokens}, Output: {output_tokens}")

                return score, explanation, is_auto_merge_env, metadata
            else:
                # Fallback logic when AI is unavailable
                logger.warning("AI service unavailable, using fallback logic")
                logger.debug("🔄 Using Fallback Logic")

                fallback_score, fallback_explanation, fallback_is_auto_merge = self._fallback_confidence_calculation(pr_data, plan_output, is_auto_merge_env)
                fallback_metadata = {
                    "provider": "fallback",
                    "model": "none",
                    "input_tokens": 0,
                    "output_tokens": 0
                }

                return fallback_score, fallback_explanation, fallback_is_auto_merge, fallback_metadata

        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            logger.debug(f"❌ Exception Details: {str(e)}")
            error_metadata = {
                "provider": "error",
                "model": "none",
                "input_tokens": 0,
                "output_tokens": 0
            }
            return 0, f"Error calculating confidence score: {str(e)}", False, error_metadata

    def _fallback_confidence_calculation(self, pr_data: Dict[str, Any], plan_output: str, is_auto_merge_env: bool) -> Tuple[int, str, bool]:
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
        if any(keyword in title for keyword in ["dependencies", "dependency", "update", "bump"]):
            score += 20
            explanation_parts.append("Dependency update detected")

        # Check for provider updates (usually safe)
        if any(keyword in title for keyword in ["provider", "terraform"]):
            score += 15
            explanation_parts.append("Provider update detected")

        # Check for breaking changes in description
        if any(keyword in body for keyword in ["breaking", "breaking change", "deprecated", "removed"]):
            score -= 30
            explanation_parts.append("Breaking changes detected")

        # Analyze Terraform plan output
        if plan_output:
            # Check for no changes (very safe)
            if "No changes" in plan_output:
                score += 25
                explanation_parts.append("No infrastructure changes")

            # Check for destructive changes
            if "destroy" in plan_output.lower() or "update" in plan_output.lower() or "replace" in plan_output.lower():
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

    def should_auto_merge(self, confidence_score: int, is_auto_merge_env: bool, enable_auto_merge: bool) -> bool:
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
        return enable_auto_merge and confidence_score >= minimum_score and is_auto_merge_env
