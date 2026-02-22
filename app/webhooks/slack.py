import json
import logging
from typing import TYPE_CHECKING

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.config import settings

if TYPE_CHECKING:
    from app.agents.orchestrator_agent import OrchestratorAgent

logger = logging.getLogger(__name__)

orchestrator: "OrchestratorAgent | None" = None

slack_app = AsyncApp(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
)


def set_orchestrator(orch: "OrchestratorAgent") -> None:
    global orchestrator
    orchestrator = orch


def _extract_customer_message_from_blocks(blocks: list[dict]) -> str:
    """Extract the customer message from the review message blocks."""
    for block in blocks:
        text = block.get("text", {})
        if isinstance(text, dict):
            value = text.get("text", "")
            if value.startswith("*Customer Message:*"):
                # Remove the markdown prefix and quote marker
                msg = value.replace("*Customer Message:*\n>", "")
                return msg.strip()
    return ""


@slack_app.action("approve_response")
async def handle_approve(ack, action, client, body):
    """Approve and send the AI response to Intercom."""
    await ack()
    payload = json.loads(action["value"])
    conversation_id = payload["conversation_id"]
    response_text = payload["response_text"]
    user_id = payload.get("user_id", "")
    reasoning = payload.get("reasoning", "")

    customer_message = _extract_customer_message_from_blocks(
        body["message"]["blocks"]
    )

    if orchestrator:
        await orchestrator.send_approved_response(
            conversation_id, customer_message, response_text,
            user_id=user_id, reasoning=reasoning,
        )

    user = body["user"]["username"]
    await client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":white_check_mark: *Response Sent*\n"
                        f"Approved by @{user}\n"
                        f"Conversation: {conversation_id}"
                    ),
                },
            }
        ],
        text=f"Response approved for conversation {conversation_id}",
    )
    logger.info(
        "Response approved by %s for conversation %s", user, conversation_id
    )


@slack_app.action("edit_response")
async def handle_edit(ack, action, client, body):
    """Open a modal for editing the AI response before sending."""
    await ack()
    payload = json.loads(action["value"])

    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "edit_response_modal",
            "title": {"type": "plain_text", "text": "Edit Response"},
            "submit": {"type": "plain_text", "text": "Send"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "response_block",
                    "label": {"type": "plain_text", "text": "Response"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "response_text",
                        "multiline": True,
                        "initial_value": payload["response_text"],
                    },
                },
            ],
            "private_metadata": json.dumps({
                "conversation_id": payload["conversation_id"],
                "user_id": payload.get("user_id", ""),
                "channel_id": body["channel"]["id"],
                "message_ts": body["message"]["ts"],
            }),
        },
    )


@slack_app.view("edit_response_modal")
async def handle_edit_submission(ack, view, client, body):
    """Handle the edited response modal submission."""
    await ack()
    edited_text = (
        view["state"]["values"]["response_block"]["response_text"]["value"]
    )
    metadata = json.loads(view["private_metadata"])
    conversation_id = metadata["conversation_id"]
    user_id = metadata.get("user_id", "")

    # Fetch original message to extract customer question
    original_msg = await client.conversations_history(
        channel=metadata["channel_id"],
        latest=metadata["message_ts"],
        inclusive=True,
        limit=1,
    )
    customer_message = ""
    if original_msg["messages"]:
        customer_message = _extract_customer_message_from_blocks(
            original_msg["messages"][0].get("blocks", [])
        )

    if orchestrator:
        await orchestrator.send_approved_response(
            conversation_id, customer_message, edited_text,
            user_id=user_id, edited=True,
        )

    user = body["user"]["username"]
    await client.chat_update(
        channel=metadata["channel_id"],
        ts=metadata["message_ts"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":pencil: *Edited Response Sent*\n"
                        f"Edited by @{user}\n"
                        f"Conversation: {conversation_id}"
                    ),
                },
            }
        ],
        text=f"Edited response sent for conversation {conversation_id}",
    )
    logger.info(
        "Edited response sent by %s for conversation %s",
        user,
        conversation_id,
    )


@slack_app.action("reject_response")
async def handle_reject(ack, action, client, body):
    """Reject the AI response — no reply sent to Intercom."""
    await ack()
    payload = json.loads(action["value"])
    conversation_id = payload["conversation_id"]

    user = body["user"]["username"]
    await client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":x: *Response Rejected*\n"
                        f"Rejected by @{user}\n"
                        f"Conversation: {conversation_id}"
                    ),
                },
            }
        ],
        text=f"Response rejected for conversation {conversation_id}",
    )
    logger.info(
        "Response rejected by %s for conversation %s", user, conversation_id
    )


slack_handler = AsyncSlackRequestHandler(slack_app)
