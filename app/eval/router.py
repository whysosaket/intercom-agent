"""Eval mode routes — fetch unanswered Intercom conversations, generate
candidate responses, review/edit/approve, and send back via Intercom."""

import asyncio
import json as json_mod
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.chat.trace import TraceCollector
from app.models.schemas import RoutingDecision
from app.services.sync_service import extract_messages
from app.utils.trace_utils import safe_serialize_trace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval", tags=["eval"])
templates = Jinja2Templates(directory="app/templates")


# ── Request / Response models ──


class GenerateRequest(BaseModel):
    conversation_id: str
    customer_message: str
    num_candidates: int = 2


class SendRequest(BaseModel):
    conversation_id: str
    response_text: str
    customer_message: str = ""
    user_id: str = ""


class GenerateAllItem(BaseModel):
    conversation_id: str
    customer_message: str


class GenerateAllRequest(BaseModel):
    conversations: list[GenerateAllItem]
    num_candidates: int = 1


# ── Routes ──


@router.get("", response_class=HTMLResponse)
async def eval_page(request: Request):
    """Serve the eval mode UI."""
    return templates.TemplateResponse(request, "eval.html")


def _get_intercom_orchestrator(request: Request):
    """Return the non-mock orchestrator that has a real Intercom HTTP client.

    Falls back to the main orchestrator if no dedicated one exists.
    """
    intercom_orch = getattr(request.app.state, "intercom_orchestrator", None)
    if intercom_orch is not None:
        return intercom_orch
    return request.app.state.orchestrator


@router.post("/conversations")
async def fetch_conversations(request: Request):
    """Fetch recent Intercom conversations where no human admin has replied."""
    orchestrator = _get_intercom_orchestrator(request)

    if orchestrator is None or orchestrator._http_client is None:
        return {
            "conversations": [],
            "message": "Intercom API not available (no access token configured).",
        }

    try:
        conversations: list[dict[str, Any]] = []
        cursor: str | None = None
        # Fetch up to 3 pages (60 conversations) to find enough unanswered ones
        max_pages = 3
        target = 20

        for _ in range(max_pages):
            if len(conversations) >= target:
                break

            page = await orchestrator.list_conversations(
                per_page=20, starting_after=cursor
            )
            summaries = page.get("conversations", [])
            if not summaries:
                break

            for summary in summaries:
                if len(conversations) >= target:
                    break
                conv_id = summary.get("id")
                if not conv_id:
                    continue

                try:
                    full_conv = await orchestrator.get_conversation(conv_id)
                    messages = extract_messages(full_conv)

                    if not messages:
                        continue

                    # Only keep conversations with NO admin reply
                    has_admin = any(m["role"] == "admin" for m in messages)
                    if has_admin:
                        continue

                    # Extract contact info from source
                    source = full_conv.get("source", {})
                    author = source.get("author", {})
                    contact = {
                        "name": author.get("name", ""),
                        "email": author.get("email", ""),
                        "id": author.get("id", ""),
                    }

                    conversations.append({
                        "conversation_id": conv_id,
                        "contact": contact,
                        "messages": messages,
                        "created_at": full_conv.get("created_at", ""),
                        "updated_at": full_conv.get("updated_at", ""),
                    })

                except Exception:
                    logger.exception(
                        "Failed to fetch conversation %s, skipping", conv_id
                    )

            pages_meta = page.get("pages", {})
            next_page = pages_meta.get("next")
            if not next_page or not next_page.get("starting_after"):
                break
            cursor = next_page["starting_after"]

        logger.info(
            "Eval: found %d unanswered conversations", len(conversations)
        )
        return {"conversations": conversations}

    except Exception:
        logger.exception("Failed to fetch conversations for eval")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


async def _generate_for_conversation(
    orchestrator,
    conversation_id: str,
    customer_message: str,
    num_candidates: int,
) -> dict:
    """Core generation logic — run the pipeline N times for one conversation.

    Returns {"conversation_id": ..., "candidates": [...]}.
    """
    candidates = []
    num = max(1, min(num_candidates, 5))
    user_id = conversation_id

    for i in range(num):
        trace = TraceCollector()

        try:
            memory_context = await orchestrator.memory_agent.fetch_context(
                user_id, customer_message, trace=trace
            )

            # Pre-check classification (if enabled)
            precheck = None
            if orchestrator.precheck_agent:
                precheck = await orchestrator.precheck_agent.classify(
                    customer_message=customer_message,
                    conversation_history=memory_context.conversation_history,
                    global_matches=memory_context.global_matches,
                    trace=trace,
                )

                # If pre-check escalates, record as a low-confidence candidate
                if precheck.routing_decision == RoutingDecision.ESCALATE:
                    with trace.step(
                        "Routing Decision", "computation",
                        input_summary="precheck_route=ESCALATE",
                    ) as ev:
                        ev.output_summary = "Escalated by pre-check"
                        ev.details = {
                            "decision": "escalated_by_precheck",
                            "reason": precheck.reasoning,
                        }

                    candidates.append({
                        "index": i,
                        "text": "",
                        "confidence": precheck.confidence_hint,
                        "reasoning": f"[Pre-Check Escalation] {precheck.reasoning}",
                        "pipeline_trace": safe_serialize_trace(trace),
                        "total_duration_ms": trace.total_duration_ms,
                    })
                    continue

                # If pre-check detects a greeting, record as a high-confidence auto-reply
                if precheck.routing_decision == RoutingDecision.GREETING:
                    greeting_text = precheck.greeting_response or "Hey, how can I help you?"
                    with trace.step(
                        "Routing Decision", "computation",
                        input_summary="precheck_route=GREETING",
                    ) as ev:
                        ev.output_summary = "Greeting auto-reply"
                        ev.details = {
                            "decision": "greeting_auto_reply",
                            "greeting_text": greeting_text,
                            "reason": precheck.reasoning,
                        }

                    candidates.append({
                        "index": i,
                        "text": greeting_text,
                        "confidence": 1.0,
                        "reasoning": "[Greeting] Auto-reply",
                        "pipeline_trace": safe_serialize_trace(trace),
                        "total_duration_ms": trace.total_duration_ms,
                    })
                    continue

                # If pre-check detects a vague issue, ask for details
                if precheck.routing_decision == RoutingDecision.CLARIFY_ISSUE:
                    clarify_text = (
                        precheck.clarify_response
                        or "Could you share more details about the issue? "
                           "The exact error message and what you were doing when it occurred would help."
                    )
                    with trace.step(
                        "Routing Decision", "computation",
                        input_summary="precheck_route=CLARIFY_ISSUE",
                    ) as ev:
                        ev.output_summary = "Asking for issue details"
                        ev.details = {
                            "decision": "clarify_issue",
                            "clarify_text": clarify_text,
                            "reason": precheck.reasoning,
                        }

                    candidates.append({
                        "index": i,
                        "text": clarify_text,
                        "confidence": 1.0,
                        "reasoning": "[Clarify Issue] Asking for details",
                        "pipeline_trace": safe_serialize_trace(trace),
                        "total_duration_ms": trace.total_duration_ms,
                    })
                    continue

            use_doc_fallback = (
                precheck is None
                or precheck.routing_decision == RoutingDecision.FULL_PIPELINE
            )

            result = await orchestrator.response_agent.generate(
                customer_message=customer_message,
                memory_context=memory_context,
                contact_info=None,
                trace=trace,
                precheck=precheck,
                use_doc_fallback=use_doc_fallback,
            )
            pre_postprocess_confidence = result.confidence

            result = await orchestrator.postprocessing_agent.process(
                customer_message=customer_message,
                generated_response=result,
                trace=trace,
                conversation_history=memory_context.conversation_history,
            )

            final_confidence = result.confidence
            auto_sent = final_confidence >= orchestrator.threshold
            precheck_route = precheck.routing_decision.value if precheck else "no_precheck"
            with trace.step(
                "Routing Decision",
                "computation",
                input_summary=f"confidence={final_confidence:.2f}, threshold={orchestrator.threshold:.2f}",
            ) as ev:
                ev.output_summary = "Would auto-send" if auto_sent else "Would need review"
                ev.details = {
                    "threshold": orchestrator.threshold,
                    "final_confidence": final_confidence,
                    "pre_postprocess_confidence": pre_postprocess_confidence,
                    "precheck_route": precheck_route,
                    "decision": "auto_sent" if auto_sent else "pending_review",
                }

            pipeline_trace = safe_serialize_trace(trace)

            candidates.append({
                "index": i,
                "text": result.text,
                "confidence": final_confidence,
                "reasoning": result.reasoning,
                "pipeline_trace": pipeline_trace,
                "total_duration_ms": trace.total_duration_ms,
            })

        except Exception:
            logger.exception(
                "Failed to generate candidate %d for %s", i, conversation_id
            )
            candidates.append({
                "index": i,
                "text": "",
                "confidence": 0.0,
                "reasoning": "Generation failed",
                "pipeline_trace": safe_serialize_trace(trace),
                "total_duration_ms": trace.total_duration_ms,
                "error": True,
            })

    return {"conversation_id": conversation_id, "candidates": candidates}


@router.post("/generate")
async def generate_candidates(request: Request, body: GenerateRequest):
    """Generate multiple candidate AI responses for a single conversation."""
    orchestrator = request.app.state.orchestrator
    return await _generate_for_conversation(
        orchestrator, body.conversation_id, body.customer_message, body.num_candidates
    )


@router.post("/generate-all")
async def generate_all(request: Request, body: GenerateAllRequest):
    """Generate candidate responses for multiple conversations in parallel."""
    orchestrator = request.app.state.orchestrator
    num = body.num_candidates

    tasks = [
        _generate_for_conversation(
            orchestrator, item.conversation_id, item.customer_message, num
        )
        for item in body.conversations
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            conv_id = body.conversations[i].conversation_id
            logger.exception("generate-all failed for %s: %s", conv_id, result)
            output.append({
                "conversation_id": conv_id,
                "candidates": [{
                    "index": 0,
                    "text": "",
                    "confidence": 0.0,
                    "reasoning": f"Generation failed: {result}",
                    "pipeline_trace": [],
                    "total_duration_ms": 0,
                    "error": True,
                }],
            })
        else:
            output.append(result)

    return {"results": output}


@router.post("/generate-all-stream")
async def generate_all_stream(request: Request, body: GenerateAllRequest):
    """Stream candidate responses as SSE events — each result sent as soon as ready."""
    orchestrator = request.app.state.orchestrator
    num = body.num_candidates

    async def _event_generator():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        total = len(body.conversations)

        async def _run_one(item: GenerateAllItem) -> None:
            try:
                result = await _generate_for_conversation(
                    orchestrator, item.conversation_id, item.customer_message, num
                )
            except Exception as exc:
                logger.exception(
                    "generate-all-stream failed for %s: %s",
                    item.conversation_id, exc,
                )
                result = {
                    "conversation_id": item.conversation_id,
                    "candidates": [{
                        "index": 0,
                        "text": "",
                        "confidence": 0.0,
                        "reasoning": f"Generation failed: {exc}",
                        "pipeline_trace": [],
                        "total_duration_ms": 0,
                        "error": True,
                    }],
                }
            await queue.put(result)

        # Launch all tasks concurrently
        tasks = [asyncio.create_task(_run_one(item)) for item in body.conversations]

        # Yield results as they arrive
        for i in range(total):
            result = await queue.get()
            payload = json_mod.dumps(result)
            yield f"data: {payload}\n\n"

        # Final event to signal completion
        yield "data: [DONE]\n\n"

        # Ensure all tasks are cleaned up
        await asyncio.gather(*tasks, return_exceptions=True)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/send")
async def send_response(request: Request, body: SendRequest):
    """Send an approved/edited response to Intercom."""
    intercom_orch = _get_intercom_orchestrator(request)
    orchestrator = request.app.state.orchestrator

    if intercom_orch is None or intercom_orch._http_client is None:
        raise HTTPException(status_code=400, detail="Intercom API not available")

    try:
        await intercom_orch.reply_to_conversation(
            body.conversation_id, body.response_text
        )

        # Store in memory via the main orchestrator's memory agent
        user_id = body.user_id or body.conversation_id
        customer_msg = body.customer_message
        if customer_msg:
            await orchestrator.memory_agent.store_exchange(
                user_id, customer_msg, body.response_text
            )
        else:
            logger.warning(
                "Skipping memory storage for %s — no customer message provided",
                body.conversation_id,
            )

        logger.info("Eval: sent response to conversation %s", body.conversation_id)
        return {
            "status": "sent",
            "conversation_id": body.conversation_id,
        }

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        try:
            error_body = exc.response.json()
            detail = error_body.get("message") or error_body.get("errors", [{}])[0].get("message", str(exc))
        except Exception:
            detail = exc.response.text or str(exc)
        logger.error(
            "Intercom API error %d for conversation %s: %s",
            status, body.conversation_id, detail,
        )
        raise HTTPException(
            status_code=status,
            detail=f"Intercom API error ({status}): {detail}",
        )
    except Exception:
        logger.exception("Failed to send response to %s", body.conversation_id)
        raise HTTPException(status_code=500, detail="Failed to send response to Intercom")
