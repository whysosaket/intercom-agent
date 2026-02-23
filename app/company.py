"""Company-specific configuration for the support bot.

Edit this file to customize the bot for your company. All company-specific
data — product names, URLs, FAQ entries, post-processing rules — lives here
so the rest of the codebase remains generic.

Values can be overridden via environment variables prefixed with ``COMPANY_``
(e.g. ``COMPANY_NAME=Acme``).
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class FAQEntry(BaseSettings):
    """A single FAQ question-answer pair."""

    question: str
    answer: str


class ObsoleteParameter(BaseSettings):
    """Describes a parameter that should be stripped from code examples."""

    client_name: str  # e.g. "MemoryClient"
    param_names: list[str]  # e.g. ["org_id", "project_id"]
    note: str = ""  # Human-readable explanation


class CompanyConfig(BaseSettings):
    """All company-specific data in one place.

    Defaults are set for Mem0 (the original deployment). Override via
    environment variables or by editing the defaults below.
    """

    # ── Core identity ──
    name: str = "Mem0"
    name_alias: str = "MemZero"
    product_description: str = "A memory layer for AI agents"
    support_platform_name: str = "Intercom"

    # ── Product features (shown in system prompt) ──
    product_features: list[str] = [
        "Vector memories (semantic retrieval using vector search)",
        "Graph memories (relationship-based memory structures)",
        "Hybrid retrieval logic",
    ]

    # ── Sub-products ──
    sub_products: list[str] = [
        "OpenMemory is a Mem0 product that enables coding and accessing memories via MCP (Model Context Protocol).",
    ]

    # ── URLs ──
    documentation_url: str = "https://docs.mem0.ai"
    pricing_url: str = "https://mem0.ai/pricing"
    custom_pricing_url: str = "https://cal.com/manmeet-sethi/quick-chat"
    dashboard_url: str = "https://app.mem0.ai"
    support_email: str = "support@mem0.ai"

    # ── FAQ knowledge base ──
    faq_entries: list[FAQEntry] = [
        FAQEntry(
            question="What is my user ID?",
            answer=(
                "The user_id can be anything you send in the add call. "
                "If that user does not already exist, we will automatically "
                "create it when the memory is added."
            ),
        ),
        FAQEntry(
            question="Where can I delete all my memories?",
            answer=(
                "Project Settings -> Configuration -> Delete All Memories\n"
                "https://app.mem0.ai/dashboard/settings?tab=projects&subtab=configuration"
            ),
        ),
        FAQEntry(
            question="What does the pricing plan look like?",
            answer="https://mem0.ai/pricing",
        ),
        FAQEntry(
            question="How can I get custom pricing?",
            answer="https://cal.com/manmeet-sethi/quick-chat",
        ),
        FAQEntry(
            question="How can I export all memories?",
            answer="Use the Memory Exports feature in the dashboard, or the getAll API call.",
        ),
        FAQEntry(
            question="I want to delete my account.",
            answer="Email support@mem0.ai from your registered email address.",
        ),
    ]

    # ── Post-processing rules (company-specific) ──
    # Extra rules injected into the post-processor system prompt.
    post_processor_extra_rules: list[str] = [
        "Graph in Mem0 is a PRO feature and it requires a PRO plan. "
        "Mention this to users if they ask questions about it and you feel "
        "that it is necessary to include that.",
    ]

    # Languages allowed in code examples (others are stripped).
    allowed_code_languages: list[str] = ["python"]

    # Parameters that are obsolete and must be removed from code snippets.
    obsolete_parameters: list[ObsoleteParameter] = [
        ObsoleteParameter(
            client_name="MemoryClient",
            param_names=["org_id", "project_id"],
            note=(
                "The org_id and project_id parameters for MemoryClient are "
                "obsolete and MUST be removed from any code snippet. "
                "If you see MemoryClient(api_key=\"...\", org_id=\"...\", "
                "project_id=\"...\"), rewrite it as MemoryClient(api_key=\"...\")."
            ),
        ),
    ]

    # ── Skill agent / doc agent ──
    # Domains the skill agent is allowed to fetch from.
    allowed_fetch_domains: list[str] = [
        "docs.mem0.ai",
        "github.com",
        "raw.githubusercontent.com",
    ]

    model_config = {"env_prefix": "COMPANY_", "env_file": ".env", "extra": "ignore"}


# Singleton instance used across the application.
company_config = CompanyConfig()
