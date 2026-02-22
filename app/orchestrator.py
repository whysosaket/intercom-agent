from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.schemas import ContactInfo, GeneratedResponse

if TYPE_CHECKING:
    from app.services.intercom_client import IntercomClient
    from app.services.memory_service import MemoryService
    from app.services.openai_service import OpenAIService
    from app.services.slack_service import SlackService
    from app.services.postprocessor import PostProcessor
    from skill_consumer import SkillAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        memory_service: MemoryService,
        openai_service: OpenAIService,
        intercom_client: IntercomClient,
        slack_service: SlackService,
        confidence_threshold: float = 0.8,
        skill_agent: SkillAgent | None = None,
        post_processor: PostProcessor | None = None,
    ):
        self.memory = memory_service
        self.ai = openai_service
        self.intercom = intercom_client
        self.slack = slack_service
        self.threshold = confidence_threshold
        self.skill_agent = skill_agent
        self.post_processor = post_processor

    async def handle_incoming_message(
        self,
        conversation_id: str,
        message_body: str,
        contact_info: ContactInfo | None = None,
        user_id: str = "",
    ) -> None:
        """Process an incoming Intercom message end-to-end."""
        # Use customer email as Mem0 user_id, fall back to conversation_id
        mem_user_id = user_id or (
            contact_info.email
            if contact_info and contact_info.email
            else conversation_id
        )
        logger.info(
            "Processing message for conversation %s (user=%s)",
            conversation_id,
            mem_user_id,
        )

        try:
            # 1. Retrieve context from both memory scopes
            #    (user message is NOT stored yet — deferred until approval/auto-send)
            conv_history = self.memory.search_conversation_history(
                mem_user_id, query=message_body
            )
            global_matches = self.memory.search_global_catalogue(message_body)

            # 2. Generate AI response with confidence
            result = await self.ai.generate_response(
                customer_message=message_body,
                conversation_history=conv_history,
                relevant_memories=global_matches,
                contact_info=contact_info,
            )

            # 3. Adjust confidence based on Mem0 relevance scores
            final_confidence = self._adjust_confidence(
                result.confidence, global_matches
            )

            logger.info(
                "Conversation %s: AI confidence=%.2f, adjusted=%.2f, threshold=%.2f",
                conversation_id,
                result.confidence,
                final_confidence,
                self.threshold,
            )

            # 3b. Skill Agent fallback: if primary AI couldn't answer confidently,
            #     try the skill documentation. This covers both empty responses
            #     (category 3: "not supported") and weak partial answers that
            #     the skill docs might handle better with full API details.
            if (
                self.skill_agent is not None
                and final_confidence < self.threshold
            ):
                logger.info(
                    "Primary AI below threshold (confidence=%.2f), trying skill agent",
                    final_confidence,
                )
                try:
                    skill_result = await self.skill_agent.answer(message_body)
                    if (
                        skill_result.answer_text
                        and skill_result.confidence > final_confidence
                    ):
                        result = GeneratedResponse(
                            text=skill_result.answer_text,
                            confidence=skill_result.confidence,
                            reasoning=f"[Skill Agent] {skill_result.reasoning}",
                        )
                        final_confidence = skill_result.confidence
                        logger.info(
                            "Skill agent answered with confidence=%.2f, sources=%s",
                            skill_result.confidence,
                            skill_result.sources,
                        )
                except Exception:
                    logger.exception("Skill agent query failed")

            # 3c. Post-process: refine tone/formatting and re-evaluate confidence
            if self.post_processor is not None and result.text.strip():
                try:
                    from app.models.schemas import PostProcessorInput

                    pp_input = PostProcessorInput(
                        customer_message=message_body,
                        generated_response=result.text,
                        original_confidence=final_confidence,
                        original_reasoning=result.reasoning,
                    )
                    pp_output = await self.post_processor.process(pp_input)
                    result = GeneratedResponse(
                        text=pp_output.refined_text,
                        confidence=pp_output.final_confidence,
                        reasoning=result.reasoning,
                    )
                    final_confidence = pp_output.final_confidence
                    logger.info(
                        "Post-processor refined response: confidence %.2f -> %.2f",
                        pp_input.original_confidence,
                        final_confidence,
                    )
                except Exception:
                    logger.exception(
                        "Post-processor failed, using original response"
                    )

            # 4. Route based on confidence
            if final_confidence >= self.threshold:
                await self._auto_respond(
                    conversation_id, mem_user_id, message_body, result.text
                )
            else:
                await self.slack.send_review_request(
                    conversation_id=conversation_id,
                    customer_message=message_body,
                    ai_response=result.text,
                    confidence=final_confidence,
                    reasoning=result.reasoning,
                    user_id=mem_user_id,
                )

        except Exception:
            logger.exception(
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
        await self.intercom.reply_to_conversation(conversation_id, response_text)
        if user_id:
            # Store both user message and assistant response (deferred from intake)
            self.memory.store_conversation_turn(
                user_id, "user", customer_message
            )
            self.memory.store_conversation_turn(
                user_id, "assistant", response_text
            )
        # Store in global catalogue if:
        # - Human edited the response (human-curated knowledge), OR
        # - Human approved a skill-agent response (validated technical answer)
        is_skill_agent_response = reasoning.startswith("[Skill Agent]")
        if (edited or is_skill_agent_response) and customer_message:
            formatted = (
                f"Intercom conversation {conversation_id}:\n"
                f"Customer said: {customer_message}\n"
                f"Support said: {response_text}"
            )
            self.memory.store_global_catalogue_conversation(
                formatted_conversation=formatted,
                conversation_id=conversation_id,
            )
            source = "edited" if edited else "skill-agent-approved"
            logger.info(
                "%s response stored in global catalogue for conversation %s",
                source,
                conversation_id,
            )
        logger.info(
            "Approved response sent for conversation %s", conversation_id
        )

    async def _auto_respond(
        self,
        conversation_id: str,
        user_id: str,
        customer_message: str,
        response_text: str,
    ) -> None:
        """Auto-send a high-confidence response and store full context."""
        await self.intercom.reply_to_conversation(conversation_id, response_text)
        # Store both user message and assistant response (deferred from intake)
        self.memory.store_conversation_turn(
            user_id, "user", customer_message
        )
        self.memory.store_conversation_turn(
            user_id, "assistant", response_text
        )
        logger.info(
            "Auto-responded to conversation %s", conversation_id
        )

    def _adjust_confidence(
        self,
        ai_confidence: float,
        global_matches: list[dict],
    ) -> float:
        """Boost confidence if Mem0 returned a near-exact match."""
        if not global_matches:
            return ai_confidence

        top_score = max(m.get("score", 0) for m in global_matches)
        if top_score >= 0.95 and ai_confidence >= 0.7:
            return min(ai_confidence + 0.1, 1.0)

        return ai_confidence
