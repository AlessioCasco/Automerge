#!/usr/bin/env python3

import json
import os
from typing import Dict, Any, Union


def read_config(config_file: str) -> Dict[str, Any]:
    """Read configuration from JSON file.

    Args:
        config_file: Location of the config file

    Returns:
        Dictionary containing the configuration

    Raises:
        OSError: If config file cannot be read
    """
    try:
        with open(config_file, encoding="utf-8") as f:
            print(f"Attempting to open config file in {config_file}\n")
            config = json.load(f)
            return config

    except OSError as exc:
        msg = f"Error reading config file at {config_file}. {exc}"
        raise OSError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Error reading config file at {config_file}. {exc}"
        raise OSError(msg) from exc


def use_config(config: Dict[str, Any], key: str) -> Union[str, list, dict]:
    """Extract a key from the configuration.

    Args:
        config: Configuration dictionary
        key: Key to extract from the config

    Returns:
        Value associated with the key

    Raises:
        SystemExit: If key is not found in config
    """
    try:
        return config[key]

    except KeyError:
        print(f'Error reading key "{key}" from config')
        raise SystemExit(1) from None


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration structure and required fields.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If configuration is invalid or required keys are missing
        TypeError: If configuration values have incorrect types
    """
    required_keys = ["access_token", "owner",
                     "github_user", "repos", "filters"]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: {key}")

    if not config["access_token"]:
        raise ValueError("access_token cannot be empty")

    if not config["owner"]:
        raise ValueError("owner cannot be empty")

    if not config["github_user"]:
        raise ValueError("github_user cannot be empty")

    if not config["filters"] or not isinstance(config["filters"], list):
        raise ValueError("filters must be a non-empty list")

    if not isinstance(config["repos"], list):
        raise ValueError("repos must be a list")

    # Validate that all repos are strings
    for i, repo in enumerate(config["repos"]):
        if not isinstance(repo, str) or not repo.strip():
            repo_type = type(repo).__name__
            raise ValueError(f"Repository at index {i} must be a non-empty string, found: {repo_type}")

    # Validate that all filters are strings
    for i, filter_pattern in enumerate(config["filters"]):
        if not isinstance(filter_pattern, str) or not filter_pattern.strip():
            filter_type = type(filter_pattern).__name__
            raise ValueError(f"Filter at index {i} must be a non-empty string, found: {filter_type}")

    # Validate optional AI configuration
    if "enable_ai_confidence_score" in config:
        if not isinstance(config["enable_ai_confidence_score"], bool):
            raise ValueError("enable_ai_confidence_score must be a boolean")

    if "enable_ai_automerge_action" in config:
        if not isinstance(config["enable_ai_automerge_action"], bool):
            raise ValueError("enable_ai_automerge_action must be a boolean")

    if "disable_pr_comments" in config:
        if not isinstance(config["disable_pr_comments"], bool):
            raise ValueError("disable_pr_comments must be a boolean")

    # Validate AI repos configuration
    if "ai_repos" in config:
        if not isinstance(config["ai_repos"], list):
            raise ValueError("ai_repos must be a list")

        for i, repo in enumerate(config["ai_repos"]):
            if not isinstance(repo, str) or not repo.strip():
                repo_type = type(repo).__name__
                raise ValueError(f"AI repository at index {i} must be a non-empty string, found: {repo_type}")

    # Validate AI provider configuration if AI is enabled
    if config.get("enable_ai_confidence_score", False):
        if "ai_provider" not in config:
            raise ValueError("ai_provider is required when enable_ai_confidence_score is true")

        if config["ai_provider"] not in ["github", "claude-code"]:
            raise ValueError("ai_provider must be either 'github' or 'claude-code'")

        if "ai_config" not in config:
            raise ValueError("ai_config is required when enable_ai_confidence_score is true")

        ai_config = config["ai_config"]
        provider = config["ai_provider"]

        if provider not in ai_config:
            raise ValueError(f"ai_config must contain configuration for '{provider}'")

        provider_config = ai_config[provider]

        if provider == "github":
            if "api_base" not in provider_config:
                raise ValueError("github config must contain 'api_base'")
            if "model" not in provider_config:
                raise ValueError("github config must contain 'model'")
        elif provider == "claude-code":
            if "api_base" not in provider_config:
                raise ValueError("claude-code config must contain 'api_base'")
            if "api_key" not in provider_config:
                raise ValueError("claude-code config must contain 'api_key'")
            if "model" not in provider_config:
                raise ValueError("claude-code config must contain 'model'")

    # Validate AI auto-merge configuration
    if config.get("enable_ai_automerge_action", False):
        if not config.get("enable_ai_confidence_score", False):
            raise ValueError("enable_ai_automerge_action requires enable_ai_confidence_score to be true")

    # Validate test PRs configuration
    if "test_prs" in config:
        if not isinstance(config["test_prs"], list):
            raise ValueError("test_prs must be a list")

        for i, test_pr in enumerate(config["test_prs"]):
            if not isinstance(test_pr, dict):
                raise ValueError(f"test_pr at index {i} must be a dictionary")

            if "repo" not in test_pr or "pr_number" not in test_pr:
                raise ValueError(f"test_pr at index {i} must contain 'repo' and 'pr_number' keys")

            if not isinstance(test_pr["repo"], str) or not test_pr["repo"].strip():
                raise ValueError(f"test_pr repo at index {i} must be a non-empty string")

            if not isinstance(test_pr["pr_number"], int) or test_pr["pr_number"] <= 0:
                raise ValueError(f"test_pr pr_number at index {i} must be a positive integer")


def load_and_validate_config(config_file: str) -> Dict[str, Any]:
    """Load and validate configuration from file.

    Args:
        config_file: Path to configuration file

    Returns:
        Validated configuration dictionary

    Raises:
        OSError: If config file cannot be read
        ValueError: If configuration is invalid
        SystemExit: If required keys are missing
    """
    config = read_config(config_file)
    validate_config(config)

    # Override with environment variables if present
    if os.environ.get("ENABLE_AI_CONFIDENCE_SCORE"):
        config["enable_ai_confidence_score"] = os.environ.get("ENABLE_AI_CONFIDENCE_SCORE").lower() == "true"

    if os.environ.get("ENABLE_AI_AUTOMERGE_ACTION"):
        config["enable_ai_automerge_action"] = os.environ.get("ENABLE_AI_AUTOMERGE_ACTION").lower() == "true"

    print(config)
    return config
