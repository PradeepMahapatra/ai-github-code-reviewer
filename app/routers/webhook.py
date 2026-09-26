import json
from json import JSONDecodeError

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.webhook_security import is_valid_signature

router = APIRouter()


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
        json.loads(payload)
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc

    return {
        "status": "received",
        "processed": False,
        "event": event_type,
        "delivery_id": delivery_id,
    }
