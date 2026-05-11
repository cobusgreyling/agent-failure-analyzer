"""
Core data models for agent session analysis.

All parsers normalize into these models before analysis.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .taxonomy import FailureCategory, FailureSubcategory, Severity


class AgentFramework(str, Enum):
    """Supported agent frameworks."""

    CLAUDE_CODE = "claude_code"
    LANGCHAIN = "langchain"
    CREWAI = "crewai"
    AUTOGEN = "autogen"
    GENERIC = "generic"


class EventType(str, Enum):
    """Types of events within an agent session."""

    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    SYSTEM = "system"
    THINKING = "thinking"


class SessionEvent(BaseModel):
    """A single event within an agent session."""

    timestamp: datetime | None = None
    event_type: EventType
    content: str = ""
    tool_name: str | None = None
    tool_args: dict | None = None
    token_count: int | None = None
    error_message: str | None = None
    metadata: dict = Field(default_factory=dict)


class FailureInstance(BaseModel):
    """A single classified failure within a session."""

    category: FailureCategory
    subcategory: FailureSubcategory
    severity: Severity
    description: str
    evidence: list[str] = Field(default_factory=list)
    event_indices: list[int] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class SessionOutcome(str, Enum):
    """Overall outcome of the session."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class AgentSession(BaseModel):
    """A complete agent session, normalized from any framework."""

    session_id: str
    framework: AgentFramework
    model: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    events: list[SessionEvent] = Field(default_factory=list)
    outcome: SessionOutcome = SessionOutcome.UNKNOWN
    total_tokens: int | None = None
    total_turns: int | None = None
    metadata: dict = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Complete analysis of a single session."""

    session: AgentSession
    failures: list[FailureInstance] = Field(default_factory=list)
    summary: str = ""
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    analyzed_at: datetime = Field(default_factory=datetime.now)


class BatchAnalysisResult(BaseModel):
    """Analysis across multiple sessions."""

    results: list[AnalysisResult] = Field(default_factory=list)
    total_sessions: int = 0
    failed_sessions: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    framework_counts: dict[str, int] = Field(default_factory=dict)
    top_failures: list[tuple[str, int]] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.now)
