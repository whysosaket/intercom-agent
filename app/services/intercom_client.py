import logging

import httpx

logger = logging.getLogger(__name__)


class IntercomClient:
    BASE_URL = "https://api.intercom.io"

    def __init__(self, access_token: str, admin_id: str):
        self.admin_id = admin_id
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def reply_to_conversation(
        self,
        conversation_id: str,
        body: str,
    ) -> dict:
        """Send an admin reply to an Intercom conversation."""
        logger.info("Replying to conversation %s", conversation_id)
        response = await self._client.post(
            f"/conversations/{conversation_id}/reply",
            json={
                "message_type": "comment",
                "type": "admin",
                "admin_id": self.admin_id,
                "body": body,
            },
        )
        response.raise_for_status()
        return response.json()

    async def list_conversations(
        self,
        per_page: int = 20,
        starting_after: str | None = None,
    ) -> dict:
        """List conversations with cursor-based pagination."""
        params: dict = {"per_page": per_page, "order": "desc", "sort": "updated_at"}
        if starting_after:
            params["starting_after"] = starting_after
        response = await self._client.get("/conversations", params=params)
        response.raise_for_status()
        return response.json()

    async def get_conversation(self, conversation_id: str) -> dict:
        """Retrieve a single conversation with all its parts."""
        response = await self._client.get(f"/conversations/{conversation_id}")
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()
