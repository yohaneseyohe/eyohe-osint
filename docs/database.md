# Database

PostgreSQL 16 (primary) or SQLite (development). SQLAlchemy 2 async models live in
`apps/api/eyohe/models/`; every schema change is an Alembic migration (`make migration m="…"`,
`make migrate`). UUID primary keys, timezone-aware timestamps, human display IDs from the
`id_sequences` counter table.

Tables: `users`, `sessions`, `api_tokens`, `audit_logs`, `system_settings`, `cases`, `targets`,
`notes`, `investigations`, `investigation_tasks`, `investigation_events`, `search_queries`,
`search_results`, `sources`, `source_snapshots`, `evidence`, `evidence_artifacts`, `entities`,
`entity_aliases`, `relationships`, `relationship_evidence`, `findings`, `finding_evidence`,
`timeline_events`, `reports`, `report_sections`, `monitors`, `alerts`, `id_sequences`.

Key indexes: `sources(case_id, canonical_url)` unique, `entities(case_id, type, normalized_value)`
unique, `relationships(case_id, source, target, type)` unique, `investigation_events(investigation_id,
seq)` unique, `search_results(case_id, canonical_url)`, plus created_at/display_id/domain/username
indexes. JSON columns are `JSONB` on PostgreSQL.

Backups: `make backup` (pg_dump custom format or SQLite copy + evidence/reports/screenshots) →
`backups/eyohe-<timestamp>.tar.gz`; `make restore f=…` restores after confirmation.
