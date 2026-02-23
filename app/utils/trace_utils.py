"""Shared utilities for trace serialization."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.chat.trace import TraceCollector

logger = logging.getLogger(__name__)


def safe_serialize_trace(trace: TraceCollector) -> list[dict]:
    """Serialize trace events, dropping non-serializable ones gracefully."""
    pipeline_trace = trace.serialize()
    safe_trace: list[dict] = []
    for i, event in enumerate(pipeline_trace):
        try:
            json.dumps(event)
            safe_trace.append(event)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Trace event %d (%s) not serializable: %s",
                i,
                event.get("label", "?"),
                exc,
            )
            safe_trace.append({
                "label": event.get("label", "unknown"),
                "call_type": event.get("call_type", "unknown"),
                "status": event.get("status", "completed"),
                "duration_ms": event.get("duration_ms", 0),
                "input_summary": event.get("input_summary", ""),
                "output_summary": event.get("output_summary", ""),
                "error_message": f"Trace serialization error: {exc}",
            })
    return safe_trace
