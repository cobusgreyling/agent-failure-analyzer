"""
OpenTelemetry exporter for analysis results.

Exports failure analysis as OTLP spans and metrics, enabling integration
with observability platforms like Grafana, Datadog, Honeycomb, etc.

Requires: pip install agent-failure-analyzer[otel]
"""

from __future__ import annotations

from typing import Any

from ..models import AnalysisResult, BatchAnalysisResult


class OTLPExporter:
    """Export analysis results as OpenTelemetry spans and metrics."""

    def __init__(
        self,
        service_name: str = "agent-failure-analyzer",
        endpoint: str | None = None,
    ) -> None:
        self.service_name = service_name
        self.endpoint = endpoint
        self._tracer = None
        self._meter = None

    def _setup(self) -> None:
        """Lazy-init OpenTelemetry SDK."""
        try:
            from opentelemetry import metrics, trace
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            raise ImportError(
                "OpenTelemetry packages are required for OTLP export. "
                "Install with: pip install agent-failure-analyzer[otel]"
            )

        resource = Resource.create({"service.name": self.service_name})

        # Traces
        exporter_kwargs: dict[str, Any] = {}
        if self.endpoint:
            exporter_kwargs["endpoint"] = self.endpoint

        span_exporter = OTLPSpanExporter(**exporter_kwargs)
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)
        self._tracer = trace.get_tracer("afa")

        # Metrics
        metric_exporter = OTLPMetricExporter(**exporter_kwargs)
        reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
        self._meter = metrics.get_meter("afa")

        self._failure_counter = self._meter.create_counter(
            "afa.failures",
            description="Number of detected agent failures",
        )
        self._risk_histogram = self._meter.create_histogram(
            "afa.risk_score",
            description="Risk score distribution across sessions",
        )
        self._session_counter = self._meter.create_counter(
            "afa.sessions_analyzed",
            description="Total sessions analyzed",
        )

    def export_result(self, result: AnalysisResult) -> None:
        """Export a single analysis result as an OTLP span with metrics."""
        if self._tracer is None:
            self._setup()

        assert self._tracer is not None
        assert self._meter is not None

        session = result.session
        attrs = {
            "afa.session_id": session.session_id,
            "afa.framework": session.framework.value,
            "afa.outcome": session.outcome.value,
            "afa.risk_score": result.risk_score,
            "afa.failure_count": len(result.failures),
        }
        if session.model:
            attrs["afa.model"] = session.model
        if session.total_tokens:
            attrs["afa.total_tokens"] = session.total_tokens

        with self._tracer.start_as_current_span("afa.analysis", attributes=attrs) as span:
            for failure in result.failures:
                span.add_event(
                    "failure_detected",
                    attributes={
                        "category": failure.category.value,
                        "subcategory": failure.subcategory.value,
                        "severity": failure.severity.value,
                        "confidence": failure.confidence,
                        "description": failure.description[:200],
                    },
                )

                self._failure_counter.add(
                    1,
                    {
                        "category": failure.category.value,
                        "severity": failure.severity.value,
                        "framework": session.framework.value,
                    },
                )

        self._risk_histogram.record(
            result.risk_score,
            {"framework": session.framework.value},
        )
        self._session_counter.add(
            1,
            {"framework": session.framework.value, "outcome": session.outcome.value},
        )

    def export_batch(self, batch: BatchAnalysisResult) -> None:
        """Export all results from a batch analysis."""
        for result in batch.results:
            self.export_result(result)

    def shutdown(self) -> None:
        """Flush and shut down exporters."""
        try:
            from opentelemetry import metrics, trace

            provider = trace.get_tracer_provider()
            if hasattr(provider, "shutdown"):
                provider.shutdown()

            meter_provider = metrics.get_meter_provider()
            if hasattr(meter_provider, "shutdown"):
                meter_provider.shutdown()
        except Exception:
            pass
