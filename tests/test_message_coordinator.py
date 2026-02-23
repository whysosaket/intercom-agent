"""Tests for the MessageCoordinator debounce-and-combine logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import ContactInfo
from app.services.message_coordinator import MessageCoordinator


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.handle_incoming_message = AsyncMock()
    return orch


@pytest.fixture
def contact():
    return ContactInfo(id="c1", name="Alice", email="alice@example.com")


# ------------------------------------------------------------------
# Single message: should be forwarded after the timeout
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_message_forwarded(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.1)
    await coord.enqueue("conv1", "Hello", contact, "alice@example.com")

    # Wait for the debounce timer to fire
    await asyncio.sleep(0.25)

    mock_orchestrator.handle_incoming_message.assert_called_once_with(
        conversation_id="conv1",
        message_body="Hello",
        contact_info=contact,
        user_id="alice@example.com",
    )


# ------------------------------------------------------------------
# Two rapid messages: should be combined into one call
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rapid_messages_combined(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.2)

    await coord.enqueue("conv1", "First message", contact, "alice@example.com")
    await asyncio.sleep(0.05)  # well within the debounce window
    await coord.enqueue("conv1", "Second message", contact, "alice@example.com")

    # Wait for debounce
    await asyncio.sleep(0.4)

    mock_orchestrator.handle_incoming_message.assert_called_once()
    call_kwargs = mock_orchestrator.handle_incoming_message.call_args.kwargs
    assert call_kwargs["conversation_id"] == "conv1"
    # Both messages should appear in the combined body
    assert "First message" in call_kwargs["message_body"]
    assert "Second message" in call_kwargs["message_body"]


# ------------------------------------------------------------------
# Three rapid messages combined
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_rapid_messages_combined(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.2)

    await coord.enqueue("conv1", "Msg 1", contact, "alice@example.com")
    await asyncio.sleep(0.05)
    await coord.enqueue("conv1", "Msg 2", contact, "alice@example.com")
    await asyncio.sleep(0.05)
    await coord.enqueue("conv1", "Msg 3", contact, "alice@example.com")

    await asyncio.sleep(0.4)

    mock_orchestrator.handle_incoming_message.assert_called_once()
    body = mock_orchestrator.handle_incoming_message.call_args.kwargs["message_body"]
    assert "Msg 1" in body
    assert "Msg 2" in body
    assert "Msg 3" in body


# ------------------------------------------------------------------
# Messages for different conversations are independent
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_conversations_independent(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.15)

    contact2 = ContactInfo(id="c2", name="Bob", email="bob@example.com")

    await coord.enqueue("conv1", "Alice says hi", contact, "alice@example.com")
    await coord.enqueue("conv2", "Bob says hi", contact2, "bob@example.com")

    await asyncio.sleep(0.35)

    assert mock_orchestrator.handle_incoming_message.call_count == 2

    calls = {
        c.kwargs["conversation_id"]: c.kwargs
        for c in mock_orchestrator.handle_incoming_message.call_args_list
    }
    assert calls["conv1"]["message_body"] == "Alice says hi"
    assert calls["conv2"]["message_body"] == "Bob says hi"


# ------------------------------------------------------------------
# Messages separated by more than timeout are processed separately
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spaced_messages_processed_separately(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.1)

    await coord.enqueue("conv1", "First", contact, "alice@example.com")
    await asyncio.sleep(0.25)  # First flush should have happened

    await coord.enqueue("conv1", "Second", contact, "alice@example.com")
    await asyncio.sleep(0.25)  # Second flush

    assert mock_orchestrator.handle_incoming_message.call_count == 2

    first_call = mock_orchestrator.handle_incoming_message.call_args_list[0].kwargs
    second_call = mock_orchestrator.handle_incoming_message.call_args_list[1].kwargs
    assert first_call["message_body"] == "First"
    assert second_call["message_body"] == "Second"


# ------------------------------------------------------------------
# Debounce resets when new message arrives within window
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debounce_resets_on_new_message(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.2)

    await coord.enqueue("conv1", "Msg A", contact, "alice@example.com")
    await asyncio.sleep(0.15)  # Almost expired
    # Second message should reset the timer
    await coord.enqueue("conv1", "Msg B", contact, "alice@example.com")

    # At this point, 0.15s have passed since first msg.
    # The timer was reset, so it shouldn't fire for another 0.2s.
    await asyncio.sleep(0.1)
    # Should not have been called yet (only 0.1s since reset)
    mock_orchestrator.handle_incoming_message.assert_not_called()

    # Wait for remaining time + margin
    await asyncio.sleep(0.2)
    mock_orchestrator.handle_incoming_message.assert_called_once()
    body = mock_orchestrator.handle_incoming_message.call_args.kwargs["message_body"]
    assert "Msg A" in body
    assert "Msg B" in body


# ------------------------------------------------------------------
# Message order is preserved in combined body
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_order_preserved(mock_orchestrator, contact):
    coord = MessageCoordinator(mock_orchestrator, timeout=0.15)

    await coord.enqueue("conv1", "First", contact, "alice@example.com")
    await asyncio.sleep(0.02)
    await coord.enqueue("conv1", "Second", contact, "alice@example.com")
    await asyncio.sleep(0.02)
    await coord.enqueue("conv1", "Third", contact, "alice@example.com")

    await asyncio.sleep(0.3)

    body = mock_orchestrator.handle_incoming_message.call_args.kwargs["message_body"]
    first_pos = body.index("First")
    second_pos = body.index("Second")
    third_pos = body.index("Third")
    assert first_pos < second_pos < third_pos
