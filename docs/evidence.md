# Evidence model

```
Source (EYO-SRC-…)  1─n  SourceSnapshot (text, hash, raw artifact in the vault)
   └─n Evidence (EYO-EV-…)  n─n  Finding (EYO-FND-…)      n─n  Relationship (EYO-REL-…)
         └─n EvidenceArtifact (screenshot / html / pdf …)
```

**Source**: URL (canonical form), type, domain, title, publisher/author, published and collected
timestamps, collector, **tier 1–5** and a reliability note. One row per canonical URL per case.

**Snapshot**: retrieval timestamp, HTTP status, content type, title, SHA-256 of the extracted text,
the text itself (bounded), and the raw artifact path in `data/evidence/{case}/snapshot/…`. Unchanged
re-fetches are marked `unchanged_since`.

**Evidence**: claim, verbatim excerpt (+ `excerpt_verified`), context, evidence type
(`DIRECT_STATEMENT`, `TECHNICAL_RECORD`, `DOCUMENT`, `PUBLIC_STATEMENT`, `ALLEGATION`,
`SYSTEM_INTERPRETATION`, `ARCHIVE_SNAPSHOT`, `SCREENSHOT`), collector + collection method, collected
and observed timestamps, computed initial confidence, review state (`PENDING`, `ACCEPTED`,
`REJECTED`, `NEEDS_VERIFICATION`), linked entity IDs, content hash, redaction flag. Observation
fields never change after creation; only review fields do.

**Source tiers**

| Tier | Meaning | Examples |
|---|---|---|
| 1 | official primary source | the target's own website |
| 2 | reputable secondary source | established news publications, Wikipedia |
| 3 | public technical database | DNS, RDAP, crt.sh, GitHub API, archives, documents |
| 4 | community discussion | Reddit, forums, social profiles |
| 5 | unverified | unknown search results, manual additions |

Low tiers are not "false": they require corroboration, and the confidence engine says so.

## Confidence engine (`verification/confidence.py`)

| Label | Rule |
|---|---|
| `CONTRADICTED` | contradicting evidence from a source as good as or better than the support; or analyst rejected |
| `CONFIRMED` | analyst accepted and a tier ≤ 2 source supports |
| `CORROBORATED` | ≥ 2 independent domains agree, best tier ≤ 3 |
| `SUPPORTED` | one tier ≤ 2 source, or ≥ 2 evidence records |
| `POSSIBLE` | a single tier 3–5 source |
| `INFERENCE` | only system interpretation |
| `UNVERIFIED` | nothing attached |

Identity claims (`POSSIBLY_SAME_ENTITY`, findings in category `identity`) are capped at `POSSIBLE`
until an analyst accepts them. The rationale returned by the engine powers the **Why?** view.

## Vault and retention

`data/evidence/{case_id}/{kind}/{sha256[:2]}/{sha256}.{ext}` with a `.meta.json` sidecar. Paths
are derived from identifiers only and checked against the vault root. `EVIDENCE_RETENTION_DAYS`
enables purging; `make backup` / `make restore` include the vault.
