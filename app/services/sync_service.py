from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.intercom_client import IntercomClient
    from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """Remove HTML tags from Intercom message bodies."""
    return re.sub(r"<[^>]+>", "", text).strip() if text else ""


class SyncService:
    def __init__(
        self,
        intercom_client: IntercomClient,
        memory_service: MemoryService,
        max_conversations: int = 1000,
        max_messages_per_conversation: int = 5,
        max_conversation_chars: int = 3000,
        data_dir: str = "data",
    ):
        self.intercom = intercom_client
        self.memory = memory_service
        self.max_conversations = max_conversations
        self.max_messages = max_messages_per_conversation
        self.max_chars = max_conversation_chars
        self.data_dir = Path(data_dir)

    async def sync_all_conversations(self) -> dict:
        """Three-phase sync: fetch from Intercom, save locally, ingest into Mem0."""
        # Phase 1: Fetch
        raw_conversations = await self._fetch_all_conversations()

        # Phase 2: Save locally as JSON
        self._save_to_json(raw_conversations)

        # Phase 3: Ingest into Mem0 global catalogue
        return self._ingest_into_mem0(raw_conversations)

    def sync_from_local_json(self, filepath: str | None = None) -> dict:
        """Re-ingest from a previously saved JSON file without hitting Intercom."""
        path = Path(filepath) if filepath else self.data_dir / "intercom_conversations.json"
        if not path.exists():
            raise FileNotFoundError(f"No saved data at {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        conversations = data.get("conversations", [])
        logger.info("Loaded %d conversations from %s", len(conversations), path)
        return self._ingest_into_mem0(conversations)

    # ── Phase 1: Fetch ──

    async def _fetch_all_conversations(self) -> list[dict]:
        """Fetch up to max_conversations from Intercom, fully hydrated."""
        conversations: list[dict] = []
        cursor: str | None = None

        logger.info(
            "Fetching up to %d conversations from Intercom...",
            self.max_conversations,
        )

        while len(conversations) < self.max_conversations:
            page = await self.intercom.list_conversations(
                per_page=20, starting_after=cursor
            )
            summaries = page.get("conversations", [])
            if not summaries:
                break

            for summary in summaries:
                if len(conversations) >= self.max_conversations:
                    break
                conv_id = summary["id"]
                try:
                    full_conv = await self.intercom.get_conversation(conv_id)
                    conversations.append(full_conv)
                except Exception:
                    logger.exception(
                        "Failed to fetch conversation %s, skipping", conv_id
                    )

            pages = page.get("pages", {})
            next_page = pages.get("next")
            if not next_page or not next_page.get("starting_after"):
                break
            cursor = next_page["starting_after"]

            logger.info("Fetched %d conversations so far...", len(conversations))

        logger.info("Total conversations fetched: %d", len(conversations))
        return conversations

    # ── Phase 2: Save ──

    def _save_to_json(self, conversations: list[dict]) -> Path:
        """Save raw conversation data to data/intercom_conversations.json."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.data_dir / "intercom_conversations.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(conversations),
                    "conversations": conversations,
                },
                f,
                indent=2,
                default=str,
            )

        logger.info("Saved %d conversations to %s", len(conversations), filepath)
        return filepath

    # ── Phase 3: Ingest ──

    def _ingest_into_mem0(self, conversations: list[dict]) -> dict:
        """Format each conversation and store in Mem0 global catalogue."""
        ingested = 0
        skipped_oversized = 0
        skipped_empty = 0
        skipped_no_admin_reply = 0
        errors = 0

        for conv in conversations:
            conv_id = conv.get("id", "unknown")
            try:
                messages = self._extract_messages(conv)

                if not messages:
                    skipped_empty += 1
                    continue

                # Skip conversations where no admin/team member actually replied
                has_admin = any(m["role"] == "admin" for m in messages)
                if not has_admin:
                    skipped_no_admin_reply += 1
                    continue

                # Limit to first N messages
                truncated = messages[: self.max_messages]

                # Format into a single string
                formatted = self._format_conversation(truncated, conv_id)

                # Skip if too large
                if len(formatted) > self.max_chars:
                    logger.debug(
                        "Skipping conversation %s: %d chars exceeds limit %d",
                        conv_id,
                        len(formatted),
                        self.max_chars,
                    )
                    skipped_oversized += 1
                    continue

                self.memory.store_global_catalogue_conversation(
                    formatted_conversation=formatted,
                    conversation_id=conv_id,
                )
                ingested += 1

                if ingested % 50 == 0:
                    logger.info("Ingested %d conversations into Mem0...", ingested)

            except Exception:
                logger.exception("Failed to ingest conversation %s", conv_id)
                errors += 1

        summary = {
            "conversations_ingested": ingested,
            "skipped_oversized": skipped_oversized,
            "skipped_empty": skipped_empty,
            "skipped_no_admin_reply": skipped_no_admin_reply,
            "errors": errors,
            "total_fetched": len(conversations),
        }
        logger.info("Ingestion complete: %s", summary)
        return summary

    # ── Helpers ──

    # Part types that may contain real human messages.
    # Bot author messages are filtered separately in _extract_messages.
    # Excludes: channel_and_reply_time_expectation, note, and all system events.
    _ALLOWED_PART_TYPES = frozenset({"comment", "assignment"})

    # Intercom author types that represent customers (not support staff).
    _CUSTOMER_AUTHOR_TYPES = frozenset({"user", "lead"})

    def _extract_messages(self, conv: dict) -> list[dict]:
        """Extract ordered messages from a conversation.

        Only includes real human messages (customers and admins). Filters out:
        - All bot messages (Fin auto-replies, prompts, etc.)
        - Intercom system parts (channel_and_reply_time_expectation, etc.)
        - Internal admin notes
        - System events (language detection, attribute updates, etc.)
        """
        messages: list[dict] = []

        # Initial message from the source (skip if authored by bot)
        source = conv.get("source", {})
        source_body = _strip_html(source.get("body", ""))
        source_author_type = source.get("author", {}).get("type", "")

        if source_body and source_author_type != "bot":
            role = "user" if source_author_type in self._CUSTOMER_AUTHOR_TYPES else "admin"
            messages.append({"role": role, "content": source_body})

        # Conversation parts — only real human messages (comment, assignment)
        parts = conv.get("conversation_parts", {}).get("conversation_parts", [])
        for part in parts:
            if part.get("part_type") not in self._ALLOWED_PART_TYPES:
                continue

            author_type = part.get("author", {}).get("type", "")
            # Skip all bot messages (Fin prompts, auto-replies, etc.)
            if author_type == "bot":
                continue

            body = _strip_html(part.get("body", ""))
            if not body:
                continue

            role = "user" if author_type in self._CUSTOMER_AUTHOR_TYPES else "admin"
            messages.append({"role": role, "content": body})

        return messages

    def _format_conversation(
        self, messages: list[dict], conversation_id: str
    ) -> str:
        """Format messages into a single string with structured turn markers."""
        lines = [f"Intercom conversation {conversation_id}:"]
        for msg in messages:
            prefix = "Customer said" if msg["role"] == "user" else "Support said"
            lines.append(f"{prefix}: {msg['content']}")
        return "\n".join(lines)
