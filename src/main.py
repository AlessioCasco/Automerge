#!/usr/bin/env python3

import argparse
import sys

from config import load_and_validate_config
from github_client import GitHubClient
from pr_processor import PRProcessor


def main():
    """Main entry point for the automerge application."""
    try:
        # Init parser for the arguments
        parser = argparse.ArgumentParser(
            prog="Automerge",
            description="Github PR auto-merger",
            epilog="Thanks for flying automerge")
        parser.add_argument(
            "--config_file",
            type=str,
            default="./config.json",
            help="JSON file holding the GitHub access token, default is ./config.json")
        parser.add_argument(
            "--force",
            default=False,
            action="store_true",
            help="Skip all regex and plan every PR")
        parser.add_argument(
            "--approve_all",
            action="store_true",
            default=False,
            help="Approves all PRs that match the filters in the config")
        args = parser.parse_args()

        # Load and validate configuration
        config = load_and_validate_config(args.config_file)

        # Extract info from config
        access_token = config["access_token"]
        owner = config["owner"]
        github_user = config["github_user"]
        repos = config["repos"]
        filters = config["filters"]

        # Initialize GitHub client
        github_client = GitHubClient(access_token, owner, github_user)

        # Get all pull requests
        all_pulls = github_client.get_pull_requests(repos, filters)

        if args.approve_all:
            print("Only Approving Now")
            github_client.approve_all_prs(all_pulls)
            sys.exit(0)

        # Initialize PR processor
        pr_processor = PRProcessor(github_client)

        # Process pull requests
        pr_processor.process_prs(all_pulls, args.force)

        print("\nAll done, exiting\n")

    except KeyboardInterrupt:
        print("\n\nExiting by user request.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
