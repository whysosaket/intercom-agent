from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Intercom
    INTERCOM_ACCESS_TOKEN: str = ""
    INTERCOM_WEBHOOK_SECRET: str = ""
    INTERCOM_ADMIN_ID: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Mem0
    MEM0_API_KEY: str = ""
    MEM0_GLOBAL_USER_ID: str = "global_catalogue"

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_CHANNEL_ID: str = ""

    # Application
    CONFIDENCE_THRESHOLD: float = 0.8
    LOG_LEVEL: str = "INFO"

    # Sync configuration
    SYNC_MAX_CONVERSATIONS: int = 200
    SYNC_MAX_MESSAGES_PER_CONVERSATION: int = 5
    SYNC_MAX_CONVERSATION_CHARS: int = 3000
    SYNC_DATA_DIR: str = "data"

    # Skill Agent
    SKILL_AGENT_ENABLED: bool = True
    SKILL_AGENT_ROUTER_MODEL: str = "gpt-5"
    SKILL_AGENT_SYNTHESIS_MODEL: str = "gpt-5"
    SKILL_AGENT_MAX_ITERATIONS: int = 4

    # Doc Agent (Mintlify Documentation Search)
    DOC_AGENT_ENABLED: bool = True
    DOC_AGENT_MINTLIFY_URL: str = "https://docs.mem0.ai"
    DOC_AGENT_MODEL: str = "gpt-4o"
    DOC_AGENT_CONFIDENCE_THRESHOLD: float = 0.6
    DOC_AGENT_MAX_RESULTS: int = 5
    DOC_AGENT_PRODUCT_DESCRIPTION: str = ""

    # Post-Processor
    POST_PROCESSOR_ENABLED: bool = True
    POST_PROCESSOR_MODEL: str = "gpt-5"

    # Mock / Development
    MOCK_MODE: bool = False
    CHAT_UI_ENABLED: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
