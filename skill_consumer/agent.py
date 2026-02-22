"""LLM-driven skill agent that reads documentation to answer technical questions.

Uses keyword extraction → BM25 retrieval → Think → Act → Observe loop
where the LLM decides at every step what files to read, whether to fetch
external docs, and when it has enough information to synthesize an answer.
"""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from skill_consumer.config import SkillAgentConfig
from skill_consumer.prompts import (
    KEYWORD_EXTRACTION_PROMPT,
    OBSERVE_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from skill_consumer.retriever import RetrievedFile, SkillRetriever
from skill_consumer.schemas import (
    KeywordExtraction,
    NextAction,
    ObserveDecision,
    PlanDecision,
    SkillAgentResponse,
)
from skill_consumer.tools import fetch_url, read_file, run_script

logger = logging.getLogger(__name__)


class SkillAgent:
    """LLM-driven agent that navigates skill files to answer questions."""

    def __init__(
        self,
        openai_api_key: str,
        config: SkillAgentConfig | None = None,
    ):
        self.config = config or SkillAgentConfig()
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self._retriever: SkillRetriever | None = None

    @property
    def retriever(self) -> SkillRetriever:
        """Lazily build and cache the BM25 index."""
        if self._retriever is None:
            self._retriever = SkillRetriever(self.config.skills_dir)
            self._retriever.build_index()
            logger.info("BM25 retriever initialized")
        return self._retriever

    async def answer(self, question: str) -> SkillAgentResponse:
        """Answer a question by navigating skill documentation.

        This is the main entry point. It runs:
        EXTRACT KEYWORDS → BM25 SEARCH → PLAN → ACT → OBSERVE → (repeat or SYNTHESIZE)
        """
        accumulated_content: list[dict[str, str]] = []  # [{source, content}]
        files_read: set[str] = set()
        total_chars = 0

        # --- Step 0: EXTRACT KEYWORDS ---
        try:
            keywords = await self._extract_keywords(question)
            logger.info("Extracted keywords: %s", keywords)
        except Exception:
            logger.exception("Skill agent keyword extraction failed")
            return self._empty_response("Keyword extraction step failed")

        # --- Step 1: BM25 SEARCH ---
        retrieved_files = self.retriever.search(
            keywords, top_k=self.config.bm25_top_k
        )
        logger.info("BM25 retrieved %d files", len(retrieved_files))

        if not retrieved_files:
            return self._empty_response("No relevant files found for the query.")

        # Build path → base_path lookup from BM25 results
        path_to_base: dict[str, str] = {
            f.relative_path: f.base_path for f in retrieved_files
        }

        # --- Step 2: PLAN ---
        try:
            plan = await self._plan(question, retrieved_files)
        except Exception:
            logger.exception("Skill agent PLAN step failed")
            return self._empty_response("Plan step failed")

        if not plan.files_to_read and not plan.needs_external_search:
            return self._empty_response(
                "Question does not relate to any available skill documentation."
            )

        # --- Iterative loop ---
        for iteration in range(self.config.max_iterations):
            logger.info(
                "Skill agent iteration %d/%d",
                iteration + 1,
                self.config.max_iterations,
            )

            # ACT: read files from plan
            for file_req in plan.files_to_read:
                if file_req.path in files_read:
                    continue
                if len(files_read) >= self.config.max_total_files:
                    logger.warning("Max total files reached (%d)", self.config.max_total_files)
                    break

                base_path = path_to_base.get(file_req.path)
                if base_path is None:
                    # Fallback: search indexed documents directly
                    base_path = self._resolve_base_path_fallback(file_req.path)
                if base_path is None:
                    logger.warning("Could not resolve base path for: %s", file_req.path)
                    continue

                result = await read_file(base_path, file_req.path)
                if result.get("content"):
                    accumulated_content.append({
                        "source": file_req.path,
                        "content": result["content"],
                    })
                    total_chars += len(result["content"])
                    files_read.add(file_req.path)
                elif result.get("error"):
                    logger.warning("Error reading %s: %s", file_req.path, result["error"])

            # ACT: fetch external URLs if requested
            if plan.needs_external_search and self.config.enable_url_fetch:
                for url in plan.external_urls[:3]:
                    result = await fetch_url(url, self.config.allowed_fetch_domains)
                    if result.get("content"):
                        accumulated_content.append({
                            "source": url,
                            "content": result["content"],
                        })
                        total_chars += len(result["content"])

            # Check context budget
            if total_chars >= self.config.max_context_chars:
                logger.warning(
                    "Context budget exceeded (%d chars), synthesizing now",
                    total_chars,
                )
                break

            # OBSERVE: decide next action (skip on last iteration)
            if iteration < self.config.max_iterations - 1:
                try:
                    observe = await self._observe(
                        question, accumulated_content, files_read, retrieved_files
                    )
                except Exception:
                    logger.exception("Skill agent OBSERVE step failed")
                    break  # Fall through to synthesis with what we have

                if observe.next_action == NextAction.ANSWER:
                    break

                elif observe.next_action == NextAction.GIVE_UP:
                    break

                elif observe.next_action == NextAction.READ_MORE:
                    plan = PlanDecision(
                        reasoning=observe.reasoning,
                        files_to_read=observe.additional_files,
                        needs_external_search=False,
                        external_urls=[],
                    )

                elif observe.next_action == NextAction.FETCH_URL:
                    plan = PlanDecision(
                        reasoning=observe.reasoning,
                        files_to_read=[],
                        needs_external_search=True,
                        external_urls=observe.urls_to_fetch,
                    )

                elif observe.next_action == NextAction.RUN_SCRIPT:
                    if (
                        observe.script_to_run
                        and self.config.enable_script_execution
                    ):
                        base_path = path_to_base.get(
                            observe.script_to_run.script_path
                        )
                        if base_path is None:
                            base_path = self._resolve_base_path_fallback(
                                observe.script_to_run.script_path
                            )
                        if base_path:
                            result = await run_script(
                                base_path,
                                observe.script_to_run.script_path,
                                observe.script_to_run.arguments,
                            )
                            output = result.get("stdout") or result.get("error", "")
                            if output:
                                accumulated_content.append({
                                    "source": f"script:{observe.script_to_run.script_path}",
                                    "content": output,
                                })
                                total_chars += len(output)
                    # After script, continue loop (will observe again)
                    plan = PlanDecision(
                        reasoning="Script executed, re-evaluating",
                        files_to_read=[],
                        needs_external_search=False,
                        external_urls=[],
                    )

        # --- Step 3: SYNTHESIZE ---
        if not accumulated_content:
            return self._empty_response("No content was retrieved from skill files.")

        try:
            return await self._synthesize(question, accumulated_content)
        except Exception:
            logger.exception("Skill agent SYNTHESIZE step failed")
            return self._empty_response("Synthesis step failed")

    async def _extract_keywords(self, question: str) -> list[str]:
        """Use a lightweight LLM call to extract search keywords from the question."""
        response = await self.client.chat.completions.create(
            model=self.config.keyword_model,
            messages=[
                {"role": "system", "content": KEYWORD_EXTRACTION_PROMPT},
                {"role": "user", "content": question},
            ],
            response_format={"type": "json_object"},
            timeout=self.config.llm_timeout,
        )

        raw_text = response.choices[0].message.content
        logger.debug("[Skill Agent - Keywords] LLM response: %s", raw_text)
        raw = json.loads(raw_text)
        extraction = KeywordExtraction(**raw)
        return extraction.keywords

    async def _plan(
        self, question: str, retrieved_files: list[RetrievedFile]
    ) -> PlanDecision:
        """Use the router model to decide which of the BM25-retrieved files to read."""
        files_text = self._format_retrieved_files(retrieved_files)
        user_msg = (
            f"## Relevant Documentation Files\n\n{files_text}\n\n"
            f"## User Question\n\n{question}"
        )

        response = await self.client.chat.completions.create(
            model=self.config.router_model,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            timeout=self.config.llm_timeout,
        )

        raw_text = response.choices[0].message.content
        logger.debug("[Skill Agent - Plan] LLM response: %s", raw_text)
        raw = json.loads(raw_text)
        return PlanDecision(**raw)

    async def _observe(
        self,
        question: str,
        accumulated_content: list[dict[str, str]],
        files_read: set[str],
        retrieved_files: list[RetrievedFile],
    ) -> ObserveDecision:
        """Evaluate retrieved content and decide the next action."""
        content_block = self._format_content(accumulated_content)

        # Show only unread files from BM25 results
        unread_files = [f for f in retrieved_files if f.relative_path not in files_read]
        files_text = self._format_retrieved_files(unread_files)

        user_msg = (
            f"## User Question\n\n{question}\n\n"
            f"## Retrieved Content\n\n{content_block}\n\n"
            f"## Files Already Read\n\n{', '.join(sorted(files_read)) or 'None'}\n\n"
            f"## Available Files (not yet read)\n\n{files_text}"
        )

        response = await self.client.chat.completions.create(
            model=self.config.synthesis_model,
            messages=[
                {"role": "system", "content": OBSERVE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            timeout=self.config.llm_timeout,
        )

        raw_text = response.choices[0].message.content
        logger.debug("[Skill Agent - Observe] LLM response: %s", raw_text)
        raw = json.loads(raw_text)
        return ObserveDecision(**raw)

    async def _synthesize(
        self,
        question: str,
        accumulated_content: list[dict[str, str]],
    ) -> SkillAgentResponse:
        """Produce a final answer from accumulated documentation content."""
        content_block = self._format_content(accumulated_content)

        user_msg = (
            f"## User Question\n\n{question}\n\n"
            f"## Retrieved Documentation\n\n{content_block}"
        )

        response = await self.client.chat.completions.create(
            model=self.config.synthesis_model,
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            timeout=self.config.llm_timeout,
        )

        raw_text = response.choices[0].message.content
        logger.debug("[Skill Agent - Synthesize] LLM response: %s", raw_text)
        raw = json.loads(raw_text)
        return SkillAgentResponse(**raw)

    def _resolve_base_path_fallback(self, relative_path: str) -> str | None:
        """Fallback: search indexed documents for a file not in BM25 results."""
        for doc in self.retriever._documents:
            if doc.relative_path == relative_path:
                return doc.base_path
        return None

    @staticmethod
    def _format_retrieved_files(files: list[RetrievedFile]) -> str:
        """Format BM25 results as a concise list for LLM prompts."""
        if not files:
            return "(No relevant files found)"
        lines = []
        for f in files:
            lines.append(
                f"- [{f.file_type}] {f.relative_path} "
                f"(relevance: {f.bm25_score:.2f}) -- {f.description}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_content(accumulated: list[dict[str, str]]) -> str:
        """Format accumulated content for inclusion in an LLM prompt."""
        parts = []
        for item in accumulated:
            parts.append(f"### Source: {item['source']}\n\n{item['content']}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _empty_response(reason: str) -> SkillAgentResponse:
        """Return an empty response with zero confidence."""
        return SkillAgentResponse(
            answer_text="",
            confidence=0.0,
            reasoning=reason,
            sources=[],
        )
