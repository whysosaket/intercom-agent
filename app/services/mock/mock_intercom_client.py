import logging

logger = logging.getLogger(__name__)


class MockIntercomClient:
    """Logs Intercom API calls instead of making real HTTP requests."""

    def __init__(self):
        self.sent_replies: list[dict] = []

    async def reply_to_conversation(
        self,
        conversation_id: str,
        body: str,
    ) -> dict:
        entry = {"conversation_id": conversation_id, "body": body}
        self.sent_replies.append(entry)
        logger.info(
            "[MOCK INTERCOM] Reply to %s: %s", conversation_id, body[:100]
        )
        return {"type": "conversation", "id": conversation_id}

    async def list_conversations(
        self,
        per_page: int = 20,
        starting_after: str | None = None,
    ) -> dict:
        return {"conversations": [], "pages": {}}

    async def get_conversation(self, conversation_id: str) -> dict:
        return {
            "id": conversation_id,
            "source": {},
            "conversation_parts": {"conversation_parts": []},
        }

    async def close(self):
        pass
