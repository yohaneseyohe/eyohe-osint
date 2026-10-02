"""Public web page screenshots via headless Chromium (fixed argv, no shell, temp profile, timeout).
Used only for pages that are already publicly retrievable; never to bypass access controls."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from eyohe.core.config import get_settings
from eyohe.core.db import utcnow
from eyohe.core.errors import ConfigurationError
from eyohe.core.netsafety import validate_url
from eyohe.services.vault import get_vault

VIEWPORT = (1440, 1800)


def _binary() -> str:
    s = get_settings()
    b = (
        s.chromium_path
        if Path(s.chromium_path).exists()
        else (shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome"))
    )
    if not b:
        raise ConfigurationError("Screenshots need Chromium (set CHROMIUM_PATH).")
    return b


async def capture(case_id: uuid.UUID, url: str) -> dict[str, Any]:
    await validate_url(url)
    binary = _binary()
    with tempfile.TemporaryDirectory(prefix="eyohe-shot-") as tmp:
        out = Path(tmp) / "shot.png"
        argv = [
            binary,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            f"--user-data-dir={tmp}/profile",
            f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}",
            f"--screenshot={out}",
            "--timeout=30000",
            url,
        ]
        proc = await asyncio.create_subprocess_exec(*argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=60)
        except TimeoutError:
            proc.kill()
            raise ConfigurationError("Screenshot timed out after 60s.") from None
        if proc.returncode != 0 or not out.exists():
            raise ConfigurationError(f"Chromium screenshot failed: {err.decode(errors='replace')[-200:]}")
        data = out.read_bytes()
    desc = get_vault().store(
        case_id,
        data,
        "image/png",
        kind="screenshot",
        original_url=url,
        metadata={
            "browser": Path(binary).name,
            "viewport": f"{VIEWPORT[0]}x{VIEWPORT[1]}",
            "captured_at": utcnow().isoformat(),
        },
    )
    return {**desc, "browser": Path(binary).name, "viewport": f"{VIEWPORT[0]}x{VIEWPORT[1]}", "captured_at": utcnow()}
