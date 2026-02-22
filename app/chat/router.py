"""Chat UI routes for prompt testing and development."""

import logging
import time

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
    """Process a user message through the agent pipeline.

    Routes by confidence just like production:
    - High confidence (>= threshold) -> auto-sent
    - Low confidence (< threshold) -> pending review with approve/edit/reject

    Captures a pipeline_trace with per-step timing and data for the UI.
    """
    user_msg = ChatMessage(role="user", content=user_text)
    session.messages.append(user_msg)

    pipeline_trace: list[dict] = []

    # Step 1: Fetch memory context via Memory Agent
    # (user message is NOT stored yet -- deferred until approval/auto-send)
    t0 = time.monotonic()
    memory_context = await orchestrator.memory_agent.fetch_context(
        session.user_id, user_text
    )
    t1 = time.monotonic()
    pipeline_trace.append({
        "step_number": 1,
        "step_name": "Memory Agent",
        "step_method": "fetch_context",
        "status": "completed",
        "duration_ms": round((t1 - t0) * 1000),
        "summary": f"Found {len(memory_context.conversation_history)} conversation turns, {len(memory_context.global_matches)} global matches",
        "details": {
            "conversation_history_count": len(memory_context.conversation_history),
            "conversation_history": memory_context.conversation_history[:10],
            "global_matches_count": len(memory_context.global_matches),
            "global_matches": memory_context.global_matches[:5],
            "confidence_boost": memory_context.adjusted_confidence_boost,
        },
    })

    # Step 2: Generate response via Response Agent
    t0 = time.monotonic()
    result = await orchestrator.response_agent.generate(
        customer_message=user_text,
        memory_context=memory_context,
        contact_info=None,
    )
    t1 = time.monotonic()
    pre_postprocess_confidence = result.confidence
    pre_postprocess_text = result.text
    pipeline_trace.append({
        "step_number": 2,
        "step_name": "Response Agent",
        "step_method": "generate",
        "status": "completed",
        "duration_ms": round((t1 - t0) * 1000),
        "summary": f"Generated response with {result.confidence:.0%} confidence",
        "details": {
            "model": orchestrator.response_agent.model,
            "initial_confidence": result.confidence,
            "text_preview": result.text[:200],
            "full_text": result.text,
            "reasoning": result.reasoning,
            "skill_agent_used": result.reasoning.startswith("[Skill Agent]"),
        },
    })

    # Step 3: Post-process via PostProcessing Agent
    t0 = time.monotonic()
    result = await orchestrator.postprocessing_agent.process(
        customer_message=user_text,
        generated_response=result,
    )
    t1 = time.monotonic()
    pp_enabled = orchestrator.postprocessing_agent.is_enabled
    pipeline_trace.append({
        "step_number": 3,
        "step_name": "PostProcessing Agent",
        "step_method": "process",
        "status": "completed" if pp_enabled else "skipped",
        "duration_ms": round((t1 - t0) * 1000),
        "summary": (
            f"Confidence {pre_postprocess_confidence:.0%} -> {result.confidence:.0%}"
            if pp_enabled else "Disabled"
        ),
        "details": {
            "enabled": pp_enabled,
            "model": orchestrator.postprocessing_agent.model if pp_enabled else None,
            "confidence_before": pre_postprocess_confidence,
            "confidence_after": result.confidence,
            "confidence_delta": round(result.confidence - pre_postprocess_confidence, 4),
            "text_changed": pre_postprocess_text != result.text,
            "reasoning": result.reasoning,
        },
    })

    final_confidence = result.confidence

    # Step 4: Routing decision
    auto_sent = final_confidence >= orchestrator.threshold
    pipeline_trace.append({
        "step_number": 4,
        "step_name": "Routing Decision",
        "step_method": "threshold_check",
        "status": "completed",
        "duration_ms": 0,
        "summary": "Auto-sent" if auto_sent else "Pending review",
        "details": {
            "threshold": orchestrator.threshold,
            "final_confidence": final_confidence,
            "decision": "auto_sent" if auto_sent else "pending_review",
            "reason": (
                f"Confidence {final_confidence:.0%} >= threshold {orchestrator.threshold:.0%}"
                if auto_sent
                else f"Confidence {final_confidence:.0%} < threshold {orchestrator.threshold:.0%}"
            ),
        },
    })

    # Route by confidence -- same logic as production orchestrator
    if auto_sent:
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
        await orchestrator.memory_agent.store_exchange(
            session.user_id, user_text, result.text
        )
        await websocket.send_json(
            {
                "type": "ai_response",
                "content": result.text,
                "confidence": final_confidence,
                "reasoning": result.reasoning,
                "auto_sent": True,
                "pipeline_trace": pipeline_trace,
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
                "pipeline_trace": pipeline_trace,
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
        await orchestrator.memory_agent.store_exchange(
            session.user_id, user_text, msg.content
        )
    else:
        await orchestrator.memory_agent.store_exchange(
            session.user_id, "", msg.content
        )
    # Approved skill-agent responses are validated technical answers --
    # store in global catalogue so future similar questions get answered
    # directly from memory without needing the skill agent again
    if user_text and msg.reasoning.startswith("[Skill Agent]"):
        await orchestrator.memory_agent.store_to_global_catalogue(
            conversation_id=session.conversation_id,
            customer_message=user_text,
            response_text=msg.content,
            source_label="skill-agent-approved",
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
        await orchestrator.memory_agent.store_exchange(
            session.user_id, user_text, new_text
        )
    else:
        await orchestrator.memory_agent.store_exchange(
            session.user_id, "", new_text
        )
    # Edited responses are human-curated -- store in global catalogue
    if user_text:
        await orchestrator.memory_agent.store_to_global_catalogue(
            conversation_id=session.conversation_id,
            customer_message=user_text,
            response_text=new_text,
            source_label="edited",
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
