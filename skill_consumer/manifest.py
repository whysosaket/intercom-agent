"""Builds a lightweight file manifest from the skills/ directory.

The manifest lists all available files with brief descriptions so the LLM
can decide which files to read without loading their full content.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillFile:
    """Metadata about a single file within a skill."""

    relative_path: str  # e.g. "references/mem0-platform/add-memory.md"
    description: str  # brief description from filename or SKILL.md
    file_type: str  # "reference", "script", "example", "manifest", "other"
    size_bytes: int


@dataclass
class SkillManifest:
    """Registry of all files within a single skill."""

    name: str
    description: str
    base_path: str  # absolute path to skill directory
    files: list[SkillFile] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Format manifest for inclusion in an LLM prompt."""
        lines = [
            f"# Skill: {self.name}",
            f"Description: {self.description}",
            "",
            "## Available Files:",
        ]
        for f in self.files:
            lines.append(
                f"- [{f.file_type}] {f.relative_path} ({f.size_bytes} bytes) -- {f.description}"
            )
        return "\n".join(lines)


def build_manifest(skills_dir: str) -> dict[str, SkillManifest]:
    """Scan the skills/ directory and build manifests for all skills.

    A skill is identified by a directory containing a SKILL.md file.
    """
    skills_path = os.path.abspath(skills_dir)
    manifests: dict[str, SkillManifest] = {}

    if not os.path.isdir(skills_path):
        logger.warning("Skills directory not found: %s", skills_path)
        return manifests

    for entry in sorted(os.listdir(skills_path)):
        skill_path = os.path.join(skills_path, entry)
        if not os.path.isdir(skill_path):
            continue

        skill_md = os.path.join(skill_path, "SKILL.md")
        if not os.path.exists(skill_md):
            continue

        name, description = _parse_frontmatter(skill_md)

        manifest = SkillManifest(
            name=name or entry,
            description=description or "",
            base_path=skill_path,
        )

        # Walk all files in the skill directory
        for root, _dirs, filenames in os.walk(skill_path):
            for fname in sorted(filenames):
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, skill_path)
                manifest.files.append(
                    SkillFile(
                        relative_path=rel_path,
                        description=_derive_description(rel_path, fname),
                        file_type=_classify_file(rel_path),
                        size_bytes=os.path.getsize(full_path),
                    )
                )

        manifests[entry] = manifest
        logger.info(
            "Built manifest for skill '%s': %d files", manifest.name, len(manifest.files)
        )

    return manifests


def _parse_frontmatter(skill_md_path: str) -> tuple[str, str]:
    """Extract name and description from YAML frontmatter."""
    with open(skill_md_path, encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return "", ""

    end = content.find("---", 3)
    if end == -1:
        return "", ""

    try:
        frontmatter = yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        logger.warning("Failed to parse YAML in %s", skill_md_path)
        return "", ""

    return frontmatter.get("name", ""), frontmatter.get("description", "")


def _classify_file(rel_path: str) -> str:
    """Classify a file based on its path within the skill directory."""
    if rel_path == "SKILL.md":
        return "manifest"
    if rel_path.startswith("scripts/"):
        return "script"
    if "tools/" in rel_path and rel_path.endswith(".py"):
        return "example"
    if rel_path.startswith("references/") and rel_path.endswith(".md"):
        return "reference"
    return "other"


def _derive_description(rel_path: str, fname: str) -> str:
    """Derive a brief description from the filename."""
    stem = os.path.splitext(fname)[0]
    return stem.replace("-", " ").replace("_", " ").title()
