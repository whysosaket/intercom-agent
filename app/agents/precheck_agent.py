"""Pre-Check Agent — fast classifier that routes messages before answer generation.

Runs a lightweight LLM call to determine:
- Whether the question can be answered from KB at all
- Whether it needs human escalation immediately
- Whether it's technical (needs doc agent) or non-technical (KB only)
- Follow-up detection and answerability assessment

This avoids expensive answer-generation LLM calls for messages that
should be escalated, and prevents unnecessary doc-agent invocations
for non-technical questions.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from app.agents.base import BaseAgent
from app.company import CompanyConfig, company_config
from app.models.schemas import PreCheckResult, QuestionType, RoutingDecision

if TYPE_CHECKING:
    from app.chat.trace import TraceCollector


def build_precheck_system_prompt(config: CompanyConfig | None = None) -> str:
    """Build the pre-check classifier system prompt."""
    cfg = config or company_config

    faq_questions = "\n".join(f"- {e.question}" for e in cfg.faq_entries)

    product_features_block = "\n".join(f"- {f}" for f in cfg.product_features)
    sub_products_block = "\n".join(f"- {p}" for p in cfg.sub_products)

    return f"""\
You are a fast message classifier for {cfg.name} customer support. Your ONLY job is to classify the incoming customer message and decide how it should be routed. You do NOT generate answers.

---

## AVAILABLE KNOWLEDGE

The support system has these FAQ questions:
{faq_questions}

Product features:
{product_features_block}

Sub-products:
{sub_products_block}

---

## CLASSIFICATION RULES

### Step 1: Detect greetings
If the message is ONLY a greeting with no question or request (e.g., "hey", "hi", "hello", "good morning", "what's up", "yo"), set routing_decision="greeting" and greeting_response to a short, natural greeting like "Hey, how can I help you?" or "Hi there, how can I help?". Do NOT escalate greetings. Confidence_hint should be 1.0 for greetings.

### Step 2: Detect vague issues (no specific details)
If the user reports an error, issue, or problem but does NOT share specific details, set routing_decision="clarify_issue" and clarify_response to a concise message asking them for more information. Do NOT escalate vague issues -- ask for details first.

This applies when the message matches patterns like:
- "I'm getting an error" / "there's an error" / "something is broken"
- "it's not working" / "it doesn't work" / "I have an issue"
- "I'm having trouble" / "I'm facing a problem" / "something went wrong"
- "I need help with an issue" / "I ran into a problem"
- Any report of an issue/error/bug where the user does NOT include: the error message text, steps they took, what they expected vs what happened, or relevant code/config.

The clarify_response should be natural and direct, for example:
- "Could you share the exact error message you're seeing?"
- "What were you trying to do when this happened? Any error messages or screenshots would help."
- "Could you share more details? The exact error message and what you were doing when it occurred would help us help you faster."

Do NOT use this for messages that already include specific error details, code snippets, or clear descriptions of what went wrong -- those should proceed to classification as normal.

Confidence_hint should be 1.0 for clarify_issue since we're confidently asking for more info.

### Step 3: Detect if user wants a human
If the message matches any of these patterns (case-insensitive), set requires_human_intervention=true and routing_decision="escalate":
- "talk to a human" / "speak to a human" / "speak with a person"
- "transfer me" / "connect me to an agent" / "connect me to support"
- "I want a real person" / "can I talk to someone"
- "escalate this" / "get me a manager"
- "this bot is not helping" / "I need human help"
- "let me speak to someone" / "real human please"

### Step 4: Detect follow-ups
If the message references a previous conversation turn ("how soon?", "what about...", "and the pricing?", uses pronouns like "it", "that", "this" referring to earlier topics), set is_followup=true and followup_context to a brief description.

For follow-ups, check: does the conversation history contain the SPECIFIC information needed to answer? A topic being mentioned does not mean the specific answer exists. Example: "We will roll out X soon" + user asks "how soon?" = topic exists but specific date does NOT. Set answerable_from_context=false.

### Step 5: Assess answerability
Can this question be answered from the FAQ list, product context, or conversation history provided?

IMPORTANT — FAQ MATCH TAKES PRIORITY: If the customer's question matches or is closely related to ANY of the FAQ questions listed above, it is answerable. Do NOT escalate it. Route it to "kb_only" or "full_pipeline" so the answer agent can provide the FAQ answer. For example, questions about deleting accounts, deleting memories, pricing, exporting data, or user IDs all have FAQ entries and must NOT be escalated.

Set answerable_from_context=false and routing_decision="escalate" ONLY when ALL of these are true:
1. The question does NOT match or closely relate to any FAQ entry above
2. AND one of these conditions applies:
   - Question asks for timelines, release dates, or ETAs
   - Question asks for account-specific data that is NOT covered by FAQ (e.g., specific usage numbers, billing amounts)
   - Question asks for internal decisions or roadmap details
   - Question is off-topic (not related to {cfg.name} at all)
   - Question is a follow-up but the specific answer is not in context
   - Question requires information not present in any provided source

### Step 6: Classify question type
- TECHNICAL: Questions about API usage, code, integration, SDK, setup, configuration, implementation, MCP, debugging, errors, technical features. ALSO includes questions asking HOW to use product features (e.g., "how do I use graph memories?", "how do I add memories?", "how to set up OpenMemory?") — these need documentation.
- NON_TECHNICAL: Questions ONLY about pricing, account management, billing, account deletion, data export. Simple "what is X?" questions where the answer is fully covered by the product context above.

IMPORTANT: If the question is about a product feature and could require implementation details, code examples, or setup steps, classify as TECHNICAL even if it sounds like a general question. For example "how does graph memory work?" is TECHNICAL because the answer requires documentation content.

### Step 7: Decide routing
- "greeting": Message is just a greeting with no question. Auto-reply with a friendly greeting.
- "clarify_issue": User reports an error/issue/problem but without specific details. Ask for more information before proceeding.
- "escalate": User asked for human, OR question is unanswerable from provided context (timelines, account-specific, off-topic, unsupported follow-up)
- "kb_only": Question is NON-TECHNICAL and answerable from FAQ or product context. No need for documentation search.
- "full_pipeline": Question is TECHNICAL or product-feature related and potentially answerable. May need documentation search if FAQ/memory don't cover it.

---

## CONFIDENCE HINT

Provide a rough confidence estimate for the downstream answer generator:
- 0.9-1.0 if the question directly matches an FAQ entry
- 0.7-0.8 if answerable from product context
- 0.0 if escalating

---

## OUTPUT FORMAT

Return ONLY valid JSON:
{{
    "intent_category": "greeting|direct_faq_match|supported_by_context|not_supported|off_topic|user_asked_for_human",
    "question_type": "technical|non_technical",
    "routing_decision": "greeting|clarify_issue|escalate|kb_only|full_pipeline",
    "requires_human_intervention": false,
    "is_followup": false,
    "followup_context": "",
    "answerable_from_context": true,
    "reasoning": "brief justification",
    "confidence_hint": 0.0,
    "greeting_response": "",
    "clarify_response": ""
}}"""


class PreCheckAgent(BaseAgent):
    """Fast message classifier that routes before answer generation.

    Uses a lightweight LLM call to classify intent, detect follow-ups,
    assess answerability, and decide routing (escalate / kb_only / full_pipeline).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-mini",
        company_cfg: CompanyConfig | None = None,
    ):
        super().__init__(name="precheck")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._system_prompt = build_precheck_system_prompt(company_cfg)

    async def initialize(self) -> None:
        self.logger.info("Pre-check agent initialized (model=%s)", self.model)

    async def classify(
        self,
        customer_message: str,
        conversation_history: list[dict] | None = None,
        global_matches: list[dict] | None = None,
        trace: TraceCollector | None = None,
    ) -> PreCheckResult:
        """Classify a customer message and decide routing.

        Parameters
        ----------
        customer_message:
            The customer's current message.
        conversation_history:
            Recent conversation turns from Mem0 (may be empty).
        global_matches:
            Matching KB entries from Mem0 global catalogue (may be empty).
        trace:
            Optional trace collector for the pipeline UI.
        """
        user_prompt = self._build_user_prompt(
            customer_message, conversation_history or [], global_matches or []
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        self.logger.debug("[Pre-Check] LLM response: %s", raw)
        parsed = json.loads(raw)

        result = PreCheckResult(
            question_type=QuestionType(parsed.get("question_type", "technical")),
            routing_decision=RoutingDecision(parsed.get("routing_decision", "full_pipeline")),
            requires_human_intervention=parsed.get("requires_human_intervention", False),
            is_followup=parsed.get("is_followup", False),
            followup_context=parsed.get("followup_context", ""),
            answerable_from_context=parsed.get("answerable_from_context", True),
            reasoning=parsed.get("reasoning", ""),
            confidence_hint=float(parsed.get("confidence_hint", 0.0)),
            greeting_response=parsed.get("greeting_response", ""),
            clarify_response=parsed.get("clarify_response", ""),
        )

        if trace:
            with trace.step(
                f"Pre-Check Agent ({self.model})",
                "llm_call",
                input_summary=f"model={self.model}, message_len={len(customer_message)} chars",
            ) as ev:
                ev.output_summary = (
                    f"route={result.routing_decision.value}, "
                    f"type={result.question_type.value}, "
                    f"human={result.requires_human_intervention}"
                )
                ev.details = {
                    "model": self.model,
                    "intent_category": parsed.get("intent_category", ""),
                    "question_type": result.question_type.value,
                    "routing_decision": result.routing_decision.value,
                    "requires_human_intervention": result.requires_human_intervention,
                    "is_followup": result.is_followup,
                    "followup_context": result.followup_context,
                    "answerable_from_context": result.answerable_from_context,
                    "confidence_hint": result.confidence_hint,
                    "reasoning": result.reasoning,
                    "raw_response": raw[:500],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens if response.usage else None,
                    },
                }

        self.logger.info(
            "Pre-check: route=%s, type=%s, human=%s, followup=%s",
            result.routing_decision.value,
            result.question_type.value,
            result.requires_human_intervention,
            result.is_followup,
        )

        return result

    @staticmethod
    def _build_user_prompt(
        customer_message: str,
        conversation_history: list[dict],
        global_matches: list[dict],
    ) -> str:
        """Build the user prompt with context for classification."""
        parts: list[str] = []

        if conversation_history:
            parts.append("## Recent Conversation History\n")
            for mem in conversation_history:
                parts.append(mem.get("memory", ""))
            parts.append("\n---\n")

        if global_matches:
            parts.append("## Relevant Knowledge Base Matches\n")
            for mem in global_matches:
                score = mem.get("score", 0)
                parts.append(f"[relevance: {score:.2f}] {mem.get('memory', '')}")
            parts.append("\n---\n")

        parts.append(f"## Customer Message\n\n{customer_message}")

        return "\n".join(parts)
