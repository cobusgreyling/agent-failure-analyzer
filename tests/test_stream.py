"""Tests for the stream module."""

from io import StringIO

from rich.console import Console

from agent_failure_analyzer.models import EventType
from agent_failure_analyzer.stream import _parse_event, stream_analyze


class TestParseEvent:
    def test_user_message(self):
        event = _parse_event('{"role": "user", "content": "Hello"}')
        assert event is not None
        assert event.event_type == EventType.USER_MESSAGE
        assert event.content == "Hello"

    def test_assistant_message(self):
        event = _parse_event('{"role": "assistant", "content": "Hi there"}')
        assert event is not None
        assert event.event_type == EventType.ASSISTANT_MESSAGE

    def test_tool_result(self):
        event = _parse_event('{"role": "tool", "content": "file contents"}')
        assert event is not None
        assert event.event_type == EventType.TOOL_RESULT

    def test_error_event(self):
        event = _parse_event('{"error": "something broke", "content": "fail"}')
        assert event is not None
        assert event.event_type == EventType.ERROR
        assert event.error_message == "something broke"

    def test_tool_call_event(self):
        event = _parse_event('{"tool_call": true, "content": "run test", "tool_name": "Bash"}')
        assert event is not None
        assert event.event_type == EventType.TOOL_CALL
        assert event.tool_name == "Bash"

    def test_invalid_json(self):
        event = _parse_event("not json at all")
        assert event is None

    def test_empty_line(self):
        event = _parse_event("")
        assert event is None

    def test_non_dict_json(self):
        event = _parse_event("[1, 2, 3]")
        assert event is None

    def test_content_as_dict(self):
        event = _parse_event('{"role": "assistant", "content": {"text": "hello"}}')
        assert event is not None
        assert "hello" in event.content


class TestStreamAnalyze:
    def test_stream_with_events(self):
        input_data = StringIO(
            '{"role": "user", "content": "Fix the bug"}\n'
            '{"role": "assistant", "content": "Looking at it"}\n'
            '{"role": "tool", "content": "error: file not found", "error": "not found"}\n'
        )
        err_buf = StringIO()
        console = Console(file=err_buf, no_color=True, width=100)
        stream_analyze(input_stream=input_data, console=console)
        output = err_buf.getvalue()
        assert "Stream complete" in output
        assert "3 events" in output

    def test_stream_empty(self):
        input_data = StringIO("")
        err_buf = StringIO()
        console = Console(file=err_buf, no_color=True, width=100)
        stream_analyze(input_stream=input_data, console=console)
        output = err_buf.getvalue()
        assert "0 events" in output
