"""Chat UI routes for prompt testing and development."""

import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.chat.session_manager import SessionManager, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])
templates = Jinja2Templates(directory="app/templates")
session_manager = SessionManager()


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Serve the chat testing UI."""
    return templates.TemplateResponse(request, "chat.html")


@router.post("/chat/sessions")
async def create_session(request: Request):
    """Create a new chat session."""
    session = session_manager.create_session()
    return {
        "session_id": session.session_id,
        "conversation_id": session.conversation_id,
        "user_id": session.user_id,
    }


@router.get("/chat/sessions")
async def list_sessions():
    """List active chat sessions."""
    sessions = session_manager.list_sessions()
    return [
        {
            "session_id": s.session_id,
            "message_count": len(s.messages),
        }
        for s in sessions
    ]


@router.websocket("/chat/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat interaction."""
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    orchestrator = websocket.app.state.orchestrator

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "user_message":
                await _handle_user_message(
                    websocket, session, orchestrator, data["content"]
                )

            elif msg_type == "approve":
                await _handle_approve(websocket, session, orchestrator, data)

            elif msg_type == "edit":
                await _handle_edit(websocket, session, orchestrator, data)

            elif msg_type == "reject":
                await _handle_reject(websocket, session, data)

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected for session %s", session_id)


def _find_preceding_user_message(messages: list[ChatMessage], assistant_idx: int) -> str:
    """Walk backward to find the most recent user message before this assistant response."""
    for i in range(assistant_idx - 1, -1, -1):
        if messages[i].role == "user":
            return messages[i].content
    return ""


async def _handle_user_message(websocket, session, orchestrator, user_text):
    """Process a user message through the AI pipeline.

    Routes by confidence just like production:
    - High confidence (>= threshold) → auto-sent
    - Low confidence (< threshold) → pending review with approve/edit/reject
    """
    user_msg = ChatMessage(role="user", content=user_text)
    session.messages.append(user_msg)

    # Search for context (user message is NOT stored yet — deferred until approval/auto-send)
    conv_history = orchestrator.memory.search_conversation_history(
        session.user_id, query=user_text
    )
    global_matches = orchestrator.memory.search_global_catalogue(user_text)

    result = await orchestrator.ai.generate_response(
        customer_message=user_text,
        conversation_history=conv_history,
        relevant_memories=global_matches,
        contact_info=None,
    )

    final_confidence = orchestrator._adjust_confidence(
        result.confidence, global_matches
    )

    # Skill Agent fallback: if primary AI couldn't answer confidently,
    # try the skill documentation for a better answer
    if (
        orchestrator.skill_agent is not None
        and final_confidence < orchestrator.threshold
    ):
        try:
            from app.models.schemas import GeneratedResponse

            skill_result = await orchestrator.skill_agent.answer(user_text)
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
        except Exception:
            logger.exception("Skill agent query failed in chat")

    # Post-process: refine tone/formatting and re-evaluate confidence
    if orchestrator.post_processor is not None and result.text.strip():
        try:
            from app.models.schemas import GeneratedResponse, PostProcessorInput

            pp_input = PostProcessorInput(
                customer_message=user_text,
                generated_response=result.text,
                original_confidence=final_confidence,
                original_reasoning=result.reasoning,
            )
            pp_output = await orchestrator.post_processor.process(pp_input)
            result = GeneratedResponse(
                text=pp_output.refined_text,
                confidence=pp_output.final_confidence,
                reasoning=result.reasoning,
            )
            final_confidence = pp_output.final_confidence
        except Exception:
            logger.exception("Post-processor failed in chat, using original")

    # Route by confidence — same logic as production orchestrator
    if final_confidence >= orchestrator.threshold:
        # High confidence: auto-send
        ai_msg = ChatMessage(
            role="assistant",
            content=result.text,
            confidence=final_confidence,
            reasoning=result.reasoning,
            status="sent",
        )
        session.messages.append(ai_msg)
        # Store both user message and assistant response (deferred from intake)
        orchestrator.memory.store_conversation_turn(
            session.user_id, "user", user_text
        )
        orchestrator.memory.store_conversation_turn(
            session.user_id, "assistant", result.text
        )
        await websocket.send_json(
            {
                "type": "ai_response",
                "content": result.text,
                "confidence": final_confidence,
                "reasoning": result.reasoning,
                "auto_sent": True,
            }
        )
    else:
        # Low confidence: send draft for manual review
        ai_msg = ChatMessage(
            role="assistant",
            content=result.text,
            confidence=final_confidence,
            reasoning=result.reasoning,
            status="pending_review",
        )
        session.messages.append(ai_msg)
        await websocket.send_json(
            {
                "type": "review_request",
                "content": result.text,
                "confidence": final_confidence,
                "reasoning": result.reasoning,
                "message_index": len(session.messages) - 1,
            }
        )


async def _handle_approve(websocket, session, orchestrator, data):
    """Approve a pending response."""
    idx = data.get("message_index", len(session.messages) - 1)
    msg = session.messages[idx]
    msg.status = "sent"
    # Store both user message and assistant response (deferred from intake)
    user_text = _find_preceding_user_message(session.messages, idx)
    if user_text:
        orchestrator.memory.store_conversation_turn(
            session.user_id, "user", user_text
        )
    orchestrator.memory.store_conversation_turn(
        session.user_id, "assistant", msg.content
    )
    # Approved skill-agent responses are validated technical answers —
    # store in global catalogue so future similar questions get answered
    # directly from memory without needing the skill agent again
    if user_text and msg.reasoning.startswith("[Skill Agent]"):
        formatted = (
            f"Chat conversation {session.conversation_id}:\n"
            f"Customer said: {user_text}\n"
            f"Support said: {msg.content}"
        )
        orchestrator.memory.store_global_catalogue_conversation(
            formatted_conversation=formatted,
            conversation_id=session.conversation_id,
        )
        logger.info(
            "Approved skill-agent response stored in global catalogue for session %s",
            session.session_id,
        )
    await websocket.send_json(
        {
            "type": "response_approved",
            "content": msg.content,
            "message_index": idx,
        }
    )


async def _handle_edit(websocket, session, orchestrator, data):
    """Edit and send a modified response."""
    idx = data.get("message_index", len(session.messages) - 1)
    new_text = data["content"]
    msg = session.messages[idx]
    msg.content = new_text
    msg.status = "edited"
    # Store both user message and edited assistant response (deferred from intake)
    user_text = _find_preceding_user_message(session.messages, idx)
    if user_text:
        orchestrator.memory.store_conversation_turn(
            session.user_id, "user", user_text
        )
    orchestrator.memory.store_conversation_turn(
        session.user_id, "assistant", new_text
    )
    # Edited responses are human-curated — store in global catalogue
    if user_text:
        formatted = (
            f"Chat conversation {session.conversation_id}:\n"
            f"Customer said: {user_text}\n"
            f"Support said: {new_text}"
        )
        orchestrator.memory.store_global_catalogue_conversation(
            formatted_conversation=formatted,
            conversation_id=session.conversation_id,
        )
    await websocket.send_json(
        {
            "type": "response_edited",
            "content": new_text,
            "message_index": idx,
        }
    )


async def _handle_reject(websocket, session, data):
    """Reject a pending response."""
    idx = data.get("message_index", len(session.messages) - 1)
    session.messages[idx].status = "rejected"
    await websocket.send_json(
        {
            "type": "response_rejected",
            "message_index": idx,
        }
    )
