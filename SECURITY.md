# Security Policy

Eyohe OSINT is designed to run on an analyst's own machine or private network. It is **not**
intended to be exposed directly to the public Internet.

## Reporting a vulnerability
Open a private security advisory on GitHub ("Security" tab → "Report a vulnerability") or contact
the maintainer directly. Please include reproduction steps and the affected version/commit. You
should receive an acknowledgement within a few days.

## Scope
In scope: authentication/session handling, SSRF protections in `core/netsafety.py`, path handling
in the evidence vault and reports, secret redaction, injection in collectors/parsers, privilege
escalation between roles, and anything that lets the AI layer fetch or write beyond its tool
boundaries.

Out of scope: issues that require an attacker to already control the host or `.env`, and
rate-limit behaviour of third-party public services.

## Deployment guidance
Use PostgreSQL, set a long random `SECRET_KEY`, `COOKIE_SECURE=true` behind TLS (Caddy), keep
`ALLOW_PRIVATE_NETWORK_FETCH=false`, restrict network access to the UI/API, and never commit `.env`.
