"""Memory Agent — assembles context from MemZero and manages deferred storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.base import BaseAgent
from app.agents.memzero_agent import MemZeroAgent
from app.company import company_config

if TYPE_CHECKING:
    from app.chat.trace import TraceCollector

# Mem0 score threshold for a "near-exact" knowledge base match.
_NEAR_EXACT_MATCH_SCORE = 0.95
# Confidence boost applied when a near-exact match is found.
_NEAR_EXACT_MATCH_BOOST = 0.1


@dataclass
class MemoryContext:
    """All memory context needed for response generation."""

    conversation_history: list[dict] = field(default_factory=list)
    global_matches: list[dict] = field(default_factory=list)
    adjusted_confidence_boost: float = 0.0


class MemoryAgent(BaseAgent):
    """Fetches and assembles memory context from MemZero.

    Interfaces with the MemZero Agent to retrieve conversation history
    and global catalogue matches, then packages them for downstream agents.
    Also handles the deferred storage pattern for conversation exchanges.
    """

    def __init__(self, memzero_agent: MemZeroAgent):
        super().__init__(name="memory")
        self.memzero = memzero_agent

    async def initialize(self) -> None:
        self.logger.info("Memory agent initialized")

    async def fetch_context(
        self,
        user_id: str,
        message: str,
        trace: TraceCollector | None = None,
    ) -> MemoryContext:
        """Fetch all memory context for a given user message.

        Returns conversation history, global matches, and a precomputed
        confidence adjustment based on Mem0 relevance scores.
        """
        conv_history = self.memzero.search_conversation_history(
            user_id, query=message, trace=trace
        )
        global_matches = self.memzero.search_global_catalogue(
            message, trace=trace
        )
        boost = self._compute_confidence_boost(global_matches)

        if trace:
            with trace.step(
                "Compute confidence boost",
                "computation",
                input_summary=f"{len(global_matches)} global matches",
            ) as ev:
                ev.output_summary = f"boost={boost}" if boost > 0 else "no boost (no near-exact match)"
                ev.details = {"boost": boost}

        return MemoryContext(
            conversation_history=conv_history,
            global_matches=global_matches,
            adjusted_confidence_boost=boost,
        )

    async def store_exchange(
        self,
        user_id: str,
        customer_message: str,
        response_text: str,
    ) -> None:
        """Store both sides of a conversation exchange.

        Implements the deferred storage pattern: messages are only
        stored after approval or auto-send, not during intake.
        """
        self.memzero.store_conversation_turn(user_id, "user", customer_message)
        self.memzero.store_conversation_turn(user_id, "assistant", response_text)

    async def store_to_global_catalogue(
        self,
        conversation_id: str,
        customer_message: str,
        response_text: str,
        source_label: str = "intercom",
    ) -> None:
        """Store a conversation in the global catalogue for future retrieval."""
        platform = company_config.support_platform_name
        formatted = (
            f"{platform} conversation {conversation_id}:\n"
            f"Customer said: {customer_message}\n"
            f"Support said: {response_text}"
        )
        self.memzero.store_global_catalogue_conversation(
            formatted_conversation=formatted,
            conversation_id=conversation_id,
        )
        self.logger.info(
            "%s response stored in global catalogue for conversation %s",
            source_label,
            conversation_id,
        )

    @staticmethod
    def _compute_confidence_boost(global_matches: list[dict]) -> float:
        """Compute confidence boost from Mem0 relevance scores.

        Returns 0.1 if there is a near-exact match (score >= 0.95), else 0.0.
        """
        if not global_matches:
            return 0.0
        top_score = max(m.get("score", 0) for m in global_matches)
        return _NEAR_EXACT_MATCH_BOOST if top_score >= _NEAR_EXACT_MATCH_SCORE else 0.0
