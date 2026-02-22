"""MemZero Agent — sole gateway to Mem0 for all memory operations."""

from __future__ import annotations

from mem0 import MemoryClient

from app.agents.base import BaseAgent


class MemZeroAgent(BaseAgent):
    """Dedicated agent for all Mem0 (MemZero) operations.

    Owns the Mem0 SDK client directly and provides the single point
    of contact for memory storage, search, and retrieval throughout
    the system.
    """

    def __init__(self, api_key: str, global_user_id: str = "global_catalogue"):
        super().__init__(name="memzero")
        self.client = MemoryClient(api_key=api_key)
        self.global_user_id = global_user_id

    async def initialize(self) -> None:
        self.logger.info("MemZero agent initialized")

    # --- Search operations ---

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

    # --- Store operations ---

    def store_conversation_turn(
        self,
        user_id: str,
        role: str,
        content: str,
    ) -> dict:
        """Store a single conversation turn verbatim (infer=False)."""
        self.logger.info("Storing %s turn for user %s", role, user_id)
        return self.client.add(
            messages=[{"role": role, "content": content}],
            user_id=user_id,
            infer=False,
        )

    def store_global_catalogue(
        self,
        question: str,
        answer: str,
        conversation_id: str,
    ) -> dict:
        """Store an approved Q&A pair in the global catalogue."""
        self.logger.info(
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
        """Store an entire conversation as a single user message in the global catalogue."""
        self.logger.info(
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
