"""Command-line entry point for reviewing a GitHub pull request summary."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from app.github_client import (
    AuthenticationError,
    GitHubApiClient,
    GitHubApiError,
    GitHubNetworkError,
    GitHubTimeoutError,
    MissingGitHubTokenError,
    PullRequestNotFoundError,
    RepositoryNotFoundError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retrieve a GitHub pull request and its changed files."
    )
    parser.add_argument("owner", help="GitHub repository owner")
    parser.add_argument("repository", help="GitHub repository name")
    parser.add_argument("pull_request", type=positive_integer, help="Pull request number")
    return parser


def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("pull request number must be positive")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        with GitHubApiClient() as client:
            pull_request = client.get_pull_request(
                args.owner, args.repository, args.pull_request
            )
            changed_files = client.get_changed_files(
                args.owner, args.repository, args.pull_request
            )
    except (
        AuthenticationError,
        GitHubApiError,
        GitHubNetworkError,
        GitHubTimeoutError,
        MissingGitHubTokenError,
        PullRequestNotFoundError,
        RepositoryNotFoundError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Repository: {args.owner}/{args.repository}")
    print(f"Pull Request: #{pull_request.number}")
    print(f"Title: {pull_request.title}")
    print(f"State: {pull_request.state}")
    print(f"Head commit SHA: {pull_request.head_sha}")
    print(f"Changed files: {len(changed_files)}")

    for changed_file in changed_files:
        print(f"\nFile: {changed_file.filename}")
        print(f"Status: {changed_file.status}")
        print(f"Additions: {changed_file.additions}")
        print(f"Deletions: {changed_file.deletions}")
        print(f"Changes: {changed_file.changes}")
        if changed_file.patch is None:
            print("Patch: unavailable")
        else:
            print("Patch:")
            print(changed_file.patch)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
