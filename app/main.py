import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.company import company_config
from app.config import settings
from app.webhooks.intercom import router as intercom_router
from app.webhooks import intercom as intercom_webhook

# Slack webhook imports may fail if slack-bolt is not installed (e.g. local mock mode)
try:
    from app.webhooks.slack import slack_handler, set_orchestrator as set_slack_orchestrator

    _slack_available = True
except ImportError:
    _slack_available = False

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.agents import (
        DocAgent,
        MemZeroAgent,
        MemoryAgent,
        PreCheckAgent,
        ResponseAgent,
        PostProcessingAgent,
        SlackAgent,
        OrchestratorAgent,
    )

    # --- Agents (own SDK clients directly, no service layer) ---

    memzero_agent = MemZeroAgent(
        api_key=settings.MEM0_API_KEY,
        global_user_id=settings.MEM0_GLOBAL_USER_ID,
    )
    memory_agent = MemoryAgent(memzero_agent=memzero_agent)

    # Skill Agent: LLM-driven agent that reads skill documentation to answer
    # technical questions the primary AI can't handle from memory alone
    skill_agent = None
    if settings.SKILL_AGENT_ENABLED and settings.OPENAI_API_KEY:
        from skill_consumer import SkillAgent
        from skill_consumer.config import SkillAgentConfig

        skill_agent = SkillAgent(
            openai_api_key=settings.OPENAI_API_KEY,
            config=SkillAgentConfig(
                router_model=settings.SKILL_AGENT_ROUTER_MODEL,
                synthesis_model=settings.SKILL_AGENT_SYNTHESIS_MODEL,
                max_iterations=settings.SKILL_AGENT_MAX_ITERATIONS,
                skills_dir="skills",
            ),
        )
        logger.info("Skill agent initialized (router=%s, synthesis=%s)",
                     settings.SKILL_AGENT_ROUTER_MODEL,
                     settings.SKILL_AGENT_SYNTHESIS_MODEL)
    else:
        logger.info("Skill agent disabled")

    # Doc Agent: searches Mintlify documentation before falling back to SkillAgent
    doc_agent = None
    if settings.DOC_AGENT_ENABLED and settings.OPENAI_API_KEY:
        doc_agent = DocAgent(
            api_key=settings.OPENAI_API_KEY,
            mintlify_url=settings.DOC_AGENT_MINTLIFY_URL,
            product_description=settings.DOC_AGENT_PRODUCT_DESCRIPTION,
            model=settings.DOC_AGENT_MODEL,
            confidence_threshold=settings.DOC_AGENT_CONFIDENCE_THRESHOLD,
            skill_agent=skill_agent,
            max_results=settings.DOC_AGENT_MAX_RESULTS,
        )
        await doc_agent.initialize()
        logger.info("Doc agent initialized (url=%s, model=%s)",
                     settings.DOC_AGENT_MINTLIFY_URL, settings.DOC_AGENT_MODEL)
    else:
        logger.info("Doc agent disabled")

    # The fallback agent is DocAgent (which wraps SkillAgent) or bare SkillAgent
    fallback_agent = doc_agent or skill_agent

    response_agent = ResponseAgent(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        skill_agent=fallback_agent,
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
    )

    # Pre-check agent: fast classifier that routes before answer generation
    precheck_agent = None
    if settings.PRE_CHECK_ENABLED and settings.OPENAI_API_KEY:
        precheck_agent = PreCheckAgent(
            api_key=settings.OPENAI_API_KEY,
            model=settings.PRE_CHECK_MODEL,
            company_cfg=company_config,
        )
        logger.info("Pre-check agent enabled (model=%s)", settings.PRE_CHECK_MODEL)
    else:
        logger.info("Pre-check agent disabled")

    # Post-processing agent: pass api_key only when enabled
    postprocessing_agent = PostProcessingAgent(
        api_key=settings.OPENAI_API_KEY if settings.POST_PROCESSOR_ENABLED else None,
        model=settings.POST_PROCESSOR_MODEL,
        company_cfg=company_config,
    )
    if postprocessing_agent.is_enabled:
        logger.info("Post-processing agent enabled (model=%s)", settings.POST_PROCESSOR_MODEL)
    else:
        logger.info("Post-processing agent disabled")

    slack_agent = SlackAgent(
        bot_token=settings.SLACK_BOT_TOKEN if not settings.MOCK_MODE else "",
        channel_id=settings.SLACK_CHANNEL_ID,
        mock_mode=settings.MOCK_MODE,
    )

    orchestrator = OrchestratorAgent(
        memory_agent=memory_agent,
        response_agent=response_agent,
        postprocessing_agent=postprocessing_agent,
        slack_agent=slack_agent,
        precheck_agent=precheck_agent,
        intercom_access_token=settings.INTERCOM_ACCESS_TOKEN if not settings.MOCK_MODE else "",
        intercom_admin_id=settings.INTERCOM_ADMIN_ID,
        mock_mode=settings.MOCK_MODE,
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
    )

    await orchestrator.initialize()

    # Sync service uses a REAL (non-mock) OrchestratorAgent for data fetching
    from app.services.sync_service import SyncService

    sync_service = None

    if settings.INTERCOM_ACCESS_TOKEN:
        sync_orchestrator = OrchestratorAgent(
            memory_agent=memory_agent,
            response_agent=response_agent,
            postprocessing_agent=postprocessing_agent,
            slack_agent=slack_agent,
            precheck_agent=precheck_agent,
            intercom_access_token=settings.INTERCOM_ACCESS_TOKEN,
            intercom_admin_id=settings.INTERCOM_ADMIN_ID,
            mock_mode=False,
            confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        )
        sync_service = SyncService(
            orchestrator=sync_orchestrator,
            memzero_agent=memzero_agent,
            max_conversations=settings.SYNC_MAX_CONVERSATIONS,
            max_messages_per_conversation=settings.SYNC_MAX_MESSAGES_PER_CONVERSATION,
            max_conversation_chars=settings.SYNC_MAX_CONVERSATION_CHARS,
            data_dir=settings.SYNC_DATA_DIR,
        )
    else:
        sync_orchestrator = None
        logger.warning("No INTERCOM_ACCESS_TOKEN — sync disabled")

    # Message coordinator: buffers rapid consecutive messages per conversation
    from app.services.message_coordinator import MessageCoordinator

    coordinator = MessageCoordinator(
        orchestrator=orchestrator,
        timeout=settings.MESSAGE_BUFFER_TIMEOUT_SECONDS,
    )
    logger.info(
        "Message coordinator initialized (buffer_timeout=%.1fs)",
        settings.MESSAGE_BUFFER_TIMEOUT_SECONDS,
    )

    intercom_webhook.orchestrator = orchestrator
    intercom_webhook.message_coordinator = coordinator
    if _slack_available:
        set_slack_orchestrator(orchestrator)

    app.state.orchestrator = orchestrator
    app.state.sync_service = sync_service
    # A non-mock orchestrator for Intercom API calls (eval mode, sync, etc.)
    app.state.intercom_orchestrator = sync_orchestrator

    logger.info("All agents initialized")
    yield

    await orchestrator.shutdown()
    if doc_agent:
        await doc_agent.shutdown()
    if sync_orchestrator:
        await sync_orchestrator.close()
    logger.info("Shutdown complete")


api = FastAPI(
    title=f"{company_config.name} {company_config.support_platform_name} Auto-Responder",
    lifespan=lifespan,
)
api.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api.include_router(intercom_router)

# Chat UI (conditional)
if settings.CHAT_UI_ENABLED:
    from app.chat.router import router as chat_router
    from app.eval.router import router as eval_router

    api.include_router(chat_router)
    api.include_router(eval_router)


if _slack_available:

    @api.post("/slack/events")
    async def slack_events(req: Request):
        return await slack_handler.handle(req)


@api.post("/sync")
async def sync_conversations(request: Request, background_tasks: BackgroundTasks):
    """Fetch Intercom conversations, save locally, and ingest into Mem0."""
    sync_service = request.app.state.sync_service
    if sync_service is None:
        raise HTTPException(
            status_code=400,
            detail="Sync not available: no INTERCOM_ACCESS_TOKEN configured",
        )
    background_tasks.add_task(sync_service.sync_all_conversations)
    return {
        "status": "sync_started",
        "message": "Fetching conversations from Intercom and ingesting into Mem0. Check logs for progress.",
    }


@api.post("/sync-local")
async def sync_from_local(request: Request, background_tasks: BackgroundTasks):
    """Re-ingest conversations from the local JSON file into Mem0."""
    sync_service = request.app.state.sync_service
    if sync_service is None:
        raise HTTPException(
            status_code=400,
            detail="Sync not available: no INTERCOM_ACCESS_TOKEN configured",
        )
    background_tasks.add_task(sync_service.sync_from_local_json)
    return {
        "status": "sync_from_local_started",
        "message": "Re-ingesting from local JSON in the background. Check logs for progress.",
    }


@api.get("/health")
async def health():
    return {"status": "ok"}
