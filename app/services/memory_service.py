import logging

from mem0 import MemoryClient

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(
        self,
        api_key: str,
        global_user_id: str = "global_catalogue",
    ):
        self.client = MemoryClient(api_key=api_key)
        self.global_user_id = global_user_id

    def store_conversation_turn(
        self,
        user_id: str,
        role: str,
        content: str,
    ) -> dict:
        """Store a single conversation turn verbatim (infer=False)."""
        logger.info("Storing %s turn for user %s", role, user_id)
        return self.client.add(
            messages=[{"role": role, "content": content}],
            user_id=user_id,
            infer=False,
        )

    def search_conversation_history(
        self,
        user_id: str,
        query: str = "",
        top_k: int = 20,
    ) -> list[dict]:
        """Retrieve recent conversation turns for context."""
        return self.client.search(
            query=query or "conversation history",
            user_id=user_id,
            top_k=top_k,
        )

    def search_global_catalogue(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Search the global answer catalogue for relevant past Q&A pairs."""
        return self.client.search(
            query=query,
            user_id=self.global_user_id,
            top_k=top_k,
        )

    def store_global_catalogue(
        self,
        question: str,
        answer: str,
        conversation_id: str,
    ) -> dict:
        """Store an approved Q&A pair in the global catalogue."""
        logger.info(
            "Storing Q&A in global catalogue from conversation %s",
            conversation_id,
        )
        return self.client.add(
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ],
            user_id=self.global_user_id,
            infer=False,
            metadata={"source": "intercom", "conversation_id": conversation_id},
        )

    def store_global_catalogue_conversation(
        self,
        formatted_conversation: str,
        conversation_id: str,
    ) -> dict:
        """Store an entire conversation as a single user message in the global catalogue.

        The formatted_conversation string contains the full conversation with
        structured turn prefixes like 'User said: ...' and 'Assistant said: ...'.
        """
        logger.info(
            "Storing conversation %s in global catalogue (single-message format)",
            conversation_id,
        )
        return self.client.add(
            messages=[{"role": "user", "content": formatted_conversation}],
            user_id=self.global_user_id,
            infer=False,
            async_mode=True,
            metadata={
                "source": "intercom_sync",
                "conversation_id": conversation_id,
            },
        )
