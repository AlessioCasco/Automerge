#!/usr/bin/env python3

import json
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

    if not config["repos"] or not isinstance(config["repos"], list):
        raise ValueError("repos must be a non-empty list")

    if not config["filters"] or not isinstance(config["filters"], list):
        raise ValueError("filters must be a non-empty list")

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
    return config
