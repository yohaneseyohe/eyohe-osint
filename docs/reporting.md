# Reporting

`POST /api/v1/reports {case_id, format}` queues generation; `GET /reports/{id}` shows status;
`/download` returns the file. Formats: `markdown`, `html`, `pdf` (WeasyPrint if installed, else
headless Chromium), `docx`.

Structure: cover (brand, case ID, date, analyst, classification) → Executive Summary →
Investigation Objective → Targets → Key Findings (ID, claim, assessment, computed confidence and
why, supporting and contradicting evidence IDs) → Entity Analysis → Relationship Graph → Timeline →
Technical Findings → Social / Public-Source Findings → Source Analysis → Evidence Index →
Limitations → Methodology (incl. task log) → References. Page footer: case ID, classification and
page numbers.

Language rules are enforced by the data model: technical records read as facts, third-party
statements as "According to …", allegations as "alleged", inference as "may indicate", and
anything unverifiable is labelled. Demo cases carry a **DEMO DATA** banner. Limitations are
generated from real task state (skipped/failed collectors, low-tier source share, unverified or
contradicted findings, unconfirmed identity claims).

Exports: `GET /cases/{id}/export?format=json|csv|graphml|markdown` (`kind=` for CSV). Imports:
`POST /cases/{id}/import` with a JSON package, a CSV (`value[,type,label]`) or a plain IOC list.
