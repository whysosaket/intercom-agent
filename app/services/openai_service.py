import json
import logging

from openai import AsyncOpenAI

from app.models.schemas import ContactInfo, GeneratedResponse
from app.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_response(
        self,
        customer_message: str,
        conversation_history: list[dict],
        relevant_memories: list[dict],
        contact_info: ContactInfo | None = None,
    ) -> GeneratedResponse:
        """Generate a response with confidence score."""
        user_prompt = build_user_prompt(
            customer_message, conversation_history, relevant_memories, contact_info
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"}
        )

        parsed = json.loads(response.choices[0].message.content)
        return GeneratedResponse(
            text=parsed["response_text"],
            confidence=float(parsed["confidence"]),
            reasoning=parsed.get("reasoning", ""),
        )
