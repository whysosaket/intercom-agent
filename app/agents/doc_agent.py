"""Doc Agent — searches Mintlify documentation before falling back to SkillAgent."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI

from app.agents.base import BaseAgent
from skill_consumer.schemas import SkillAgentResponse

if TYPE_CHECKING:
    from app.chat.trace import TraceCollector
    from skill_consumer import SkillAgent

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

QUERY_REWRITE_PROMPT = """\
You are a query optimization agent for a documentation search engine.

Product context:
{product_description}

Given a customer support message, rewrite it as an optimized search query for
searching product documentation.

Rules:
- Extract the core technical question.
- Remove conversational filler (greetings, "I need help with", etc.).
- Include relevant product terminology from the product context above.
- Keep the query concise (under 20 words).
- If the message contains multiple questions, focus on the primary one.
- Output ONLY the rewritten query string, nothing else.
"""

PAGE_SELECTION_PROMPT = """\
You are a documentation navigator. Given a search query and the full contents
of an llms.txt file (which lists every page in a documentation site with URLs
and short descriptions), select the 3-5 most relevant page URLs that are
likely to answer the query.

Rules:
- Pick pages whose title or description best matches the query intent.
- Prefer specific feature/API pages over generic overview pages.
- Return between 1 and 5 URLs, ordered by relevance (most relevant first).

You MUST respond with valid JSON:
{"urls": ["https://docs.example.com/page1", "https://docs.example.com/page2"]}
"""

DOC_SYNTHESIS_PROMPT = """\
You are a technical support agent. Answer the customer question using ONLY
the documentation content provided below.

Rules:
- Do NOT fabricate information that is not in the provided documentation.
- Be concise — 2-5 sentences unless the question demands more detail.
- Use Python code examples only (no JavaScript/cURL) and keep snippets under 10 lines.
- Include relevant documentation links where helpful.
- If the documentation does not contain enough information, say so and set a low confidence.

Confidence guidelines:
- 0.9-1.0: Direct, complete answer found in docs.
- 0.7-0.8: Good answer with minor gaps.
- 0.4-0.6: Partial answer, significant information missing.
- 0.1-0.3: Barely relevant content found.
- 0.0: No relevant content at all.

You MUST respond with valid JSON and nothing else:
{
    "answer_text": "your answer here",
    "confidence": 0.0,
    "reasoning": "how you derived this answer",
    "sources": ["https://docs.example.com/page"]
}
"""


class DocAgent(BaseAgent):
    """Searches Mintlify documentation and synthesises an answer.

    Flow:
    1. Rewrite user query for doc search.
    2. Fetch llms.txt (full page index) and ask LLM to pick relevant URLs.
    3. Fetch markdown content of each page.
    4. Synthesise an answer from the fetched content.
    5. If confidence is high, return. Otherwise fall back to SkillAgent.
    """

    def __init__(
        self,
        api_key: str,
        mintlify_url: str = "https://docs.mem0.ai",
        product_description: str = "",
        model: str = "gpt-5-mini",
        confidence_threshold: float = 0.6,
        skill_agent: SkillAgent | None = None,
        max_results: int = 5,
    ):
        super().__init__(name="doc")
        self.client = AsyncOpenAI(api_key=api_key)
        self.mintlify_url = mintlify_url.rstrip("/")
        self.product_description = product_description
        self.model = model
        self.threshold = confidence_threshold
        self.skill_agent = skill_agent
        self.max_results = max_results
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        self._http = httpx.AsyncClient(timeout=15.0)
        self.logger.info(
            "Doc agent initialized (url=%s, model=%s, threshold=%.2f)",
            self.mintlify_url,
            self.model,
            self.threshold,
        )

    async def shutdown(self) -> None:
        if self._http:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Public API — same signature shape as SkillAgent.answer()
    # ------------------------------------------------------------------

    async def answer(
        self,
        question: str,
        trace: TraceCollector | None = None,
    ) -> SkillAgentResponse:
        """Search docs, synthesise an answer, optionally fall back to SkillAgent."""
        doc_response: SkillAgentResponse | None = None

        try:
            # 1. Rewrite the query for documentation search
            query = await self._rewrite_query(question, trace=trace)
            self.logger.info("Rewritten query: %s", query)

            # 2. Fetch llms.txt and select relevant page URLs
            page_urls = await self._select_pages(query, trace=trace)
            self.logger.info("Selected %d doc pages", len(page_urls))

            if page_urls:
                # 3. Fetch markdown content of each page
                pages = await self._fetch_pages(page_urls, trace=trace)
                self.logger.info("Fetched %d pages successfully", len(pages))

                if pages:
                    # 4. Synthesise response from page content
                    doc_response = await self._synthesize(question, pages, trace=trace)
                    self.logger.info(
                        "Doc synthesis confidence=%.2f", doc_response.confidence
                    )

                    if doc_response.confidence >= self.threshold:
                        return doc_response

                    self.logger.info(
                        "Doc confidence %.2f < threshold %.2f, trying skill agent",
                        doc_response.confidence,
                        self.threshold,
                    )
            else:
                self.logger.info("No relevant pages found, trying skill agent")

        except Exception:
            self.logger.exception("Doc agent search/synthesis failed")

        # 5. Skill Agent fallback
        if self.skill_agent is not None:
            try:
                if trace:
                    with trace.step(
                        "Skill Agent fallback (from Doc Agent)",
                        "agent_call",
                        input_summary=f"doc_confidence={doc_response.confidence:.2f if doc_response else 'N/A'}",
                    ) as ev:
                        skill_result = await self.skill_agent.answer(question)
                        used = not (
                            doc_response
                            and doc_response.confidence > skill_result.confidence
                        )
                        ev.output_summary = (
                            f"confidence={skill_result.confidence:.2f}, used={used}"
                        )
                        ev.details = {
                            "skill_confidence": skill_result.confidence,
                            "skill_reasoning": skill_result.reasoning,
                            "skill_sources": skill_result.sources,
                            "used_skill_response": used,
                        }
                        if not used:
                            return doc_response
                        return skill_result
                else:
                    skill_result = await self.skill_agent.answer(question)
                    if (
                        doc_response
                        and doc_response.confidence > skill_result.confidence
                    ):
                        return doc_response
                    return skill_result
            except Exception:
                self.logger.exception("Skill agent fallback also failed")

        # 6. Return best effort or empty
        if doc_response:
            return doc_response

        return SkillAgentResponse(
            answer_text="",
            confidence=0.0,
            reasoning="Doc agent could not find relevant documentation",
            sources=[],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _rewrite_query(
        self,
        customer_message: str,
        trace: TraceCollector | None = None,
    ) -> str:
        """Use OpenAI to rewrite the customer message into a search query."""
        try:
            if trace:
                with trace.step(
                    f"OpenAI LLM call ({self.model})",
                    "llm_call",
                    input_summary=f"query rewrite, model={self.model}",
                ) as ev:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": QUERY_REWRITE_PROMPT.format(
                                    product_description=self.product_description
                                    or "A developer-facing product."
                                ),
                            },
                            {"role": "user", "content": customer_message},
                        ],
                    )
                    rewritten = response.choices[0].message.content.strip()
                    ev.output_summary = f"rewritten: {rewritten[:80]}"
                    ev.details = {
                        "model": self.model,
                        "purpose": "query_rewrite",
                        "original_message": customer_message[:200],
                        "rewritten_query": rewritten,
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                            "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        },
                    }
                    return rewritten if rewritten else customer_message
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": QUERY_REWRITE_PROMPT.format(
                                product_description=self.product_description
                                or "A developer-facing product."
                            ),
                        },
                        {"role": "user", "content": customer_message},
                    ],
                )
                rewritten = response.choices[0].message.content.strip()
                self.logger.debug("[Step 1 - Query Rewrite] LLM response: %s", rewritten)
                return rewritten if rewritten else customer_message
        except Exception:
            self.logger.exception("Query rewrite failed, using original")
            return customer_message

    async def _select_pages(
        self,
        query: str,
        trace: TraceCollector | None = None,
    ) -> list[str]:
        """Fetch llms.txt, feed it to the LLM, and get back relevant page URLs."""
        assert self._http is not None

        # Fetch the full llms.txt index
        try:
            if trace:
                with trace.step(
                    "HTTP fetch: llms.txt",
                    "http_fetch",
                    input_summary=f"GET {self.mintlify_url}/llms.txt",
                ) as ev:
                    resp = await self._http.get(f"{self.mintlify_url}/llms.txt")
                    ev.output_summary = f"status={resp.status_code}, size={len(resp.text)} chars"
                    ev.details = {
                        "url": f"{self.mintlify_url}/llms.txt",
                        "status_code": resp.status_code,
                        "content_length": len(resp.text),
                    }
                    if resp.status_code != 200:
                        self.logger.warning("llms.txt returned %d", resp.status_code)
                        return []
            else:
                resp = await self._http.get(f"{self.mintlify_url}/llms.txt")
                if resp.status_code != 200:
                    self.logger.warning("llms.txt returned %d", resp.status_code)
                    return []
        except Exception:
            self.logger.exception("Failed to fetch llms.txt")
            return []

        llms_txt = resp.text

        # Ask LLM to pick the most relevant pages
        try:
            if trace:
                with trace.step(
                    f"OpenAI LLM call ({self.model})",
                    "llm_call",
                    input_summary=f"page selection, model={self.model}, llms_txt={len(llms_txt)} chars",
                ) as ev:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": PAGE_SELECTION_PROMPT},
                            {
                                "role": "user",
                                "content": (
                                    f"Query: {query}\n\n"
                                    f"llms.txt contents:\n{llms_txt}"
                                ),
                            },
                        ],
                        response_format={"type": "json_object"},
                    )
                    raw = response.choices[0].message.content.strip()
                    parsed = json.loads(raw)
                    urls = parsed.get("urls", [])
                    if isinstance(urls, list):
                        urls = [u for u in urls if isinstance(u, str)][: self.max_results]
                    else:
                        urls = []
                    ev.output_summary = f"{len(urls)} pages selected"
                    ev.details = {
                        "model": self.model,
                        "purpose": "page_selection",
                        "selected_urls": urls,
                        "raw_response": raw[:500],
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                            "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        },
                    }
                    return urls
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": PAGE_SELECTION_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Query: {query}\n\n"
                                f"llms.txt contents:\n{llms_txt}"
                            ),
                        },
                    ],
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content.strip()
                self.logger.debug("[Step 2 - Page Selection] LLM response: %s", raw)
                parsed = json.loads(raw)

                urls = parsed.get("urls", [])
                if isinstance(urls, list):
                    return [u for u in urls if isinstance(u, str)][: self.max_results]
                return []

        except Exception:
            self.logger.exception("Page selection LLM call failed")
            return []

    async def _fetch_pages(
        self,
        urls: list[str],
        trace: TraceCollector | None = None,
    ) -> list[dict]:
        """Fetch each page's markdown content by appending .md to the URL."""
        assert self._http is not None
        pages = []

        for page_url in urls:
            md_url = page_url.rstrip("/") + ".md"
            try:
                if trace:
                    with trace.step(
                        "HTTP fetch: doc page",
                        "http_fetch",
                        input_summary=f"GET {md_url}",
                    ) as ev:
                        resp = await self._http.get(md_url)
                        if resp.status_code == 200:
                            content = resp.text[:15_000]
                            pages.append(
                                {
                                    "content": content,
                                    "path": page_url,
                                    "title": page_url.split("/")[-1].replace("-", " ").title(),
                                }
                            )
                            ev.output_summary = f"OK, {len(content)} chars"
                            ev.details = {
                                "url": md_url,
                                "status_code": 200,
                                "content_length": len(content),
                                "title": pages[-1]["title"],
                            }
                        else:
                            ev.status = "error"
                            ev.output_summary = f"status={resp.status_code}"
                            ev.details = {
                                "url": md_url,
                                "status_code": resp.status_code,
                            }
                            self.logger.debug(
                                "Failed to fetch %s (status=%d)", md_url, resp.status_code
                            )
                else:
                    resp = await self._http.get(md_url)
                    if resp.status_code == 200:
                        content = resp.text[:15_000]
                        pages.append(
                            {
                                "content": content,
                                "path": page_url,
                                "title": page_url.split("/")[-1].replace("-", " ").title(),
                            }
                        )
                    else:
                        self.logger.debug(
                            "Failed to fetch %s (status=%d)", md_url, resp.status_code
                        )
            except Exception:
                self.logger.debug("Failed to fetch %s", md_url)

        return pages

    async def _synthesize(
        self,
        question: str,
        pages: list[dict],
        trace: TraceCollector | None = None,
    ) -> SkillAgentResponse:
        """Use OpenAI to synthesise a response from fetched documentation pages."""
        context_parts = []
        for i, page in enumerate(pages, 1):
            context_parts.append(
                f"--- Document {i}: {page['title']} ---\n"
                f"URL: {page['path']}\n"
                f"{page['content']}\n"
            )
        context_block = "\n".join(context_parts)

        try:
            if trace:
                with trace.step(
                    f"OpenAI LLM call ({self.model})",
                    "llm_call",
                    input_summary=f"doc synthesis, model={self.model}, {len(pages)} pages, {len(context_block)} chars",
                ) as ev:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": DOC_SYNTHESIS_PROMPT},
                            {
                                "role": "user",
                                "content": (
                                    f"Customer question: {question}\n\n"
                                    f"Documentation content:\n{context_block}"
                                ),
                            },
                        ],
                        response_format={"type": "json_object"},
                    )

                    synthesis_raw = response.choices[0].message.content
                    parsed = json.loads(synthesis_raw)
                    result = SkillAgentResponse(
                        answer_text=parsed.get("answer_text", ""),
                        confidence=float(parsed.get("confidence", 0.0)),
                        reasoning=f"[Doc Agent] {parsed.get('reasoning', '')}",
                        sources=parsed.get("sources", []),
                    )
                    ev.output_summary = f"confidence={result.confidence:.2f}"
                    ev.details = {
                        "model": self.model,
                        "purpose": "doc_synthesis",
                        "confidence": result.confidence,
                        "reasoning": result.reasoning,
                        "sources": result.sources,
                        "answer_preview": result.answer_text[:200],
                        "raw_response": synthesis_raw[:500],
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                            "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        },
                    }
                    return result
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": DOC_SYNTHESIS_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Customer question: {question}\n\n"
                                f"Documentation content:\n{context_block}"
                            ),
                        },
                    ],
                    response_format={"type": "json_object"},
                )

                synthesis_raw = response.choices[0].message.content
                self.logger.debug("[Step 4 - Synthesis] LLM response: %s", synthesis_raw)
                parsed = json.loads(synthesis_raw)
                return SkillAgentResponse(
                    answer_text=parsed.get("answer_text", ""),
                    confidence=float(parsed.get("confidence", 0.0)),
                    reasoning=f"[Doc Agent] {parsed.get('reasoning', '')}",
                    sources=parsed.get("sources", []),
                )

        except Exception:
            self.logger.exception("Doc synthesis failed")
            return SkillAgentResponse(
                answer_text="",
                confidence=0.0,
                reasoning="Doc synthesis encountered an error",
                sources=[],
            )
