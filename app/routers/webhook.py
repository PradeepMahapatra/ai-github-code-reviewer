import json
from json import JSONDecodeError

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, object]:
    event_type = request.headers.get("X-GitHub-Event")
    delivery_id = request.headers.get("X-GitHub-Delivery")

    if not event_type:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")
    if not delivery_id:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Delivery header")

    try:
        json.loads(await request.body())
    except JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc

    return {
        "status": "received",
        "processed": False,
        "event": event_type,
        "delivery_id": delivery_id,
    }
