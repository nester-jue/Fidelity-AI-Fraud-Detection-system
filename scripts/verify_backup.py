"""Verify a NEXA backup file and its optional JSON manifest."""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def verify(path: Path, expected_hash: str | None = None) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = Path(str(path) + ".json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != digest:
            raise ValueError("Backup checksum does not match its manifest")
        expected_hash = expected_hash or manifest.get("sha256")
    if expected_hash and digest != expected_hash:
        raise ValueError("Backup checksum does not match the supplied hash")

    if path.suffix == ".sqlite":
        result = sqlite3.connect(path).execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"SQLite integrity check failed: {result}")
        integrity = result
    else:
        listing = subprocess.run(
            ["pg_restore", "--list", str(path)], capture_output=True, text=True
        )
        if listing.returncode != 0 or not listing.stdout.strip():
            raise ValueError("PostgreSQL dump could not be listed by pg_restore")
        integrity = "pg_restore_list_ok"

    return {"file": str(path), "sha256": digest, "bytes": path.stat().st_size, "integrity_check": integrity}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/verify_backup.py <backup-file> [sha256]", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(verify(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None), indent=2))
