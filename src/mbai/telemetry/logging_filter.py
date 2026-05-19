"""Logging filter that injects OTel trace/span IDs into log records.

Attach to any logger to make its records trace-correlated. Adds two
attributes to each record: `trace_id` and `span_id` (hex strings) when
an OTel span is active, empty strings otherwise. The filter never
blocks a record.
"""

from __future__ import annotations

import logging

from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""
        return True