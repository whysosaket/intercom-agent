"""Chat UI routes for prompt testing and development."""

import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.chat.session_manager import SessionManager, ChatMessage
from app.chat.trace import TraceCollector
from app.models.schemas import RoutingDecision
from app.utils.trace_utils import safe_serialize_trace

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

    Pipeline: Memory -> PreCheck -> (Route) -> Response -> PostProcessing -> Route

    Three paths based on pre-check:
    - ESCALATE: Immediate pending review (no answer generation)
    - KB_ONLY: Answer from FAQ/memory only (no doc agent fallback)
    - FULL_PIPELINE: Full answer generation with doc agent fallback

    Uses TraceCollector to capture per-call events from all agents for the UI.
    """
    user_msg = ChatMessage(role="user", content=user_text)
    session.messages.append(user_msg)

    trace = TraceCollector()

    # Step 1: Fetch memory context via Memory Agent
    memory_context = await orchestrator.memory_agent.fetch_context(
        session.user_id, user_text, trace=trace
    )

    # Step 2: Pre-check classification (if enabled)
    precheck = None
    if orchestrator.precheck_agent:
        precheck = await orchestrator.precheck_agent.classify(
            customer_message=user_text,
            conversation_history=memory_context.conversation_history,
            global_matches=memory_context.global_matches,
            trace=trace,
        )

        # Path A: Immediate escalation — no answer generation
        if precheck.routing_decision == RoutingDecision.ESCALATE:
            reasoning = f"[Pre-Check Escalation] {precheck.reasoning}"

            # Record routing trace
            with trace.step(
                "Routing Decision",
                "computation",
                input_summary=f"precheck_route=ESCALATE",
            ) as ev:
                ev.output_summary = "Escalated (pending review)"
                ev.details = {
                    "threshold": orchestrator.threshold,
                    "final_confidence": precheck.confidence_hint,
                    "decision": "escalated_by_precheck",
                    "reason": precheck.reasoning,
                }

            pipeline_trace = safe_serialize_trace(trace)
            total_duration_ms = trace.total_duration_ms
            logger.info(
                "Pipeline trace: %d events, %dms total. Labels: %s",
                len(pipeline_trace),
                total_duration_ms,
                [ev.get("label", "?") for ev in pipeline_trace],
            )

            ai_msg = ChatMessage(
                role="assistant",
                content="",
                confidence=precheck.confidence_hint,
                reasoning=reasoning,
                status="pending_review",
            )
            session.messages.append(ai_msg)
            await websocket.send_json(
                {
                    "type": "review_request",
                    "content": "",
                    "confidence": precheck.confidence_hint,
                    "reasoning": reasoning,
                    "message_index": len(session.messages) - 1,
                    "pipeline_trace": pipeline_trace,
                    "total_duration_ms": total_duration_ms,
                }
            )
            return

        # Path B: Greeting — auto-reply without LLM answer generation
        if precheck.routing_decision == RoutingDecision.GREETING:
            greeting_text = precheck.greeting_response or "Hey, how can I help you?"

            with trace.step(
                "Routing Decision",
                "computation",
                input_summary="precheck_route=GREETING",
            ) as ev:
                ev.output_summary = "Greeting auto-reply"
                ev.details = {
                    "decision": "greeting_auto_reply",
                    "greeting_text": greeting_text,
                    "reason": precheck.reasoning,
                }

            pipeline_trace = safe_serialize_trace(trace)
            total_duration_ms = trace.total_duration_ms
            logger.info(
                "Pipeline trace: %d events, %dms total. Labels: %s",
                len(pipeline_trace),
                total_duration_ms,
                [ev.get("label", "?") for ev in pipeline_trace],
            )

            ai_msg = ChatMessage(
                role="assistant",
                content=greeting_text,
                confidence=1.0,
                reasoning="[Greeting] Auto-reply",
                status="sent",
            )
            session.messages.append(ai_msg)
            await orchestrator.memory_agent.store_exchange(
                session.user_id, user_text, greeting_text
            )
            await websocket.send_json(
                {
                    "type": "ai_response",
                    "content": greeting_text,
                    "confidence": 1.0,
                    "reasoning": "[Greeting] Auto-reply",
                    "auto_sent": True,
                    "pipeline_trace": pipeline_trace,
                    "total_duration_ms": total_duration_ms,
                }
            )
            return

        # Path C: Vague issue — ask for details without LLM answer generation
        if precheck.routing_decision == RoutingDecision.CLARIFY_ISSUE:
            clarify_text = (
                precheck.clarify_response
                or "Could you share more details about the issue? "
                   "The exact error message and what you were doing when it occurred would help."
            )

            with trace.step(
                "Routing Decision",
                "computation",
                input_summary="precheck_route=CLARIFY_ISSUE",
            ) as ev:
                ev.output_summary = "Asking for issue details"
                ev.details = {
                    "decision": "clarify_issue",
                    "clarify_text": clarify_text,
                    "reason": precheck.reasoning,
                }

            pipeline_trace = safe_serialize_trace(trace)
            total_duration_ms = trace.total_duration_ms
            logger.info(
                "Pipeline trace: %d events, %dms total. Labels: %s",
                len(pipeline_trace),
                total_duration_ms,
                [ev.get("label", "?") for ev in pipeline_trace],
            )

            ai_msg = ChatMessage(
                role="assistant",
                content=clarify_text,
                confidence=1.0,
                reasoning="[Clarify Issue] Asking for details",
                status="sent",
            )
            session.messages.append(ai_msg)
            await orchestrator.memory_agent.store_exchange(
                session.user_id, user_text, clarify_text
            )
            await websocket.send_json(
                {
                    "type": "ai_response",
                    "content": clarify_text,
                    "confidence": 1.0,
                    "reasoning": "[Clarify Issue] Asking for details",
                    "auto_sent": True,
                    "pipeline_trace": pipeline_trace,
                    "total_duration_ms": total_duration_ms,
                }
            )
            return

    # Step 3: Generate response via Response Agent
    use_doc_fallback = (
        precheck is None
        or precheck.routing_decision == RoutingDecision.FULL_PIPELINE
    )

    result = await orchestrator.response_agent.generate(
        customer_message=user_text,
        memory_context=memory_context,
        contact_info=None,
        trace=trace,
        precheck=precheck,
        use_doc_fallback=use_doc_fallback,
    )
    pre_postprocess_confidence = result.confidence
    pre_postprocess_text = result.text

    # Step 4: Post-process via PostProcessing Agent
    result = await orchestrator.postprocessing_agent.process(
        customer_message=user_text,
        generated_response=result,
        trace=trace,
        conversation_history=memory_context.conversation_history,
    )

    # Step 5: Routing decision — record as a trace event
    final_confidence = result.confidence
    auto_sent = final_confidence >= orchestrator.threshold
    precheck_route = precheck.routing_decision.value if precheck else "no_precheck"
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
            "precheck_route": precheck_route,
            "decision": "auto_sent" if auto_sent else "pending_review",
            "reason": (
                f"Confidence {final_confidence:.0%} >= threshold {orchestrator.threshold:.0%}"
                if auto_sent
                else f"Confidence {final_confidence:.0%} < threshold {orchestrator.threshold:.0%}"
            ),
        }

    # Serialize the trace for the frontend
    pipeline_trace = safe_serialize_trace(trace)
    total_duration_ms = trace.total_duration_ms
    logger.info(
        "Pipeline trace: %d events, %dms total. Labels: %s",
        len(pipeline_trace),
        total_duration_ms,
        [ev.get("label", "?") for ev in pipeline_trace],
    )

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
