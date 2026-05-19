"""OpenTelemetry SDK setup and exporter configuration.

App-wide infrastructure: configured once at app startup, used by every
layer (HTTP, agent service, gateway). The rest of the codebase only
calls `tracer.start_as_current_span(...)` and `meter.create_counter(...)`
through the OTel SDK directly — this package exists to bootstrap the
SDK and manage the exporter chain.

Q1: writes to corp endpoints via a custom exporter.
Q2-Q3: swap to OTLPSpanExporter pointing at the corp OTel endpoint.
"""