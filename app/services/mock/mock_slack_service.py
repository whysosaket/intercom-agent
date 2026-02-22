import logging

logger = logging.getLogger(__name__)


class MockSlackService:
    """Logs Slack messages instead of posting to a real workspace."""

    def __init__(self):
        self.review_requests: list[dict] = []

    async def send_review_request(
        self,
        conversation_id: str,
        customer_message: str,
        ai_response: str,
        confidence: float,
        reasoning: str,
        user_id: str = "",
    ) -> dict:
        entry = {
            "conversation_id": conversation_id,
            "customer_message": customer_message,
            "ai_response": ai_response,
            "confidence": confidence,
            "reasoning": reasoning,
        }
        self.review_requests.append(entry)
        logger.info(
            "[MOCK SLACK] Review request for %s (confidence=%.2f)",
            conversation_id,
            confidence,
        )
        return {"ok": True}
