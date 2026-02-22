from dataclasses import dataclass, field


@dataclass
class SkillAgentConfig:
    """Configuration for the LLM-driven Skill Agent."""

    # Model selection
    router_model: str = "gpt-5-mini"  # fast model for file selection
    synthesis_model: str = "gpt-5-mini"  # full model for reasoning + answer

    # Loop control
    max_iterations: int = 4  # max think-act-observe cycles
    max_files_per_iteration: int = 5
    max_total_files: int = 8

    # Content limits
    max_context_chars: int = 50_000

    # Paths
    skills_dir: str = "skills"

    # Timeouts
    llm_timeout: float = 30.0

    # Feature flags
    enable_url_fetch: bool = True
    enable_script_execution: bool = True
    allowed_fetch_domains: list[str] = field(
        default_factory=lambda: [
            "docs.mem0.ai",
            "github.com",
            "raw.githubusercontent.com",
        ]
    )
