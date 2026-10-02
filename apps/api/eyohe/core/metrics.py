"""Prometheus metrics (basic observability)."""

from prometheus_client import Counter, Gauge, Histogram

investigations_total = Counter("eyohe_investigations_total", "Investigations started")
investigations_active = Gauge("eyohe_investigations_active", "Investigations currently running")
sources_collected = Counter("eyohe_sources_collected_total", "Sources collected", ["collector"])
evidence_created = Counter("eyohe_evidence_created_total", "Evidence records created", ["collector"])
collector_errors = Counter("eyohe_collector_errors_total", "Collector errors", ["collector"])
search_requests = Counter("eyohe_search_requests_total", "Search provider requests", ["provider", "cache"])
ai_requests = Counter("eyohe_ai_requests_total", "Ollama requests", ["purpose", "outcome"])
report_generation_time = Histogram("eyohe_report_generation_seconds", "Report generation time", ["format"])
