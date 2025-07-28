#!/usr/bin/env python3

"""Utility functions and constants for the automerge application."""

# Timeout constants (in seconds)
DEFAULT_TIMEOUT = 10
MERGEABLE_STATE_TIMEOUT = 240  # 4 minutes
COMMENT_DELAY = 4  # seconds between comments

# GitHub API constants
GITHUB_API_VERSION = "2022-11-28"
GITHUB_ACCEPT_HEADER = "application/vnd.github+json"

# PR states
MERGEABLE_STATE_UNKNOWN = "unknown"
MERGEABLE_STATE_BEHIND = "behind"
MERGEABLE_STATE_BLOCKED = "blocked"
MERGEABLE_STATE_CLEAN = "clean"
MERGEABLE_STATE_DIRTY = "dirty"

# Review states
REVIEW_STATE_APPROVED = "APPROVED"
REVIEW_STATE_DISMISSED = "DISMISSED"

# Labels
LABEL_AUTOMERGE_IGNORE = "automerge_ignore"
LABEL_AUTOMERGE_NO_PROJECT = "automerge_no_project"
LABEL_AUTOMERGE_DISMISSED = "automerge_dismissed"
LABEL_AUTOMERGE_CONFLICT = "automerge_conflict"

# Comments
COMMENT_ATLANTIS_PLAN = "atlantis plan"
COMMENT_ATLANTIS_UNLOCK = "atlantis unlock"
COMMENT_IGNORE_AUTOMERGE = "This PR will be ignored by automerge"
COMMENT_CLOSE_NEW_VERSION = "This PR will be closed since there is a new version of this dependency"
COMMENT_NO_PROJECT = "Will be ignored, 0 projects planned, usually due to modules update or no file changed, check and close them yourself please"

# Merge method
MERGE_METHOD_SQUASH = "squash"


def format_pr_info(pr: dict) -> str:
    """Format PR information for logging.

    Args:
        pr: Pull request dictionary

    Returns:
        Formatted string with PR information
    """
    return f"PR {pr['number']} in repo {pr['head']['repo']['name']}"


def format_api_error(status_code: int, response_text: str) -> str:
    """Format API error message.

    Args:
        status_code: HTTP status code
        response_text: Response text from API

    Returns:
        Formatted error message
    """
    return f"Status code: {status_code} \n Reason: {response_text}"


def is_mergeable_state_final(state: str) -> bool:
    """Check if mergeable state is final (not unknown).

    Args:
        state: Mergeable state string

    Returns:
        True if state is final, False otherwise

    Raises:
        TypeError: If state is None
    """
    if state is None:
        raise TypeError("state cannot be None")
    return state != MERGEABLE_STATE_UNKNOWN


def should_update_branch(state: str) -> bool:
    """Check if branch should be updated based on mergeable state.

    Args:
        state: Mergeable state string

    Returns:
        True if branch should be updated, False otherwise
    """
    return state == MERGEABLE_STATE_BEHIND


def is_clean_state(state: str) -> bool:
    """Check if mergeable state is clean.

    Args:
        state: Mergeable state string

    Returns:
        True if state is clean, False otherwise
    """
    return state == MERGEABLE_STATE_CLEAN


def is_blocked_state(state: str) -> bool:
    """Check if mergeable state is blocked.

    Args:
        state: Mergeable state string

    Returns:
        True if state is blocked, False otherwise
    """
    return state == MERGEABLE_STATE_BLOCKED


def is_dirty_state(state: str) -> bool:
    """Check if mergeable state is dirty.

    Args:
        state: Mergeable state string

    Returns:
        True if state is dirty, False otherwise
    """
    return state == MERGEABLE_STATE_DIRTY
