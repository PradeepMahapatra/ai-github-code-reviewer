import json
import logging
from json import JSONDecodeError

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.config import get_settings
from app.github_client import GitHubApiClient, GitHubClientError
from app.review_service import retrieve_pull_request_review_input
from app.webhook_events import parse_pull_request_event
from app.webhook_security import is_valid_signature

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, object]:
    payload = await request.body()
    settings = get_settings()
    if not is_valid_signature(
        payload,
        request.headers.get("X-Hub-Signature-256"),
        settings.github_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event")
    delivery_id = request.headers.get("X-GitHub-Delivery")

    if not event_type:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")
    if not delivery_id:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Delivery header")

    try:
        decoded_payload = json.loads(payload)
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc

    if event_type != "pull_request":
        return {
            "status": "ignored",
            "event": event_type,
            "delivery_id": delivery_id,
            "reason": "unsupported event type",
        }

    if not isinstance(decoded_payload, dict):
        raise HTTPException(status_code=400, detail="Malformed webhook payload")
    action = decoded_payload.get("action")
    if action is not None and action not in {"opened", "synchronize", "reopened"}:
        return {
            "status": "ignored",
            "event": event_type,
            "delivery_id": delivery_id,
            "reason": "unsupported pull request action",
        }

    try:
        pull_request_event = parse_pull_request_event(decoded_payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Malformed pull request payload",
        ) from exc

    logger.info(
        "Received supported Pull Request event %s for %s/%s#%s",
        delivery_id,
        pull_request_event.repository_owner,
        pull_request_event.repository_name,
        pull_request_event.pull_request_number,
    )
    try:
        token = settings.github_token.get_secret_value() if settings.github_token else None
        with GitHubApiClient(token=token) as client:
            review_input = retrieve_pull_request_review_input(
                pull_request_event,
                client,
            )
    except GitHubClientError as exc:
        logger.warning(
            "Unable to retrieve Pull Request data for %s/%s#%s: %s",
            pull_request_event.repository_owner,
            pull_request_event.repository_name,
            pull_request_event.pull_request_number,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Pull Request data",
        ) from exc

    return {
        "status": "accepted",
        "message": "Pull Request event accepted for processing",
        "event": event_type,
        "delivery_id": delivery_id,
        "pull_request": review_input.model_dump(),
    }
