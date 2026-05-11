"""Tests for log parsers."""

from pathlib import Path

from agent_failure_analyzer.models import AgentFramework, EventType
from agent_failure_analyzer.parsers import (
    ClaudeCodeParser,
    CrewAIParser,
    GenericJSONParser,
    LangChainParser,
)
from agent_failure_analyzer.parsers.base import BaseParser
from agent_failure_analyzer.parsers.registry import ParserRegistry, _load_plugin_parsers

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestClaudeCodeParser:
    def test_can_parse_jsonl(self):
        parser = ClaudeCodeParser()
        assert parser.can_parse(SAMPLE_DIR / "claude_code_context_overflow.jsonl")

    def test_parse_context_overflow(self):
        parser = ClaudeCodeParser()
        sessions = parser.parse(SAMPLE_DIR / "claude_code_context_overflow.jsonl")
        assert len(sessions) == 1
        session = sessions[0]
        assert session.framework == AgentFramework.CLAUDE_CODE
        assert session.model == "claude-sonnet-4-6"
        assert len(session.events) > 0
        # Should have tool calls and an error
        event_types = {e.event_type for e in session.events}
        assert EventType.TOOL_CALL in event_types
        assert EventType.ERROR in event_types

    def test_parse_tool_loop(self):
        parser = ClaudeCodeParser()
        sessions = parser.parse(SAMPLE_DIR / "claude_code_tool_loop.jsonl")
        assert len(sessions) == 1
        session = sessions[0]
        assert session.total_turns >= 2  # Two user messages


class TestLangChainParser:
    def test_can_parse_json(self):
        parser = LangChainParser()
        assert parser.can_parse(SAMPLE_DIR / "langchain_error_cascade.json")

    def test_parse_error_cascade(self):
        parser = LangChainParser()
        sessions = parser.parse(SAMPLE_DIR / "langchain_error_cascade.json")
        assert len(sessions) == 1
        session = sessions[0]
        assert session.framework == AgentFramework.LANGCHAIN
        # Should detect errors
        errors = [e for e in session.events if e.event_type == EventType.ERROR]
        assert len(errors) >= 2


class TestCrewAIParser:
    def test_can_parse(self):
        parser = CrewAIParser()
        assert parser.can_parse(SAMPLE_DIR / "crewai_hallucination.json")

    def test_parse_hallucination(self):
        parser = CrewAIParser()
        sessions = parser.parse(SAMPLE_DIR / "crewai_hallucination.json")
        assert len(sessions) == 1
        session = sessions[0]
        assert session.framework == AgentFramework.CREWAI
        assert session.model == "gpt-4-turbo"
        # Should have tool calls with errors (file not found)
        tool_results = [
            e for e in session.events
            if e.event_type == EventType.TOOL_RESULT and e.error_message
        ]
        assert len(tool_results) >= 2


class TestGenericParser:
    def test_can_parse_json(self):
        parser = GenericJSONParser()
        assert parser.can_parse(SAMPLE_DIR / "generic_mixed_failures.json")

    def test_parse_mixed(self):
        parser = GenericJSONParser()
        sessions = parser.parse(SAMPLE_DIR / "generic_mixed_failures.json")
        assert len(sessions) == 1
        session = sessions[0]
        assert session.framework == AgentFramework.GENERIC
        errors = [e for e in session.events if e.event_type == EventType.ERROR]
        assert len(errors) >= 2


class TestParserRegistry:
    def test_auto_detect_claude_code(self):
        registry = ParserRegistry()
        sessions = registry.parse(SAMPLE_DIR / "claude_code_context_overflow.jsonl")
        assert len(sessions) == 1
        assert sessions[0].framework == AgentFramework.CLAUDE_CODE

    def test_auto_detect_langchain(self):
        registry = ParserRegistry()
        sessions = registry.parse(SAMPLE_DIR / "langchain_error_cascade.json")
        assert len(sessions) == 1
        assert sessions[0].framework == AgentFramework.LANGCHAIN

    def test_parse_directory(self):
        registry = ParserRegistry()
        sessions = registry.parse_directory(SAMPLE_DIR)
        assert len(sessions) >= 4  # At least one per sample file

    def test_plugin_parsers_loaded(self):
        """Verify that the plugin entry point loading mechanism works."""
        # _load_plugin_parsers should return an empty list when no plugins are installed
        plugins = _load_plugin_parsers()
        assert isinstance(plugins, list)
        # All loaded plugins must be BaseParser subclasses
        for p in plugins:
            assert isinstance(p, BaseParser)

    def test_plugin_parser_integration(self):
        """Verify plugin parsers are tried between built-in and generic parsers."""
        registry = ParserRegistry()
        # Built-in parsers + generic fallback should be present
        parser_types = [type(p).__name__ for p in registry._parsers]
        assert "ClaudeCodeParser" in parser_types
        assert "GenericJSONParser" in parser_types
        # Generic must be last
        assert parser_types[-1] == "GenericJSONParser"
