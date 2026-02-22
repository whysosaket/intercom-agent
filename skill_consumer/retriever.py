"""BM25-based file retriever for skill documentation.

Builds an index at startup by reading all file content once, then
supports fast keyword-based retrieval at query time without re-reading files.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from skill_consumer.manifest import _classify_file, _derive_description, _parse_frontmatter

logger = logging.getLogger(__name__)


@dataclass
class IndexedDocument:
    """A single file stored in the BM25 index."""

    relative_path: str
    skill_name: str
    base_path: str
    file_type: str
    description: str
    content: str


@dataclass
class RetrievedFile:
    """A file returned by BM25 search with its relevance score."""

    relative_path: str
    skill_name: str
    base_path: str
    file_type: str
    description: str
    bm25_score: float


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric characters."""
    return [tok for tok in re.split(r"\W+", text.lower()) if tok]


class SkillRetriever:
    """BM25-based retriever that indexes skill files at startup."""

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self._index: BM25Okapi | None = None
        self._documents: list[IndexedDocument] = []

    def build_index(self) -> None:
        """Walk the skills directory, read all files, and build the BM25 index.

        Called once at startup. Each document's searchable text is a
        concatenation of path tokens, description, and file content.
        """
        skills_path = os.path.abspath(self.skills_dir)
        if not os.path.isdir(skills_path):
            logger.warning("Skills directory not found: %s", skills_path)
            return

        documents: list[IndexedDocument] = []
        corpus: list[list[str]] = []

        for entry in sorted(os.listdir(skills_path)):
            skill_path = os.path.join(skills_path, entry)
            if not os.path.isdir(skill_path):
                continue

            skill_md = os.path.join(skill_path, "SKILL.md")
            if not os.path.exists(skill_md):
                continue

            skill_name, _description = _parse_frontmatter(skill_md)
            skill_name = skill_name or entry

            for root, _dirs, filenames in os.walk(skill_path):
                for fname in sorted(filenames):
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, skill_path)

                    try:
                        with open(full_path, encoding="utf-8") as f:
                            content = f.read()
                    except Exception:
                        logger.warning("Could not read file for indexing: %s", full_path)
                        continue

                    description = _derive_description(rel_path, fname)
                    file_type = _classify_file(rel_path)

                    doc = IndexedDocument(
                        relative_path=rel_path,
                        skill_name=skill_name,
                        base_path=skill_path,
                        file_type=file_type,
                        description=description,
                        content=content,
                    )
                    documents.append(doc)

                    # Build searchable text: path tokens + description + content
                    path_text = rel_path.replace("/", " ").replace("-", " ").replace("_", " ")
                    searchable = f"{path_text} {description} {content}"
                    corpus.append(_tokenize(searchable))

        self._documents = documents

        if corpus:
            self._index = BM25Okapi(corpus)
            logger.info("BM25 index built: %d documents", len(documents))
        else:
            logger.warning("No documents found for BM25 index")

    def search(self, keywords: list[str], top_k: int = 10) -> list[RetrievedFile]:
        """Search the BM25 index with extracted keywords.

        Returns up to top_k files sorted by descending BM25 score.
        """
        if not self._index or not self._documents:
            return []

        query_tokens = _tokenize(" ".join(keywords))
        if not query_tokens:
            return []

        scores = self._index.get_scores(query_tokens)

        # Pair documents with scores, filter zero-score, sort descending
        scored = [
            (doc, score)
            for doc, score in zip(self._documents, scores)
            if score > 0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc, score in scored[:top_k]:
            results.append(
                RetrievedFile(
                    relative_path=doc.relative_path,
                    skill_name=doc.skill_name,
                    base_path=doc.base_path,
                    file_type=doc.file_type,
                    description=doc.description,
                    bm25_score=score,
                )
            )

        return results
