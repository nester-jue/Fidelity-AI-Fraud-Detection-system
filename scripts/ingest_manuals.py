"""
NEXA Knowledge Base — Phase 6 Manuals/Policies Ingestion Script

Ingests Fidelity Life Assurance manuals, policies, procedures and SOPs from
``docs/manuals/`` into the NEXA knowledge base so the AI can answer
departmental knowledge questions.

Usage:
    python scripts/ingest_manuals.py [docs/manuals]

Prereqs: the API must be running (backend on port 8010). Authentication:
set the admin token via ADMIN_TOKEN env var, or provide admin username/password
via ADMIN_USERNAME / ADMIN_PASSWORD (default admin / AdminPass123!).

Department scoping is read from the file header (``Department: <scope>``) or
from the folder name; packages default to "shared".
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

from backend.app.services.knowledge.documents import parse_document

DEFAULT_MANUALS_DIR = Path("docs/manuals")
SUPPORTED_EXTENSIONS = (".txt", ".md", ".csv", ".tsv", ".rst", ".pdf", ".docx")


def _get_token(client: httpx.Client, username: str, password: str) -> str:
    res = client.post("/auth/token", data={"username": username, "password": password})
    res.raise_for_status()
    return res.json()["access_token"]


KNOWN_SCOPES = {
    "shared", "claims_officer", "claims_manager", "fraud_investigator",
    "compliance_officer", "executive_management", "system_admin",
}


def _department_from_header(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:10]:
        stripped = line.strip().lstrip("-").strip()
        if stripped.lower().startswith("department:"):
            value = stripped.split(":", 1)[1].strip()
            if value and value.lower() in KNOWN_SCOPES:
                return value.lower()
            if value:
                print(f"WARN {path.name}: unknown department scope '{value}'; defaulting to 'shared'")
            break
    return "shared"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest manuals/policies into the NEXA knowledge base.")
    parser.add_argument("folder", nargs="?", default=str(DEFAULT_MANUALS_DIR))
    parser.add_argument("--base-url", default=os.environ.get("API_URL", "http://localhost:8010"))
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: manuals folder not found: {folder}")
        return 1

    token = os.environ.get("ADMIN_TOKEN")
    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        if not token:
            username = os.environ.get("ADMIN_USERNAME", "admin")
            password = os.environ.get("ADMIN_PASSWORD", "AdminPass123!")
            token = _get_token(client, username, password)
        headers = {"Authorization": f"Bearer {token}"}

        files = sorted(
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.name.lower().startswith("readme")
        )
        if not files:
            print(f"No supported manuals found in {folder} (supported: {', '.join(SUPPORTED_EXTENSIONS)})")
            return 0

        uploaded = 0
        for path in files:
            try:
                content = parse_document(path)
            except NotImplementedError as exc:
                print(f"SKIP {path.name}: {exc}")
                continue
            title = path.stem.replace("_", " ").title()
            department = _department_from_header(path)
            res = client.post(
                "/chatbot/documents",
                json={
                    "title": title,
                    "content": content[:100000],
                    "department": department,
                    "doc_type": "manual",
                    "status": "verified",
                },
                headers=headers,
            )
            if res.status_code == 200:
                body = res.json()
                print(f"OK   {path.name} → doc {body['document_id']} ({body['department']}, {body['chunks_added']} chunks)")
                uploaded += 1
            else:
                print(f"FAIL {path.name}: {res.status_code} {res.text[:200]}")

            time.sleep(0.2)  # gentle rate limiting

        print(f"\n{uploaded}/{len(files)} manuals ingested. New manuals appear in knowledge-base answers immediately.")
        return 0 if uploaded > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
