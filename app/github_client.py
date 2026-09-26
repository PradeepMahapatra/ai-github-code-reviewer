"""Client for retrieving GitHub pull request data."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


class GitHubClientError(Exception):
    """Base exception for GitHub client failures."""


class MissingGitHubTokenError(GitHubClientError):
    """Raised when GITHUB_TOKEN is not configured."""


class AuthenticationError(GitHubClientError):
    """Raised when GitHub rejects the configured credentials."""


class RepositoryNotFoundError(GitHubClientError):
    """Raised when the requested repository does not exist or is inaccessible."""


class PullRequestNotFoundError(GitHubClientError):
    """Raised when the requested pull request does not exist."""


class GitHubApiError(GitHubClientError):
    """Raised for an unexpected GitHub API response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API error ({status_code}): {message}")


class GitHubNetworkError(GitHubClientError):
    """Raised when a request cannot reach GitHub."""


class GitHubTimeoutError(GitHubClientError):
    """Raised when a GitHub request exceeds its timeout."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    state: str
    head_sha: str


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None


class GitHubApiClient:
    """Retrieve pull requests and changed files from GitHub's REST API."""

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved_token = token or os.getenv("GITHUB_TOKEN")
        if not resolved_token:
            raise MissingGitHubTokenError(
                "GITHUB_TOKEN environment variable is required"
            )

        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {resolved_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubApiClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_pull_request(self, owner: str, repository: str, number: int) -> PullRequest:
        self._ensure_repository(owner, repository)
        response = self._request("GET", f"/repos/{owner}/{repository}/pulls/{number}")
        if response.status_code == 404:
            raise PullRequestNotFoundError(
                f"Pull Request #{number} was not found in {owner}/{repository}"
            )

        payload = self._json_object(response)
        return PullRequest(
            number=int(payload["number"]),
            title=str(payload["title"]),
            state=str(payload["state"]),
            head_sha=str(payload["head"]["sha"]),
        )

    def get_changed_files(
        self, owner: str, repository: str, number: int
    ) -> list[ChangedFile]:
        self._ensure_repository(owner, repository)
        response = self._request(
            "GET", f"/repos/{owner}/{repository}/pulls/{number}/files"
        )
        if response.status_code == 404:
            raise PullRequestNotFoundError(
                f"Pull Request #{number} was not found in {owner}/{repository}"
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise GitHubApiError(response.status_code, "Unexpected files response")

        return [
            ChangedFile(
                filename=str(file_data["filename"]),
                status=str(file_data["status"]),
                additions=int(file_data["additions"]),
                deletions=int(file_data["deletions"]),
                changes=int(file_data["changes"]),
                patch=file_data.get("patch"),
            )
            for file_data in payload
        ]

    def _ensure_repository(self, owner: str, repository: str) -> None:
        response = self._request("GET", f"/repos/{owner}/{repository}")
        if response.status_code == 404:
            raise RepositoryNotFoundError(
                f"Repository {owner}/{repository} was not found"
            )

    def _request(self, method: str, path: str) -> httpx.Response:
        try:
            response = self._client.request(method, path)
        except httpx.TimeoutException as exc:
            raise GitHubTimeoutError("GitHub request timed out") from exc
        except httpx.RequestError as exc:
            raise GitHubNetworkError(f"GitHub network error: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("GitHub rejected the provided credentials")
        if response.status_code >= 400 and response.status_code != 404:
            raise GitHubApiError(response.status_code, self._error_message(response))
        return response

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        payload = response.json()
        if not isinstance(payload, dict):
            raise GitHubApiError(response.status_code, "Unexpected pull request response")
        return payload

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "Unknown GitHub API error"
        if isinstance(payload, dict) and isinstance(payload.get("message"), str):
            return payload["message"]
        return "Unknown GitHub API error"
