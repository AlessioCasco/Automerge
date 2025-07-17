#!/usr/bin/env python3

import json
from typing import Dict, Any


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


def use_config(config: Dict[str, Any], key: str) -> Any:
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
        raise SystemExit(1)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration structure and required fields.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If configuration is invalid
    """
    required_keys = ["access_token", "owner", "github_user", "repos", "filters"]

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
    for repo in config["repos"]:
        if not isinstance(repo, str):
            raise ValueError(f"All repos must be strings, found: {type(repo)}")

    # Validate that all filters are strings
    for filter_pattern in config["filters"]:
        if not isinstance(filter_pattern, str):
            raise ValueError(f"All filters must be strings, found: {type(filter_pattern)}")


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
