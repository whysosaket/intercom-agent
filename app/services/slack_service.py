import json
import logging

from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackService:
    def __init__(self, bot_token: str, channel_id: str):
        self.client = AsyncWebClient(token=bot_token)
        self.channel_id = channel_id

    async def send_review_request(
        self,
        conversation_id: str,
        customer_message: str,
        ai_response: str,
        confidence: float,
        reasoning: str,
        user_id: str = "",
    ) -> dict:
        """Post a review message with Approve/Edit/Reject buttons."""
        blocks = self._build_review_blocks(
            conversation_id, customer_message, ai_response, confidence, reasoning,
            user_id=user_id,
        )
        logger.info(
            "Sending review request to Slack for conversation %s",
            conversation_id,
        )
        result = await self.client.chat_postMessage(
            channel=self.channel_id,
            text=f"Review needed for conversation {conversation_id}",
            blocks=blocks,
        )
        return result

    def _build_review_blocks(
        self,
        conversation_id: str,
        customer_message: str,
        ai_response: str,
        confidence: float,
        reasoning: str,
        user_id: str = "",
    ) -> list[dict]:
        approve_value = json.dumps({
            "conversation_id": conversation_id,
            "response_text": ai_response,
            "user_id": user_id,
            "reasoning": reasoning,
        })
        edit_value = json.dumps({
            "conversation_id": conversation_id,
            "response_text": ai_response,
            "user_id": user_id,
        })
        reject_value = json.dumps({
            "conversation_id": conversation_id,
        })

        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "AI Response Review Required",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Customer Message:*\n>{customer_message}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Conversation ID:* {conversation_id}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:* {confidence:.2f} / 1.0",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggested Response:*\n{ai_response}",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*AI Reasoning:* {reasoning}",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve and Send"},
                        "style": "primary",
                        "action_id": "approve_response",
                        "value": approve_value,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Edit Response"},
                        "action_id": "edit_response",
                        "value": edit_value,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "action_id": "reject_response",
                        "value": reject_value,
                    },
                ],
            },
        ]
