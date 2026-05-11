"""Tests for the dashboard app."""

from pathlib import Path

from agent_failure_analyzer.dashboard.app import create_app

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestDashboardApp:
    def test_create_app(self):
        app = create_app(SAMPLE_DIR)
        assert app is not None
        assert app.title == "Agent Failure Analyzer"

    def test_routes_exist(self):
        app = create_app(SAMPLE_DIR)
        route_paths = [r.path for r in app.routes]
        assert "/" in route_paths
        assert "/api/report" in route_paths
