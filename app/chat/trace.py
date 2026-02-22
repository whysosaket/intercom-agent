"""Pipeline trace collector for the chat testing UI.

Provides a lightweight mechanism for agents to report sub-step traces
(individual LLM calls, Mem0 searches, HTTP fetches, etc.) during pipeline
execution. The router creates a TraceCollector per request, passes it to
agents, and serializes all collected events into the WebSocket response.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _safe_json_value(obj: object) -> object:
    """Recursively convert an object to JSON-safe primitives.

    Mem0/OpenAI may return pydantic models or other non-serializable objects
    inside the details dict. This ensures everything survives ``json.dumps``.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_json_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json_value(item) for item in obj]
    # Fallback: try to convert pydantic / dataclass / arbitrary objects
    if hasattr(obj, "model_dump"):
        return _safe_json_value(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return _safe_json_value(vars(obj))
    return str(obj)


@dataclass
class TraceEvent:
    """A single trace event (sub-step) within a pipeline step."""

    label: str  # e.g. "Mem0 Search: conversation history"
    call_type: str  # "mem0_search", "llm_call", "http_fetch", "computation"
    status: str = "completed"  # "completed", "skipped", "error"
    duration_ms: int = 0
    input_summary: str = ""  # brief description of input
    output_summary: str = ""  # brief description of output
    details: dict = field(default_factory=dict)  # arbitrary extra data
    error_message: str = ""

    def to_dict(self) -> dict:
        d = {
            "label": self.label,
            "call_type": self.call_type,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }
        if self.input_summary:
            d["input_summary"] = self.input_summary
        if self.output_summary:
            d["output_summary"] = self.output_summary
        if self.details:
            d["details"] = _safe_json_value(self.details)
        if self.error_message:
            d["error_message"] = self.error_message
        return d


class TraceCollector:
    """Collects trace events from agents during a single pipeline run.

    Usage in router:
        trace = TraceCollector()
        result = await agent.generate(..., trace=trace)
        ws_payload["pipeline_trace"] = trace.serialize()

    Usage in agents:
        with trace.step("Mem0 Search: history", "mem0_search") as ev:
            results = self.memzero.search(...)
            ev.output_summary = f"{len(results)} results"
            ev.details = {"results": results[:3]}
    """

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._start_time: float = time.monotonic()

    @contextmanager
    def step(
        self,
        label: str,
        call_type: str,
        input_summary: str = "",
    ):
        """Context manager that times a sub-step and captures its trace.

        Yields the TraceEvent so the caller can populate output_summary,
        details, etc. before the context exits.
        """
        event = TraceEvent(
            label=label,
            call_type=call_type,
            input_summary=input_summary,
        )
        t0 = time.monotonic()
        try:
            yield event
            event.status = "completed"
        except Exception as exc:
            event.status = "error"
            event.error_message = str(exc)
            raise
        finally:
            event.duration_ms = round((time.monotonic() - t0) * 1000)
            self._events.append(event)

    def add_event(self, event: TraceEvent) -> None:
        """Directly add a pre-built trace event."""
        self._events.append(event)

    @property
    def total_duration_ms(self) -> int:
        return round((time.monotonic() - self._start_time) * 1000)

    def serialize(self) -> list[dict]:
        """Serialize all events to a list of dicts for JSON transport."""
        return [ev.to_dict() for ev in self._events]

    def __bool__(self) -> bool:
        """Always truthy so ``if trace:`` checks work even with 0 events."""
        return True

    def __len__(self) -> int:
        return len(self._events)
