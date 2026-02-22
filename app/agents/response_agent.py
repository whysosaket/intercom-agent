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
    from app.chat.trace import TraceCollector
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
        model: str = "gpt-5-mini",
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
        trace: TraceCollector | None = None,
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
            trace=trace,
        )

        # Step 2: Apply memory-based confidence adjustment
        raw_confidence = result.confidence
        adjusted_confidence = result.confidence
        if (
            memory_context.adjusted_confidence_boost > 0
            and adjusted_confidence >= 0.7
        ):
            adjusted_confidence = min(
                adjusted_confidence + memory_context.adjusted_confidence_boost,
                1.0,
            )

        if trace:
            with trace.step(
                "Memory confidence adjustment",
                "computation",
                input_summary=f"raw={raw_confidence:.2f}, boost={memory_context.adjusted_confidence_boost}",
            ) as ev:
                applied = adjusted_confidence != raw_confidence
                ev.output_summary = (
                    f"{raw_confidence:.2f} -> {adjusted_confidence:.2f}"
                    if applied else f"no change ({raw_confidence:.2f}, boost not applied)"
                )
                ev.details = {
                    "raw_confidence": raw_confidence,
                    "boost": memory_context.adjusted_confidence_boost,
                    "adjusted_confidence": adjusted_confidence,
                    "boost_applied": applied,
                }

        self.logger.info(
            "Primary AI confidence=%.2f, adjusted=%.2f",
            result.confidence,
            adjusted_confidence,
        )

        # Step 3: Skill Agent fallback
        # Only skip fallback if the user explicitly asked for a human agent.
        # When answerable_from_context is false, it just means the primary
        # model's FAQ/memory didn't have the answer — the skill/doc agent
        # can still search documentation and find it.
        skip_fallback = result.requires_human_intervention
        if (
            self.skill_agent is not None
            and adjusted_confidence < self.threshold
            and not skip_fallback
        ):
            self.logger.info(
                "Primary AI below threshold (confidence=%.2f), trying skill agent",
                adjusted_confidence,
            )
            try:
                if trace:
                    with trace.step(
                        "Skill/Doc Agent fallback",
                        "agent_call",
                        input_summary=f"confidence {adjusted_confidence:.2f} < threshold {self.threshold:.2f}",
                    ) as ev:
                        skill_result = await self.skill_agent.answer(
                            customer_message, trace=trace
                        )
                        used = bool(
                            skill_result.answer_text
                            and skill_result.confidence > adjusted_confidence
                        )
                        ev.output_summary = (
                            f"confidence={skill_result.confidence:.2f}, used={used}"
                        )
                        ev.details = {
                            "skill_confidence": skill_result.confidence,
                            "skill_reasoning": skill_result.reasoning,
                            "skill_sources": skill_result.sources,
                            "used_skill_response": used,
                        }
                        if used:
                            result = GeneratedResponse(
                                text=skill_result.answer_text,
                                confidence=skill_result.confidence,
                                reasoning=f"[Skill Agent] {skill_result.reasoning}",
                                is_followup=result.is_followup,
                                followup_context=result.followup_context,
                                answerable_from_context=True,
                                requires_human_intervention=False,
                            )
                            adjusted_confidence = skill_result.confidence
                else:
                    skill_result = await self.skill_agent.answer(customer_message)
                    if (
                        skill_result.answer_text
                        and skill_result.confidence > adjusted_confidence
                    ):
                        result = GeneratedResponse(
                            text=skill_result.answer_text,
                            confidence=skill_result.confidence,
                            reasoning=f"[Skill Agent] {skill_result.reasoning}",
                            is_followup=result.is_followup,
                            followup_context=result.followup_context,
                            answerable_from_context=True,
                            requires_human_intervention=False,
                        )
                        adjusted_confidence = skill_result.confidence
                        self.logger.info(
                            "Skill agent answered with confidence=%.2f, sources=%s",
                            skill_result.confidence,
                            skill_result.sources,
                        )
            except Exception:
                self.logger.exception("Skill agent query failed")
        elif trace and self.skill_agent is not None:
            if skip_fallback:
                skip_reason = "skipped (user requested human intervention)"
                skip_input = f"requires_human={result.requires_human_intervention}"
            else:
                skip_reason = "skipped (confidence above threshold)"
                skip_input = f"confidence {adjusted_confidence:.2f} >= threshold {self.threshold:.2f}"
            with trace.step(
                "Skill/Doc Agent fallback",
                "agent_call",
                input_summary=skip_input,
            ) as ev:
                ev.status = "skipped"
                ev.output_summary = skip_reason

        return GeneratedResponse(
            text=result.text,
            confidence=adjusted_confidence,
            reasoning=result.reasoning,
            requires_human_intervention=result.requires_human_intervention,
            is_followup=result.is_followup,
            followup_context=result.followup_context,
            answerable_from_context=result.answerable_from_context,
        )

    async def _call_openai(
        self,
        customer_message: str,
        conversation_history: list[dict],
        relevant_memories: list[dict],
        contact_info: ContactInfo | None = None,
        trace: TraceCollector | None = None,
    ) -> GeneratedResponse:
        """Call OpenAI to generate a response with confidence score."""
        user_prompt = build_user_prompt(
            customer_message, conversation_history, relevant_memories, contact_info
        )

        if trace:
            with trace.step(
                f"OpenAI LLM call ({self.model})",
                "llm_call",
                input_summary=f"model={self.model}, prompt_len={len(user_prompt)} chars",
            ) as ev:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content
                self.logger.debug("[Primary Generation] LLM response: %s", raw)
                parsed = json.loads(raw)
                ev.output_summary = f"confidence={parsed['confidence']}"
                ev.details = {
                    "model": self.model,
                    "prompt_length": len(user_prompt),
                    "raw_response": raw[:500],
                    "confidence": parsed["confidence"],
                    "reasoning": parsed.get("reasoning", ""),
                    "response_preview": parsed["response_text"][:200],
                    "requires_human_intervention": parsed.get("requires_human_intervention", False),
                    "is_followup": parsed.get("is_followup", False),
                    "followup_context": parsed.get("followup_context", ""),
                    "answerable_from_context": parsed.get("answerable_from_context", True),
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens if response.usage else None,
                    },
                }
                return GeneratedResponse(
                    text=parsed["response_text"],
                    confidence=float(parsed["confidence"]),
                    reasoning=parsed.get("reasoning", ""),
                    requires_human_intervention=parsed.get("requires_human_intervention", False),
                    is_followup=parsed.get("is_followup", False),
                    followup_context=parsed.get("followup_context", ""),
                    answerable_from_context=parsed.get("answerable_from_context", True),
                )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        self.logger.debug("[Primary Generation] LLM response: %s", raw)
        parsed = json.loads(raw)
        return GeneratedResponse(
            text=parsed["response_text"],
            confidence=float(parsed["confidence"]),
            reasoning=parsed.get("reasoning", ""),
            requires_human_intervention=parsed.get("requires_human_intervention", False),
            is_followup=parsed.get("is_followup", False),
            followup_context=parsed.get("followup_context", ""),
            answerable_from_context=parsed.get("answerable_from_context", True),
        )
