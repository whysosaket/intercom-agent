"""Message Coordinator — buffers rapid consecutive messages per conversation.

When a customer sends multiple messages in quick succession, Intercom fires
separate webhook events for each.  Without coordination the system would
process each message independently and the earlier ones could be ignored.

The coordinator solves this by:
1. Buffering incoming messages per conversation_id.
2. Resetting a short debounce timer every time a new message arrives for
   the same conversation.
3. Once the timer expires (no new messages within the window), it combines
   all buffered messages and forwards the batch to the orchestrator as a
   single unified message.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.models.schemas import ContactInfo

if TYPE_CHECKING:
    from app.agents.orchestrator_agent import OrchestratorAgent

logger = logging.getLogger(__name__)


@dataclass
class _BufferedMessage:
    """A single message waiting in the buffer."""

    body: str
    timestamp: float


@dataclass
class _ConversationBuffer:
    """Per-conversation state used by the coordinator."""

    messages: list[_BufferedMessage] = field(default_factory=list)
    contact_info: ContactInfo | None = None
    user_id: str = ""
    timer_task: asyncio.Task | None = None  # type: ignore[type-arg]


class MessageCoordinator:
    """Buffers rapid messages per conversation and debounces processing.

    Usage::

        coordinator = MessageCoordinator(orchestrator, timeout=3.0)
        # Called from the webhook handler instead of orchestrator directly:
        await coordinator.enqueue(conversation_id, message_body, contact_info, user_id)
    """

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        timeout: float = 3.0,
    ) -> None:
        self._orchestrator = orchestrator
        self._timeout = timeout
        # conversation_id -> buffer
        self._buffers: dict[str, _ConversationBuffer] = {}
        # Per-conversation lock to prevent race conditions
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        conversation_id: str,
        message_body: str,
        contact_info: ContactInfo | None = None,
        user_id: str = "",
    ) -> None:
        """Add a message to the buffer and (re)start the debounce timer."""
        lock = self._get_lock(conversation_id)
        async with lock:
            buf = self._buffers.get(conversation_id)
            if buf is None:
                buf = _ConversationBuffer(contact_info=contact_info, user_id=user_id)
                self._buffers[conversation_id] = buf

            buf.messages.append(
                _BufferedMessage(body=message_body, timestamp=time.monotonic())
            )
            # Always keep the latest contact_info / user_id
            if contact_info:
                buf.contact_info = contact_info
            if user_id:
                buf.user_id = user_id

            # Cancel any pending timer so we restart the debounce window.
            if buf.timer_task is not None and not buf.timer_task.done():
                buf.timer_task.cancel()

            buf.timer_task = asyncio.create_task(
                self._debounce_then_flush(conversation_id)
            )

            logger.info(
                "Buffered message for conversation %s (%d message(s) pending)",
                conversation_id,
                len(buf.messages),
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_lock(self, conversation_id: str) -> asyncio.Lock:
        if conversation_id not in self._locks:
            self._locks[conversation_id] = asyncio.Lock()
        return self._locks[conversation_id]

    async def _debounce_then_flush(self, conversation_id: str) -> None:
        """Wait for the debounce window then flush the buffer."""
        try:
            await asyncio.sleep(self._timeout)
        except asyncio.CancelledError:
            # Timer was reset by a newer message — this is expected.
            return

        await self._flush(conversation_id)

    async def _flush(self, conversation_id: str) -> None:
        """Combine buffered messages and forward to the orchestrator."""
        lock = self._get_lock(conversation_id)
        async with lock:
            buf = self._buffers.pop(conversation_id, None)
            # Also clean up the lock entry to avoid unbounded growth.
            self._locks.pop(conversation_id, None)

        if buf is None or not buf.messages:
            return

        # Build a single unified message from the buffered texts.
        if len(buf.messages) == 1:
            combined_body = buf.messages[0].body
        else:
            combined_body = "\n\n".join(m.body for m in buf.messages)
            logger.info(
                "Combined %d buffered messages for conversation %s",
                len(buf.messages),
                conversation_id,
            )

        await self._orchestrator.handle_incoming_message(
            conversation_id=conversation_id,
            message_body=combined_body,
            contact_info=buf.contact_info,
            user_id=buf.user_id,
        )
