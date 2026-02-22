"""Response Agent — generates AI responses using OpenAI and skill fallback."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from app.agents.base import BaseAgent
from app.agents.memory_agent import MemoryContext
from app.models.schemas import ContactInfo, GeneratedResponse
from app.prompts import SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from skill_consumer import SkillAgent


class ResponseAgent(BaseAgent):
    """Generates AI responses using OpenAI and memory context.

    Owns the OpenAI client directly and handles:
    1. Primary response generation via OpenAI
    2. Confidence adjustment from memory boost
    3. Skill Agent fallback when primary confidence is low
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        skill_agent: SkillAgent | None = None,
        confidence_threshold: float = 0.8,
    ):
        super().__init__(name="response")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.skill_agent = skill_agent
        self.threshold = confidence_threshold

    async def initialize(self) -> None:
        self.logger.info("Response agent initialized (model=%s)", self.model)

    async def generate(
        self,
        customer_message: str,
        memory_context: MemoryContext,
        contact_info: ContactInfo | None = None,
    ) -> GeneratedResponse:
        """Generate an AI response with confidence score.

        1. Call OpenAI with context
        2. Apply confidence boost from memory (only if AI confidence >= 0.7)
        3. If below threshold, try Skill Agent fallback
        """
        # Step 1: Primary OpenAI generation
        result = await self._call_openai(
            customer_message=customer_message,
            conversation_history=memory_context.conversation_history,
            relevant_memories=memory_context.global_matches,
            contact_info=contact_info,
        )

        # Step 2: Apply memory-based confidence adjustment
        adjusted_confidence = result.confidence
        if (
            memory_context.adjusted_confidence_boost > 0
            and adjusted_confidence >= 0.7
        ):
            adjusted_confidence = min(
                adjusted_confidence + memory_context.adjusted_confidence_boost,
                1.0,
            )

        self.logger.info(
            "Primary AI confidence=%.2f, adjusted=%.2f",
            result.confidence,
            adjusted_confidence,
        )

        # Step 3: Skill Agent fallback
        if (
            self.skill_agent is not None
            and adjusted_confidence < self.threshold
        ):
            self.logger.info(
                "Primary AI below threshold (confidence=%.2f), trying skill agent",
                adjusted_confidence,
            )
            try:
                skill_result = await self.skill_agent.answer(customer_message)
                if (
                    skill_result.answer_text
                    and skill_result.confidence > adjusted_confidence
                ):
                    result = GeneratedResponse(
                        text=skill_result.answer_text,
                        confidence=skill_result.confidence,
                        reasoning=f"[Skill Agent] {skill_result.reasoning}",
                    )
                    adjusted_confidence = skill_result.confidence
                    self.logger.info(
                        "Skill agent answered with confidence=%.2f, sources=%s",
                        skill_result.confidence,
                        skill_result.sources,
                    )
            except Exception:
                self.logger.exception("Skill agent query failed")

        return GeneratedResponse(
            text=result.text,
            confidence=adjusted_confidence,
            reasoning=result.reasoning,
        )

    async def _call_openai(
        self,
        customer_message: str,
        conversation_history: list[dict],
        relevant_memories: list[dict],
        contact_info: ContactInfo | None = None,
    ) -> GeneratedResponse:
        """Call OpenAI to generate a response with confidence score."""
        user_prompt = build_user_prompt(
            customer_message, conversation_history, relevant_memories, contact_info
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        parsed = json.loads(response.choices[0].message.content)
        return GeneratedResponse(
            text=parsed["response_text"],
            confidence=float(parsed["confidence"]),
            reasoning=parsed.get("reasoning", ""),
        )
