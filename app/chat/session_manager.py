"""In-memory chat session management for the testing UI."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    confidence: float | None = None
    reasoning: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "sent"  # "sent", "pending_review", "approved", "rejected", "edited"


@dataclass
class ChatSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = field(
        default_factory=lambda: f"chat_test_{uuid.uuid4().hex[:8]}"
    )
    # Random user_id for Mem0 storage (each session is a separate "customer")
    user_id: str = field(
        default_factory=lambda: f"chat_user_{uuid.uuid4().hex[:8]}"
    )
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SessionManager:
    """Stores active chat sessions in memory."""

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}

    def create_session(self) -> ChatSession:
        session = ChatSession()
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[ChatSession]:
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None
