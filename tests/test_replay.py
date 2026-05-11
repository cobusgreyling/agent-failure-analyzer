"""Tests for the replay module."""

from io import StringIO

from rich.console import Console

from agent_failure_analyzer.models import (
    AgentFramework,
    AgentSession,
    AnalysisResult,
    EventType,
    FailureInstance,
    SessionEvent,
    SessionOutcome,
)
from agent_failure_analyzer.replay import SessionReplay
from agent_failure_analyzer.taxonomy import (
    FailureCategory,
    FailureSubcategory,
    Severity,
)


def _make_result():
    events = [
        SessionEvent(event_type=EventType.USER_MESSAGE, content="Fix the bug"),
        SessionEvent(
            event_type=EventType.TOOL_CALL,
            content="cat file.py",
            tool_name="Bash",
        ),
        SessionEvent(
            event_type=EventType.TOOL_RESULT,
            content="file not found",
            error_message="No such file: file.py",
        ),
        SessionEvent(
            event_type=EventType.ASSISTANT_MESSAGE,
            content="The file doesn't exist",
        ),
    ]
    failures = [
        FailureInstance(
            category=FailureCategory.HALLUCINATION,
            subcategory=FailureSubcategory.FABRICATED_FILE_PATH,
            severity=Severity.HIGH,
            description="Referenced non-existent file",
            event_indices=[1, 2],
            confidence=0.9,
        ),
    ]
    session = AgentSession(
        session_id="replay-test",
        framework=AgentFramework.GENERIC,
        events=events,
        outcome=SessionOutcome.FAILURE,
    )
    return AnalysisResult(session=session, failures=failures, risk_score=0.6)


class TestSessionReplay:
    def test_init(self):
        result = _make_result()
        replay = SessionReplay(result)
        assert replay.current == 0
        assert len(replay.events) == 4

    def test_failure_map_built(self):
        result = _make_result()
        replay = SessionReplay(result)
        # Events 1 and 2 should have failure annotations
        assert 1 in replay._failure_map
        assert 2 in replay._failure_map
        assert 0 not in replay._failure_map

    def test_render_event(self):
        result = _make_result()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=100)
        replay = SessionReplay(result, console=console)
        panel = replay._render_event(0)
        assert panel is not None

    def test_render_event_with_failure(self):
        result = _make_result()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=100)
        replay = SessionReplay(result, console=console)
        # Event index 1 has a failure annotation
        panel = replay._render_event(1)
        assert panel.border_style == "red"

    def test_render_clean_event(self):
        result = _make_result()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=100)
        replay = SessionReplay(result, console=console)
        # Event index 0 has no failure
        panel = replay._render_event(0)
        assert panel.border_style == "blue"

    def test_static_print(self):
        result = _make_result()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=100)
        replay = SessionReplay(result, console=console)
        replay._print_static()
        output = buf.getvalue()
        assert len(output) > 0

    def test_empty_session(self):
        session = AgentSession(
            session_id="empty",
            framework=AgentFramework.GENERIC,
            events=[],
            outcome=SessionOutcome.UNKNOWN,
        )
        result = AnalysisResult(session=session, failures=[], risk_score=0.0)
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=100)
        replay = SessionReplay(result, console=console)
        replay.run()
        output = buf.getvalue()
        assert "No events" in output
