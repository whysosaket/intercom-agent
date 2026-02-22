"""
Centralized prompt templates for AI response generation.

Edit prompt.py to tune the system prompt; this module builds the user message
and re-exports SYSTEM_PROMPT for callers.
"""

from __future__ import annotations

from app.prompt import SYSTEM_PROMPT


def build_user_prompt(
    customer_message: str,
    conversation_history: list[dict],
    relevant_memories: list[dict],
    contact_info=None,
) -> str:
    """Build the user prompt from all context pieces.

    Args:
        customer_message: The customer's current message.
        conversation_history: Recent conversation turns from Mem0.
        relevant_memories: Matching knowledge base entries from Mem0.
        contact_info: Optional ContactInfo with name/email.
    """
    parts: list[str] = []

    if contact_info and contact_info.name:
        parts.append(f"Customer: {contact_info.name} ({contact_info.email})")

    if conversation_history:
        parts.append("--- Previous conversation turns ---")
        for mem in conversation_history:
            parts.append(mem.get("memory", ""))

    if relevant_memories:
        parts.append("--- Relevant knowledge base entries ---")
        for mem in relevant_memories:
            score = mem.get("score", 0)
            parts.append(f"[relevance: {score:.2f}] {mem.get('memory', '')}")

    parts.append("--- Customer's current message ---")
    parts.append(customer_message)

    return "\n\n".join(parts)
