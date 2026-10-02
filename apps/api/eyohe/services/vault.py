"""Evidence vault: content-addressed artifact storage under DATA_DIR/evidence/{case_id}/.

Paths are derived from identifiers only, never from user-supplied names, and are verified to stay
inside the vault root (path traversal protection).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from eyohe.core.config import get_settings
from eyohe.core.db import utcnow
from eyohe.core.security import sha256_bytes

_EXT = {
    "text/html": ".html",
    "application/json": ".json",
    "text/plain": ".txt",
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/markdown": ".md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


class EvidenceVault:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_settings().data_dir / "evidence").resolve()

    def _case_dir(self, case_id: uuid.UUID | str) -> Path:
        d = (self.root / str(uuid.UUID(str(case_id)))).resolve()
        if not d.is_relative_to(self.root):
            raise ValueError("vault path escaped root")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store(
        self,
        case_id: uuid.UUID | str,
        content: bytes,
        mime_type: str,
        *,
        kind: str,
        original_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store bytes and a sidecar metadata JSON. Returns artifact descriptor."""
        digest = sha256_bytes(content)
        ext = _EXT.get(mime_type.split(";")[0].strip(), ".bin")
        case_dir = self._case_dir(case_id)
        sub = case_dir / kind
        sub.mkdir(exist_ok=True)
        path = sub / f"{digest[:2]}" / f"{digest}{ext}"
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
            meta = {
                "sha256": digest,
                "mime_type": mime_type,
                "kind": kind,
                "size_bytes": len(content),
                "original_url": original_url,
                "created_at": utcnow().isoformat(),
                **(metadata or {}),
            }
            path.with_suffix(path.suffix + ".meta.json").write_text(json.dumps(meta, indent=2, default=str))
        rel = path.relative_to(self.root)
        return {
            "path": str(rel),
            "sha256": digest,
            "mime_type": mime_type,
            "size_bytes": len(content),
            "kind": kind,
            "original_url": original_url,
            "created_at": utcnow(),
        }

    def resolve(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError("artifact path escaped vault root")
        return p

    def read(self, rel_path: str) -> bytes:
        return self.resolve(rel_path).read_bytes()

    def delete_case(self, case_id: uuid.UUID | str) -> int:
        import shutil

        d = self._case_dir(case_id)
        n = sum(1 for _ in d.rglob("*") if _.is_file())
        shutil.rmtree(d, ignore_errors=True)
        return n

    def purge_older_than(self, cutoff: datetime) -> int:
        n = 0
        for f in self.root.rglob("*"):
            if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime, tz=cutoff.tzinfo) < cutoff:
                f.unlink(missing_ok=True)
                n += 1
        return n


def get_vault() -> EvidenceVault:
    return EvidenceVault()
