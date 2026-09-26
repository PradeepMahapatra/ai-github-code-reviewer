from __future__ import annotations

import unittest
from collections.abc import Iterator

import httpx

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


class GitHubApiClientTests(unittest.TestCase):
    def make_client(self, responses: list[httpx.Response]) -> GitHubApiClient:
        response_iterator: Iterator[httpx.Response] = iter(responses)

        def handler(request: httpx.Request) -> httpx.Response:
            response = next(response_iterator)
            response.request = request
            return response

        return GitHubApiClient(token="test-token", transport=httpx.MockTransport(handler))

    def test_successful_pull_request_retrieval(self) -> None:
        client = self.make_client(
            [
                httpx.Response(200, json={"full_name": "octo/demo"}),
                httpx.Response(
                    200,
                    json={
                        "number": 42,
                        "title": "Improve review output",
                        "state": "open",
                        "head": {"sha": "abc123"},
                    },
                ),
            ]
        )
        with client:
            pull_request = client.get_pull_request("octo", "demo", 42)

        self.assertEqual(pull_request.number, 42)
        self.assertEqual(pull_request.title, "Improve review output")
        self.assertEqual(pull_request.head_sha, "abc123")

    def test_successful_changed_files_retrieval(self) -> None:
        client = self.make_client(
            [
                httpx.Response(200, json={"full_name": "octo/demo"}),
                httpx.Response(
                    200,
                    json=[
                        {
                            "filename": "app/reviewer.py",
                            "status": "modified",
                            "additions": 4,
                            "deletions": 1,
                            "changes": 5,
                            "patch": "@@ -1 +1,4 @@",
                        },
                        {
                            "filename": "docs.md",
                            "status": "added",
                            "additions": 2,
                            "deletions": 0,
                            "changes": 2,
                        },
                    ],
                ),
            ]
        )
        with client:
            changed_files = client.get_changed_files("octo", "demo", 42)

        self.assertEqual(len(changed_files), 2)
        self.assertEqual(changed_files[0].filename, "app/reviewer.py")
        self.assertEqual(changed_files[0].patch, "@@ -1 +1,4 @@")
        self.assertIsNone(changed_files[1].patch)

    def test_authentication_failure(self) -> None:
        client = self.make_client([httpx.Response(401, json={"message": "Bad credentials"})])
        with client:
            with self.assertRaises(AuthenticationError):
                client.get_pull_request("octo", "demo", 42)

    def test_missing_token(self) -> None:
        with self.assertRaises(MissingGitHubTokenError):
            GitHubApiClient(token="")

    def test_repository_not_found(self) -> None:
        client = self.make_client([httpx.Response(404, json={"message": "Not Found"})])
        with client:
            with self.assertRaises(RepositoryNotFoundError):
                client.get_pull_request("octo", "demo", 42)

    def test_pull_request_not_found(self) -> None:
        client = self.make_client(
            [
                httpx.Response(200, json={"full_name": "octo/demo"}),
                httpx.Response(404, json={"message": "Not Found"}),
            ]
        )
        with client:
            with self.assertRaises(PullRequestNotFoundError):
                client.get_pull_request("octo", "demo", 42)

    def test_github_api_error(self) -> None:
        client = self.make_client(
            [
                httpx.Response(200, json={"full_name": "octo/demo"}),
                httpx.Response(500, json={"message": "Server Error"}),
            ]
        )
        with client:
            with self.assertRaises(GitHubApiError):
                client.get_pull_request("octo", "demo", 42)

    def test_network_error(self) -> None:
        request = httpx.Request("GET", "https://api.github.com/repos/octo/demo")

        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        client = GitHubApiClient(token="test-token", transport=httpx.MockTransport(handler))
        with client:
            with self.assertRaises(GitHubNetworkError):
                client.get_pull_request("octo", "demo", 42)

    def test_timeout_error(self) -> None:
        request = httpx.Request("GET", "https://api.github.com/repos/octo/demo")

        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("request timed out", request=request)

        client = GitHubApiClient(token="test-token", transport=httpx.MockTransport(handler))
        with client:
            with self.assertRaises(GitHubTimeoutError):
                client.get_pull_request("octo", "demo", 42)


if __name__ == "__main__":
    unittest.main()
