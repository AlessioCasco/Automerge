#!/usr/bin/env python3

"""Automerge package for GitHub PR automation."""

from .github_client import GitHubClient
from .pr_processor import PRProcessor
from .config import load_and_validate_config, read_config, use_config, validate_config
from .utils import (
    DEFAULT_TIMEOUT,
    MERGEABLE_STATE_TIMEOUT,
    COMMENT_DELAY,
    GITHUB_API_VERSION,
    GITHUB_ACCEPT_HEADER,
    MERGEABLE_STATE_UNKNOWN,
    MERGEABLE_STATE_BEHIND,
    MERGEABLE_STATE_BLOCKED,
    MERGEABLE_STATE_CLEAN,
    MERGEABLE_STATE_DIRTY,
    REVIEW_STATE_APPROVED,
    REVIEW_STATE_DISMISSED,
    LABEL_AUTOMERGE_IGNORE,
    LABEL_AUTOMERGE_NO_PROJECT,
    LABEL_AUTOMERGE_DISMISSED,
    LABEL_AUTOMERGE_CONFLICT,
    COMMENT_ATLANTIS_PLAN,
    COMMENT_ATLANTIS_UNLOCK,
    COMMENT_IGNORE_AUTOMERGE,
    COMMENT_CLOSE_NEW_VERSION,
    COMMENT_NO_PROJECT,
    MERGE_METHOD_SQUASH,
    format_pr_info,
    format_api_error,
    is_mergeable_state_final,
    should_update_branch,
    is_clean_state,
    is_blocked_state,
    is_dirty_state,
)

__version__ = "1.0.12"
__author__ = "AlessioCasco"

__all__ = [
    "GitHubClient",
    "PRProcessor",
    "load_and_validate_config",
    "read_config",
    "use_config",
    "validate_config",
    "DEFAULT_TIMEOUT",
    "MERGEABLE_STATE_TIMEOUT",
    "COMMENT_DELAY",
    "GITHUB_API_VERSION",
    "GITHUB_ACCEPT_HEADER",
    "MERGEABLE_STATE_UNKNOWN",
    "MERGEABLE_STATE_BEHIND",
    "MERGEABLE_STATE_BLOCKED",
    "MERGEABLE_STATE_CLEAN",
    "MERGEABLE_STATE_DIRTY",
    "REVIEW_STATE_APPROVED",
    "REVIEW_STATE_DISMISSED",
    "LABEL_AUTOMERGE_IGNORE",
    "LABEL_AUTOMERGE_NO_PROJECT",
    "LABEL_AUTOMERGE_DISMISSED",
    "LABEL_AUTOMERGE_CONFLICT",
    "COMMENT_ATLANTIS_PLAN",
    "COMMENT_ATLANTIS_UNLOCK",
    "COMMENT_IGNORE_AUTOMERGE",
    "COMMENT_CLOSE_NEW_VERSION",
    "COMMENT_NO_PROJECT",
    "MERGE_METHOD_SQUASH",
    "format_pr_info",
    "format_api_error",
    "is_mergeable_state_final",
    "should_update_branch",
    "is_clean_state",
    "is_blocked_state",
    "is_dirty_state",
]
