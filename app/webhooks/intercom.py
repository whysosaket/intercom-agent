import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.utils.hmac_verify import verify_intercom_signature
from app.models.schemas import ContactInfo

if TYPE_CHECKING:
    from app.agents.orchestrator_agent import OrchestratorAgent
    from app.services.message_coordinator import MessageCoordinator

logger = logging.getLogger(__name__)
router = APIRouter()

orchestrator: "OrchestratorAgent | None" = None
message_coordinator: "MessageCoordinator | None" = None


def _extract_latest_message(payload: dict) -> str:
    """Extract the most recent customer message from the webhook payload."""
    topic = payload.get("topic", "")
    data = payload.get("data", {}).get("item", {})

    if topic == "conversation.user.created":
        # New conversation: message is in source.body
        body = data.get("source", {}).get("body", "")
    else:
        # Reply: message is in the last conversation part
        parts = (
            data.get("conversation_parts", {}).get("conversation_parts", [])
        )
        if parts:
            body = parts[-1].get("body", "")
        else:
            body = data.get("source", {}).get("body", "")

    # Strip HTML tags (Intercom sends HTML)
    import re

    return re.sub(r"<[^>]+>", "", body).strip()


def _extract_contact_info(payload: dict) -> ContactInfo:
    """Extract contact name and email from the payload."""
    data = payload.get("data", {}).get("item", {})
    source = data.get("source", {})
    author = source.get("author", {})
    return ContactInfo(
        id=str(author.get("id", "")),
        name=author.get("name", ""),
        email=author.get("email", ""),
    )


@router.post("/webhooks/intercom")
async def intercom_webhook(request: Request):
    """Receive Intercom webhook events and dispatch to orchestrator."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature", "")

    if not verify_intercom_signature(
        raw_body, signature, settings.INTERCOM_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    topic = payload.get("topic", "")

    if topic in ("conversation.user.created", "conversation.user.replied"):
        conversation_id = payload["data"]["item"]["id"]
        message_body = _extract_latest_message(payload)
        contact_info = _extract_contact_info(payload)

        logger.info(
            "Received %s for conversation %s: %s",
            topic,
            conversation_id,
            message_body[:100],
        )

        if message_coordinator and message_body:
            await message_coordinator.enqueue(
                conversation_id=conversation_id,
                message_body=message_body,
                contact_info=contact_info,
                user_id=contact_info.email or "",
            )

    return {"status": "ok"}
