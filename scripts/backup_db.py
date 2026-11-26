"""Create a verified, checksummed database backup.

SQLite: uses sqlite3's online backup API (safe while the app is running).
PostgreSQL: uses pg_dump in custom format. Never prints credentials.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.services.db import get_database_url  # noqa: E402


def _sqlite_path(url: str) -> str:
    return url.split(":///", 1)[1]


def backup(output_dir: str) -> dict:
    url = os.getenv("DATABASE_URL") or get_database_url()
    destination_dir = Path(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if url.startswith("sqlite"):
        destination = destination_dir / f"nexa-sqlite-{stamp}.sqlite"
        source = sqlite3.connect(_sqlite_path(url))
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        check = sqlite3.connect(destination).execute("PRAGMA integrity_check").fetchone()[0]
        dialect = "sqlite"
    else:
        destination = destination_dir / f"nexa-postgres-{stamp}.dump"
        # pg_dump accepts a libpq connection URI directly; the URI is passed
        # as an argument, not echoed, so credentials never reach the logs.
        result = subprocess.run(
            ["pg_dump", "--format=custom", "--dbname", url, "--file", str(destination)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr.strip()}")
        listing = subprocess.run(
            ["pg_restore", "--list", str(destination)], capture_output=True, text=True
        )
        if listing.returncode != 0 or not listing.stdout.strip():
            raise RuntimeError("pg_dump output could not be listed by pg_restore")
        check = "pg_restore_list_ok"
        dialect = "postgresql"

    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dialect": dialect,
        "file": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": digest,
        "integrity_check": check,
        "environment": settings.ENVIRONMENT,
    }
    Path(str(destination) + ".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "backups")
    print(json.dumps(backup(directory), indent=2))
