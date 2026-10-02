"""Imports: previous case export (JSON package), CSV entities, plain IOC lists. All input is validated
and everything imported is attributed to the import (collector 'import:<filename>')."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, File, UploadFile, status

from eyohe.api.deps import DB, Analyst
from eyohe.core.enums import AuditAction, EntityType, EvidenceType, SourceType
from eyohe.core.errors import ValidationError
from eyohe.enrichment.classify import classify_target
from eyohe.services import cases as case_service
from eyohe.services import entities as ent_service
from eyohe.services import evidence as ev_service
from eyohe.services.audit import record_audit

router = APIRouter(tags=["imports"])
MAX_UPLOAD = 20 * 1024 * 1024
_IOC_TYPES = {
    EntityType.DOMAIN,
    EntityType.IP,
    EntityType.EMAIL,
    EntityType.URL,
    EntityType.CRYPTO_ADDRESS,
    EntityType.PHONE,
}


async def _read(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise ValidationError("Upload exceeds 20 MB.")
    return data


@router.post("/cases/{case_id}/import", status_code=status.HTTP_201_CREATED)
async def import_into_case(
    case_id: str, user: Analyst, db: DB, file: UploadFile = File(...), kind: str = "auto"
) -> dict[str, Any]:
    case = await case_service.get_case(db, case_id)
    raw = await _read(file)
    name = (file.filename or "upload")[:120]
    ctype = (file.content_type or "").lower()
    if kind == "auto":
        kind = (
            "json"
            if name.endswith(".json") or "json" in ctype
            else ("csv" if name.endswith(".csv") or "csv" in ctype else "ioc")
        )
    collector = f"import:{name}"
    stats: dict[str, Any] = {"entities": 0, "sources": 0, "evidence": 0, "skipped": 0, "kind": kind}
    text = raw.decode("utf-8", errors="replace")
    if kind == "json":
        try:
            pkg = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON: {exc}") from exc
        if not isinstance(pkg, dict) or "eyohe_export" not in pkg:
            raise ValidationError("Not an Eyohe export package (missing 'eyohe_export').")
        src_map: dict[str, Any] = {}
        for s in pkg.get("sources", [])[:5000]:
            if not isinstance(s, dict) or not s.get("url"):
                stats["skipped"] += 1
                continue
            try:
                st = SourceType(s.get("source_type", "OTHER"))
            except ValueError:
                st = SourceType.OTHER
            src = await ev_service.upsert_source(
                db,
                case.id,
                url=str(s["url"])[:4000],
                source_type=st,
                collector=collector,
                tier=int(s.get("tier", 5) or 5),
                title=str(s.get("title", ""))[:2000],
                publisher=str(s.get("publisher", ""))[:256],
                reliability_note=f"Imported from {name}; original collector {s.get('collector', '?')}",
            )
            src_map[str(s.get("display_id"))] = src
            stats["sources"] += 1
        for e in pkg.get("evidence", [])[:20000]:
            if not isinstance(e, dict) or not e.get("claim"):
                stats["skipped"] += 1
                continue
            try:
                et = EvidenceType(e.get("type", "DIRECT_STATEMENT"))
            except ValueError:
                et = EvidenceType.DIRECT_STATEMENT
            src_obj = src_map.get(str((e.get("source") or {}).get("id"))) if isinstance(e.get("source"), dict) else None
            await ev_service.create_evidence(
                db,
                case.id,
                claim=str(e["claim"])[:4000],
                evidence_type=et,
                collector=collector,
                source=src_obj,
                excerpt=str(e.get("excerpt", ""))[:4000],
                collection_method="import",
                structured={"imported_id": e.get("id")},
            )
            stats["evidence"] += 1
        for ent in pkg.get("entities", [])[:20000]:
            if not isinstance(ent, dict) or not ent.get("value"):
                stats["skipped"] += 1
                continue
            try:
                et2 = EntityType(ent.get("type", ""))
            except ValueError:
                stats["skipped"] += 1
                continue
            await ent_service.upsert_entity(
                db,
                case.id,
                et2,
                str(ent["value"])[:2000],
                label=str(ent.get("label", ""))[:256],
                attributes={"imported_from": name},
            )
            stats["entities"] += 1
    elif kind == "csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "value" not in [f.lower() for f in reader.fieldnames]:
            raise ValidationError("CSV needs a 'value' column (optional: 'type', 'label').")
        for row in list(reader)[:20000]:
            row = {k.lower(): v for k, v in row.items() if k}
            value = (row.get("value") or "").strip()
            if not value:
                stats["skipped"] += 1
                continue
            try:
                ent_type = EntityType(row["type"].upper()) if row.get("type") else _entity_type_for(value)
            except ValueError:
                stats["skipped"] += 1
                continue
            await ent_service.upsert_entity(
                db, case.id, ent_type, value, label=(row.get("label") or "")[:256], attributes={"imported_from": name}
            )
            stats["entities"] += 1
    else:  # plain IOC list: one indicator per line
        for line in text.splitlines()[:20000]:
            v = line.strip().split("#")[0].strip()
            if not v:
                continue
            try:
                ioc_type = _entity_type_for(v)
            except ValueError:
                stats["skipped"] += 1
                continue
            if ioc_type not in _IOC_TYPES:  # free text is not an indicator
                stats["skipped"] += 1
                continue
            await ent_service.upsert_entity(db, case.id, ioc_type, v, attributes={"imported_from": name, "ioc": True})
            stats["entities"] += 1
    await case_service.refresh_counts(db, case.id)
    await record_audit(
        db,
        AuditAction.IMPORT_COMPLETED,
        actor_id=user.id,
        actor_label=user.username,
        case_id=case.id,
        detail={"file": name, **stats},
    )
    await db.commit()
    return stats


def _entity_type_for(value: str) -> EntityType:
    from eyohe.core.enums import TargetType

    t, _, _ = classify_target(value)
    mapping = {
        TargetType.DOMAIN: EntityType.DOMAIN,
        TargetType.IP: EntityType.IP,
        TargetType.EMAIL: EntityType.EMAIL,
        TargetType.URL: EntityType.URL,
        TargetType.USERNAME: EntityType.USERNAME,
        TargetType.ORGANIZATION: EntityType.ORGANIZATION,
        TargetType.PERSON: EntityType.PERSON,
        TargetType.CRYPTO_ADDRESS: EntityType.CRYPTO_ADDRESS,
        TargetType.PHONE: EntityType.PHONE,
        TargetType.SOCIAL_ACCOUNT: EntityType.SOCIAL_ACCOUNT,
    }
    if t not in mapping:
        raise ValueError("unclassifiable")
    return mapping[t]
