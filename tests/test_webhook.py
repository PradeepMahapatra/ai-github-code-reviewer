from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def webhook_headers() -> dict[str, str]:
    return {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-123",
    }


def test_valid_pull_request_webhook() -> None:
    response = client.post(
        "/webhook",
        headers=webhook_headers(),
        json={"action": "opened", "pull_request": {"number": 1}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "received",
        "processed": False,
        "event": "pull_request",
        "delivery_id": "delivery-123",
    }


def test_missing_event_header() -> None:
    headers = webhook_headers()
    headers.pop("X-GitHub-Event")

    response = client.post("/webhook", headers=headers, json={"action": "opened"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing X-GitHub-Event header"


def test_missing_delivery_id_header() -> None:
    headers = webhook_headers()
    headers.pop("X-GitHub-Delivery")

    response = client.post("/webhook", headers=headers, json={"action": "opened"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing X-GitHub-Delivery header"


def test_malformed_json_body() -> None:
    response = client.post(
        "/webhook",
        headers={**webhook_headers(), "Content-Type": "application/json"},
        content=b'{"action":',
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Malformed JSON body"
