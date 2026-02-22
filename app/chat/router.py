"""Chat UI routes for prompt testing and development."""

import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.chat.session_manager import SessionManager, ChatMessage
from app.chat.trace import TraceCollector

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

    Uses TraceCollector to capture per-call events from all agents for the UI.
    """
    user_msg = ChatMessage(role="user", content=user_text)
    session.messages.append(user_msg)

    trace = TraceCollector()

    # Step 1: Fetch memory context via Memory Agent
    memory_context = await orchestrator.memory_agent.fetch_context(
        session.user_id, user_text, trace=trace
    )

    # Step 2: Generate response via Response Agent
    result = await orchestrator.response_agent.generate(
        customer_message=user_text,
        memory_context=memory_context,
        contact_info=None,
        trace=trace,
    )
    pre_postprocess_confidence = result.confidence
    pre_postprocess_text = result.text

    # Step 3: Post-process via PostProcessing Agent
    result = await orchestrator.postprocessing_agent.process(
        customer_message=user_text,
        generated_response=result,
        trace=trace,
    )

    # Step 4: Routing decision — record as a trace event
    final_confidence = result.confidence
    auto_sent = final_confidence >= orchestrator.threshold
    with trace.step(
        "Routing Decision",
        "computation",
        input_summary=f"confidence={final_confidence:.2f}, threshold={orchestrator.threshold:.2f}",
    ) as ev:
        ev.output_summary = "Auto-sent" if auto_sent else "Pending review"
        ev.details = {
            "threshold": orchestrator.threshold,
            "final_confidence": final_confidence,
            "pre_postprocess_confidence": pre_postprocess_confidence,
            "text_changed_in_postprocessing": pre_postprocess_text != result.text,
            "decision": "auto_sent" if auto_sent else "pending_review",
            "reason": (
                f"Confidence {final_confidence:.0%} >= threshold {orchestrator.threshold:.0%}"
                if auto_sent
                else f"Confidence {final_confidence:.0%} < threshold {orchestrator.threshold:.0%}"
            ),
        }

    # Serialize the trace for the frontend
    pipeline_trace = trace.serialize()
    total_duration_ms = trace.total_duration_ms

    # Route by confidence — same logic as production orchestrator
    if auto_sent:
        ai_msg = ChatMessage(
            role="assistant",
            content=result.text,
            confidence=final_confidence,
            reasoning=result.reasoning,
            status="sent",
        )
        session.messages.append(ai_msg)
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
                "total_duration_ms": total_duration_ms,
            }
        )
    else:
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
                "total_duration_ms": total_duration_ms,
            }
        )


async def _handle_approve(websocket, session, orchestrator, data):
    """Approve a pending response."""
    idx = data.get("message_index", len(session.messages) - 1)
    msg = session.messages[idx]
    msg.status = "sent"
    user_text = _find_preceding_user_message(session.messages, idx)
    if user_text:
        await orchestrator.memory_agent.store_exchange(
            session.user_id, user_text, msg.content
        )
    else:
        await orchestrator.memory_agent.store_exchange(
            session.user_id, "", msg.content
        )
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
    user_text = _find_preceding_user_message(session.messages, idx)
    if user_text:
        await orchestrator.memory_agent.store_exchange(
            session.user_id, user_text, new_text
        )
    else:
        await orchestrator.memory_agent.store_exchange(
            session.user_id, "", new_text
        )
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
