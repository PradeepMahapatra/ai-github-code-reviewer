import hashlib
import hmac

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import app
import app.routers.webhook as webhook_router


client = TestClient(app)
TEST_SECRET = "test-webhook-secret"


def webhook_headers(signature: str | None = None) -> dict[str, str]:
    headers = {
        "X-GitHub-Event": "pull_request",
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


def test_valid_signature(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":"opened"}'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(payload)),
        content=payload,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "processed": False,
        "event": "pull_request",
        "delivery_id": "delivery-123",
    }


def test_signature_is_generated_from_exact_raw_body(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{ "action": "opened" }'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(payload)),
        content=payload,
    )

    assert response.status_code == 200


def test_invalid_signature(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":"opened"}'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(payload, "wrong-secret")),
        content=payload,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_missing_signature(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":"opened"}'

    response = client.post("/webhook", headers=webhook_headers(), content=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_unavailable_webhook_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        webhook_router,
        "get_settings",
        lambda: Settings(_env_file=None),
    )
    payload = b'{"action":"opened"}'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(payload)),
        content=payload,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_malformed_signature(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":"opened"}'

    response = client.post(
        "/webhook",
        headers=webhook_headers("sha256=not-a-hex-digest"),
        content=payload,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_modified_request_body_is_rejected(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    signed_payload = b'{"action":"opened"}'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(signed_payload)),
        content=b'{"action":"closed"}',
    )

    assert response.status_code == 401


def test_missing_event_header(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":"opened"}'
    headers = webhook_headers(sign_payload(payload))
    headers.pop("X-GitHub-Event")

    response = client.post("/webhook", headers=headers, content=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing X-GitHub-Event header"


def test_missing_delivery_id_header(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":"opened"}'
    headers = webhook_headers(sign_payload(payload))
    headers.pop("X-GitHub-Delivery")

    response = client.post("/webhook", headers=headers, content=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing X-GitHub-Delivery header"


def test_malformed_json_body(monkeypatch) -> None:
    configure_test_secret(monkeypatch)
    payload = b'{"action":'

    response = client.post(
        "/webhook",
        headers=webhook_headers(sign_payload(payload)),
        content=payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Malformed JSON body"
