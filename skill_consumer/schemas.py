"""Pydantic models for all structured LLM outputs in the skill agent."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# --- Step 1: PLAN (which files to read) ---


class FileRequest(BaseModel):
    """A file the LLM wants to read."""

    path: str = Field(
        description="Relative path within the skill directory, e.g. 'references/mem0-platform/add-memory.md'"
    )
    reason: str = Field(description="Why this file is relevant to the question")


class PlanDecision(BaseModel):
    """LLM output from the PLAN step (router model)."""

    reasoning: str = Field(
        description="Chain-of-thought about which files are relevant"
    )
    files_to_read: list[FileRequest] = Field(
        default_factory=list,
        description="Files to read in this iteration (max 5)",
    )
    needs_external_search: bool = Field(
        default=False,
        description="True if the question likely needs info beyond local docs",
    )
    external_urls: list[str] = Field(
        default_factory=list,
        description="External documentation URLs to fetch",
    )


# --- Step 2: OBSERVE (decide next action after reading files) ---


class NextAction(str, Enum):
    ANSWER = "answer"  # enough info to synthesize
    READ_MORE = "read_more"  # need additional files
    FETCH_URL = "fetch_url"  # need external documentation
    RUN_SCRIPT = "run_script"  # need to execute a script
    GIVE_UP = "give_up"  # cannot answer from available sources


class ScriptRequest(BaseModel):
    """A script the LLM wants to execute."""

    script_path: str = Field(
        description="Relative path to script, e.g. 'scripts/mem0_doc_search.py'"
    )
    arguments: list[str] = Field(
        description="Command-line arguments for the script"
    )
    reason: str = Field(description="Why this script needs to run")


class ObserveDecision(BaseModel):
    """LLM output from the OBSERVE step (synthesis model)."""

    reasoning: str = Field(
        description="Assessment of whether retrieved content answers the question"
    )
    next_action: NextAction
    additional_files: list[FileRequest] = Field(
        default_factory=list,
        description="More files to read if next_action is READ_MORE",
    )
    urls_to_fetch: list[str] = Field(
        default_factory=list,
        description="URLs to fetch if next_action is FETCH_URL",
    )
    script_to_run: ScriptRequest | None = Field(
        default=None,
        description="Script to execute if next_action is RUN_SCRIPT",
    )


# --- Step 3: SYNTHESIZE (final answer) ---


class SkillAgentResponse(BaseModel):
    """Final structured response from the skill agent."""

    answer_text: str = Field(
        description="The complete answer, or empty string if unable to answer"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the answer (0.0 to 1.0)"
    )
    reasoning: str = Field(
        description="Explanation of how the answer was derived"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="File paths and URLs used to construct the answer",
    )
