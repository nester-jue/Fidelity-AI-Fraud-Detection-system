"""Restore a NEXA backup, with explicit protection against accidental production overwrites."""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.services.db import get_database_url  # noqa: E402
from scripts.verify_backup import verify  # noqa: E402


def restore(backup_file: Path, target_url: str, confirm_production: bool = False) -> dict:
    target_url = target_url or os.getenv("DATABASE_URL") or get_database_url()
    production = settings.ENVIRONMENT.lower() == "production" or (
        "postgresql" in target_url and "localhost" not in target_url and "127.0.0.1" not in target_url
    )
    if production and not confirm_production:
        raise RuntimeError(
            "Refusing to restore into a production target without --confirm-production. "
            "Take a fresh backup and validate the change window first."
        )
    check = verify(backup_file)
    if target_url.startswith("sqlite"):
        target_path = target_url.split(":///", 1)[1]
        source = sqlite3.connect(backup_file)
        target = sqlite3.connect(target_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    else:
        result = subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--dbname", target_url, str(backup_file)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_restore failed: {result.stderr.strip()}")
    return {"restored_from": check, "target_dialect": "sqlite" if target_url.startswith("sqlite") else "postgresql"}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: python scripts/restore_db.py <backup-file> [target-url] [--confirm-production]", file=sys.stderr)
        sys.exit(2)
    confirm = "--confirm-production" in args
    args = [a for a in args if a != "--confirm-production"]
    result = restore(Path(args[0]), args[1] if len(args) > 1 else "", confirm)
    import json
    print(json.dumps(result, indent=2))
