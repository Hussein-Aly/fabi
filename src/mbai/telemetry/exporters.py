"""Custom OpenTelemetry span exporters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
)

class JsonlFileSpanExporter(SpanExporter):
    """Append one JSON-encoded span per line to a file.

    Suitable for local dev (tail/grep/jq) and for the OTel Collector
    sidecar pattern (filelog receiver reads the same file).

    The file is opened in append mode, line-buffered. Multiple span
    processor flushes append cleanly because each write is one line.
    """

    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        # Line-buffered append. Each span is one write of one '\n'-terminated line.
        self._file = self._file_path.open("a", buffering=1, encoding="utf-8")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            for span in spans:
                # OTel SDK provides to_json() returning a (multi-line, pretty) JSON
                # string. We compact it onto one line.
                line = json.dumps(json.loads(span.to_json()), separators=(",", ":"))
                self._file.write(line + "\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        try:
            self._file.flush()
        except Exception:
            return False
        return True


class JsonlFileMetricExporter(MetricExporter):
    """Append one JSON-encoded metrics snapshot per line to a file.

    OTel metrics are exported as periodic snapshots (default every 60s)
    containing all current instrument values. Each snapshot is written
    as a single JSONL line.
    """

    def __init__(self, file_path: str | Path) -> None:
        super().__init__()
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._file_path.open("a", buffering=1, encoding="utf-8")

    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10_000,
        **kwargs,
    ) -> MetricExportResult:
        try:
            line = json.dumps(
                json.loads(metrics_data.to_json()),
                separators=(",", ":"),
            )
            self._file.write(line + "\n")
            return MetricExportResult.SUCCESS
        except Exception:
            return MetricExportResult.FAILURE

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        try:
            self._file.flush()
        except Exception:
            return False
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        try:
            self._file.close()
        except Exception:
            pass

class FilteringSpanExporter(SpanExporter):
    """Wraps another exporter, dropping spans whose name matches any
    of the excluded regex patterns before delegating."""

    def __init__(self, inner: SpanExporter, exclude_patterns: list[str]) -> None:
        self._inner = inner
        self._patterns = [re.compile(p) for p in exclude_patterns]

    def export(self, spans):
        kept = [s for s in spans if not any(p.search(s.name) for p in self._patterns)]
        if not kept:
            return SpanExportResult.SUCCESS
        return self._inner.export(kept)

    def force_flush(self, timeout_millis=30_000):
        return self._inner.force_flush(timeout_millis)

    def shutdown(self):
        self._inner.shutdown()