import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.orchestrator import Orchestrator
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
    # Memory and OpenAI are always real — they're needed for proper testing
    from app.services.memory_service import MemoryService
    from app.services.openai_service import OpenAIService

    memory_service = MemoryService(
        api_key=settings.MEM0_API_KEY,
        global_user_id=settings.MEM0_GLOBAL_USER_ID,
    )
    openai_service = OpenAIService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
    )

    if settings.MOCK_MODE:
        # Mock mode: only Intercom replies and Slack are faked
        logger.info("Starting in MOCK MODE (Intercom replies & Slack mocked)")
        from app.services.mock.mock_intercom_client import MockIntercomClient
        from app.services.mock.mock_slack_service import MockSlackService

        intercom_client = MockIntercomClient()
        slack_service = MockSlackService()
    else:
        from app.services.intercom_client import IntercomClient
        from app.services.slack_service import SlackService

        intercom_client = IntercomClient(
            access_token=settings.INTERCOM_ACCESS_TOKEN,
            admin_id=settings.INTERCOM_ADMIN_ID,
        )
        slack_service = SlackService(
            bot_token=settings.SLACK_BOT_TOKEN,
            channel_id=settings.SLACK_CHANNEL_ID,
        )

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

    # Post-processor: LLM agent that refines responses for tone/formatting
    # and provides a final confidence evaluation before routing
    post_processor = None
    if settings.POST_PROCESSOR_ENABLED and settings.OPENAI_API_KEY:
        from app.services.postprocessor import PostProcessor

        post_processor = PostProcessor(
            api_key=settings.OPENAI_API_KEY,
            model=settings.POST_PROCESSOR_MODEL,
        )
        logger.info("Post-processor initialized (model=%s)",
                     settings.POST_PROCESSOR_MODEL)
    else:
        logger.info("Post-processor disabled")

    orchestrator = Orchestrator(
        memory_service=memory_service,
        openai_service=openai_service,
        intercom_client=intercom_client,
        slack_service=slack_service,
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        skill_agent=skill_agent,
        post_processor=post_processor,
    )

    # Sync service uses a REAL Intercom client (even in mock mode) for data fetching
    from app.services.sync_service import SyncService

    sync_intercom_client = None
    sync_service = None

    if settings.INTERCOM_ACCESS_TOKEN:
        from app.services.intercom_client import IntercomClient as RealIntercomClient

        sync_intercom_client = RealIntercomClient(
            access_token=settings.INTERCOM_ACCESS_TOKEN,
            admin_id=settings.INTERCOM_ADMIN_ID,
        )
        sync_service = SyncService(
            intercom_client=sync_intercom_client,
            memory_service=memory_service,
            max_conversations=settings.SYNC_MAX_CONVERSATIONS,
            max_messages_per_conversation=settings.SYNC_MAX_MESSAGES_PER_CONVERSATION,
            max_conversation_chars=settings.SYNC_MAX_CONVERSATION_CHARS,
            data_dir=settings.SYNC_DATA_DIR,
        )
    else:
        logger.warning("No INTERCOM_ACCESS_TOKEN — sync disabled")

    intercom_webhook.orchestrator = orchestrator
    if _slack_available:
        set_slack_orchestrator(orchestrator)

    app.state.orchestrator = orchestrator
    app.state.sync_service = sync_service

    logger.info("All services initialized")
    yield

    if sync_intercom_client:
        await sync_intercom_client.close()
    if hasattr(intercom_client, "close"):
        await intercom_client.close()
    logger.info("Shutdown complete")


api = FastAPI(title="Intercom Auto-Responder", lifespan=lifespan)
api.include_router(intercom_router)

# Static files for chat UI
api.mount("/static", StaticFiles(directory="app/static"), name="static")

# Chat UI (conditional)
if settings.CHAT_UI_ENABLED:
    from app.chat.router import router as chat_router

    api.include_router(chat_router)


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
