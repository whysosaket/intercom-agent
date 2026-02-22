"""Orchestrator Agent — central coordinator that delegates to specialized agents."""

from __future__ import annotations

import httpx

from app.agents.base import BaseAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.postprocessing_agent import PostProcessingAgent
from app.agents.response_agent import ResponseAgent
from app.agents.slack_agent import SlackAgent
from app.models.schemas import ContactInfo

INTERCOM_BASE_URL = "https://api.intercom.io"


class OrchestratorAgent(BaseAgent):
    """Central coordinator that delegates to specialized agents.

    Owns the Intercom HTTP client directly. Routes incoming messages
    through the agent pipeline:
      Memory Agent -> Response Agent -> PostProcessing Agent -> Route
    """

    def __init__(
        self,
        memory_agent: MemoryAgent,
        response_agent: ResponseAgent,
        postprocessing_agent: PostProcessingAgent,
        slack_agent: SlackAgent,
        intercom_access_token: str = "",
        intercom_admin_id: str = "",
        mock_mode: bool = False,
        confidence_threshold: float = 0.8,
    ):
        super().__init__(name="orchestrator")
        self.memory_agent = memory_agent
        self.response_agent = response_agent
        self.postprocessing_agent = postprocessing_agent
        self.slack_agent = slack_agent
        self.threshold = confidence_threshold

        # Intercom client (owned directly)
        self.admin_id = intercom_admin_id
        self.mock_mode = mock_mode
        self.sent_replies: list[dict] = []  # stores replies in mock mode

        if not mock_mode and intercom_access_token:
            self._http_client = httpx.AsyncClient(
                base_url=INTERCOM_BASE_URL,
                headers={
                    "Authorization": f"Bearer {intercom_access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        else:
            self._http_client = None

    async def initialize(self) -> None:
        """Initialize all child agents."""
        await self.memory_agent.initialize()
        await self.response_agent.initialize()
        await self.postprocessing_agent.initialize()
        await self.slack_agent.initialize()
        mode = "mock" if self.mock_mode else "real"
        self.logger.info(
            "Orchestrator agent initialized with all sub-agents (intercom=%s)", mode
        )

    async def shutdown(self) -> None:
        """Shutdown all child agents and close HTTP client."""
        await self.memory_agent.shutdown()
        await self.response_agent.shutdown()
        await self.postprocessing_agent.shutdown()
        await self.slack_agent.shutdown()
        if self._http_client:
            await self._http_client.aclose()

    # --- Intercom operations (absorbed from IntercomClient) ---

    async def reply_to_conversation(
        self,
        conversation_id: str,
        body: str,
    ) -> dict:
        """Send an admin reply to an Intercom conversation."""
        if self.mock_mode or self._http_client is None:
            entry = {"conversation_id": conversation_id, "body": body}
            self.sent_replies.append(entry)
            self.logger.info(
                "[MOCK INTERCOM] Reply to %s: %s", conversation_id, body[:100]
            )
            return {"type": "conversation", "id": conversation_id}

        self.logger.info("Replying to conversation %s", conversation_id)
        response = await self._http_client.post(
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
        if self.mock_mode or self._http_client is None:
            return {"conversations": [], "pages": {}}

        params: dict = {"per_page": per_page, "order": "desc", "sort": "updated_at"}
        if starting_after:
            params["starting_after"] = starting_after
        response = await self._http_client.get("/conversations", params=params)
        response.raise_for_status()
        return response.json()

    async def get_conversation(self, conversation_id: str) -> dict:
        """Retrieve a single conversation with all its parts."""
        if self.mock_mode or self._http_client is None:
            return {
                "id": conversation_id,
                "source": {},
                "conversation_parts": {"conversation_parts": []},
            }

        response = await self._http_client.get(f"/conversations/{conversation_id}")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client (alias for shutdown compatibility)."""
        if self._http_client:
            await self._http_client.aclose()

    # --- Orchestration ---

    async def handle_incoming_message(
        self,
        conversation_id: str,
        message_body: str,
        contact_info: ContactInfo | None = None,
        user_id: str = "",
    ) -> None:
        """Process an incoming Intercom message end-to-end.

        Pipeline: Memory -> Response -> PostProcessing -> Route
        """
        mem_user_id = user_id or (
            contact_info.email
            if contact_info and contact_info.email
            else conversation_id
        )
        self.logger.info(
            "Processing message for conversation %s (user=%s)",
            conversation_id,
            mem_user_id,
        )

        try:
            # Step 1: Fetch memory context via Memory Agent
            memory_context = await self.memory_agent.fetch_context(
                mem_user_id, message_body
            )

            # Step 2: Generate response via Response Agent
            result = await self.response_agent.generate(
                customer_message=message_body,
                memory_context=memory_context,
                contact_info=contact_info,
            )

            self.logger.info(
                "Conversation %s: confidence=%.2f, threshold=%.2f",
                conversation_id,
                result.confidence,
                self.threshold,
            )

            # Step 3: Post-process via PostProcessing Agent
            result = await self.postprocessing_agent.process(
                customer_message=message_body,
                generated_response=result,
            )

            # Step 4: Route based on confidence
            if result.confidence >= self.threshold:
                await self._auto_respond(
                    conversation_id,
                    mem_user_id,
                    message_body,
                    result.text,
                )
            else:
                await self.slack_agent.send_review_request(
                    conversation_id=conversation_id,
                    customer_message=message_body,
                    ai_response=result.text,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    user_id=mem_user_id,
                )

        except Exception:
            self.logger.exception(
                "Error processing message for conversation %s",
                conversation_id,
            )

    async def send_approved_response(
        self,
        conversation_id: str,
        customer_message: str,
        response_text: str,
        user_id: str = "",
        edited: bool = False,
        reasoning: str = "",
    ) -> None:
        """Send a human-approved (or edited) response to Intercom."""
        await self.reply_to_conversation(conversation_id, response_text)

        if user_id:
            await self.memory_agent.store_exchange(
                user_id, customer_message, response_text
            )

        # Store in global catalogue if:
        # - Human edited the response (human-curated knowledge), OR
        # - Human approved a skill-agent response (validated technical answer)
        is_skill_agent_response = reasoning.startswith("[Skill Agent]")
        if (edited or is_skill_agent_response) and customer_message:
            source_label = "edited" if edited else "skill-agent-approved"
            await self.memory_agent.store_to_global_catalogue(
                conversation_id=conversation_id,
                customer_message=customer_message,
                response_text=response_text,
                source_label=source_label,
            )

        self.logger.info(
            "Approved response sent for conversation %s", conversation_id
        )

    async def _auto_respond(
        self,
        conversation_id: str,
        user_id: str,
        customer_message: str,
        response_text: str,
    ) -> None:
        """Auto-send a high-confidence response and store context."""
        await self.reply_to_conversation(conversation_id, response_text)
        await self.memory_agent.store_exchange(
            user_id, customer_message, response_text
        )
        self.logger.info(
            "Auto-responded to conversation %s", conversation_id
        )
