"""Base agent contract for the agentic architecture."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Standardized result from any agent invocation."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class BaseAgent(ABC):
    """Base class for all agents in the system.

    Provides a common interface, logging setup, and the pattern
    that all agents follow: receive a request, produce a result.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def initialize(self) -> None:
        """Async initialization (called during app lifespan startup)."""
        ...

    async def shutdown(self) -> None:
        """Optional cleanup (called during app lifespan shutdown)."""
        pass
