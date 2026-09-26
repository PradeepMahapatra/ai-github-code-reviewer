import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.github_client import ChangedFile, GitHubApiError, PullRequest
from app.main import app
import app.routers.webhook as webhook_router


client = TestClient(app)
TEST_SECRET = "test-webhook-secret"


class FakeGitHubApiClient:
    calls: list[tuple[str, str, str, int]] = []
    error: GitHubApiError | None = None

    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self.calls = []
        FakeGitHubApiClient.calls = self.calls

    def __enter__(self) -> "FakeGitHubApiClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_pull_request(self, owner: str, repository: str, number: int) -> PullRequest:
        self.calls.append(("pull_request", owner, repository, number))
        if self.error:
            raise self.error
        return PullRequest(
            number=number,
            title="Retrieved Pull Request title",
            state="open",
            head_sha="retrieved-head-sha",
        )

    def get_changed_files(
        self, owner: str, repository: str, number: int
    ) -> list[ChangedFile]:
        self.calls.append(("changed_files", owner, repository, number))
        if self.error:
            raise self.error
        return [
            ChangedFile(
                filename="app/main.py",
                status="modified",
                additions=3,
                deletions=1,
                changes=4,
                patch="@@ -1 +1,3 @@",
            )
        ]


def webhook_headers(signature: str | None = None, event: str = "pull_request") -> dict[str, str]:
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "delivery-123",
    }
    if signature is not None:
        headers["X-Hub-Signature-256"] = signature
    return headers


def sign_payload(payload: bytes, secret: str = TEST_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def configure_test_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        webhook_router,
        "get_settings",
        lambda: Settings(_env_file=None, github_webhook_secret=SecretStr(TEST_SECRET)),
    )
    FakeGitHubApiClient.calls = []
    FakeGitHubApiClient.error = None
    monkeypatch.setattr(webhook_router, "GitHubApiClient", FakeGitHubApiClient)


def pull_request_payload(action: str = "opened") -> dict[str, object]:
    return {
        "action": action,
        "number": 42,
        "repository": {
            "name": "review-target",
            "owner": {"login": "octo-owner"},
        },
        "pull_request": {
            "title": "Improve reviewer output",
            "head": {"sha": "abc123def456"},
        },
    }


def post_signed_webhook(monkeypatch, payload: object, event: str = "pull_request"):
    configure_test_secret(monkeypatch)
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(raw_payload), event),
        content=raw_payload,
    )


def test_supported_pull_request_actions(monkeypatch) -> None:
    for action in ("opened", "synchronize", "reopened"):
        response = post_signed_webhook(monkeypatch, pull_request_payload(action))

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        assert response.json()["pull_request"]["action"] == action


def test_supported_event_extracts_internal_pull_request_fields(monkeypatch) -> None:
    response = post_signed_webhook(monkeypatch, pull_request_payload())

    assert response.status_code == 200
    assert response.json()["pull_request"] == {
        "repository_owner": "octo-owner",
        "repository_name": "review-target",
        "pull_request_number": 42,
        "pull_request_title": "Retrieved Pull Request title",
        "action": "opened",
        "head_commit_sha": "retrieved-head-sha",
        "changed_files": [
            {
                "filename": "app/main.py",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "changes": 4,
                "patch": "@@ -1 +1,3 @@",
            }
        ],
    }
    assert response.json()["message"] == "Pull Request event accepted for processing"


def test_supported_event_passes_repository_and_number_to_client(monkeypatch) -> None:
    response = post_signed_webhook(monkeypatch, pull_request_payload())

    assert response.status_code == 200
    assert FakeGitHubApiClient.calls == [
        ("pull_request", "octo-owner", "review-target", 42),
        ("changed_files", "octo-owner", "review-target", 42),
    ]


def test_unsupported_pull_request_action_is_ignored(monkeypatch) -> None:
    response = post_signed_webhook(monkeypatch, pull_request_payload("closed"))

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "unsupported pull request action"
    assert FakeGitHubApiClient.calls == []


def test_unrelated_event_is_ignored(monkeypatch) -> None:
    response = post_signed_webhook(
        monkeypatch,
        {"action": "created", "ignored": "payload"},
        event="issues",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "unsupported event type"
    assert FakeGitHubApiClient.calls == []


def test_github_api_failure_returns_safe_error(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    FakeGitHubApiClient.error = GitHubApiError(500, "internal details")
    payload = pull_request_payload()
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(raw_payload)),
        content=raw_payload,
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to retrieve Pull Request data"}


def test_missing_required_pull_request_field_returns_bad_request(monkeypatch) -> None:
    payload = pull_request_payload()
    del payload["pull_request"]["head"]

    response = post_signed_webhook(monkeypatch, payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Malformed pull request payload"


def test_missing_pull_request_action_returns_bad_request(monkeypatch) -> None:
    payload = pull_request_payload()
    del payload["action"]

    response = post_signed_webhook(monkeypatch, payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Malformed pull request payload"


def test_signature_is_verified_before_event_processing(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = pull_request_payload()
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    calls = 0

    def fail_if_parsed(_: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("payload parser must not run for an invalid signature")

    monkeypatch.setattr(webhook_router, "parse_pull_request_event", fail_if_parsed)
    response = client.post(
        "/webhook",
        headers=webhook_headers("sha256=" + "0" * 64),
        content=raw_payload,
    )

    assert response.status_code == 401
    assert calls == 0


def test_valid_signature() -> None:
    payload = b'{"action":"opened"}'
    signature = sign_payload(payload)

    from app.webhook_security import is_valid_signature

    assert is_valid_signature(payload, signature, SecretStr(TEST_SECRET))


def test_modified_request_body_is_rejected(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    signed_payload = b'{"action":"opened"}'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(signed_payload)),
        content=b'{"action":"closed"}',
    )

    assert response.status_code == 401


def test_missing_signature(monkeypatch) -> None:
    configure_test_secret(monkeypatch)

    response = client.post(
        "/webhook",
        headers=webhook_headers(),
        content=b'{"action":"opened"}',
    )

    assert response.status_code == 401


def test_malformed_signature(monkeypatch) -> None:
    configure_test_secret(monkeypatch)

    response = client.post(
        "/webhook",
        headers=webhook_headers("sha256=not-a-hex-digest"),
        content=b'{"action":"opened"}',
    )

    assert response.status_code == 401
