# NEXA Knowledge Base — Manuals / Policies Intake (Phase 6)

This folder is the **Phase 6 intake** for the departmental AI knowledge base:
verified Fidelity manuals, policies, procedures and SOPs.

## How ingestion works

Each file in this folder is parsed and ingested into the knowledge store via
the System Administrator endpoints (`POST /chatbot/documents`):

```powershell
python scripts/ingest_manuals.py docs/manuals
```

(The script requires the backend running on `http://localhost:8010`; authenticate
with `ADMIN_TOKEN` or `ADMIN_USERNAME`/`ADMIN_PASSWORD`.)

## Supported formats

| Format | Status |
|---|---|
| `.txt`, `.md`, `.rst`, `.csv`, `.tsv` | Phase 5 — parsed to text now |
| `.pdf`, `.docx` | Phase 6 — parsing added when `pypdf` / `python-docx` are installed (`backend/app/services/knowledge/documents.py`) |

## Department scoping

Add a header to any ingested file so the chatbot only serves it to the
matching department's role:

```text
# Claims Procedures Manual
- Department: claims_officer
...
```

Default scope is `shared` when no header is present.

## Status of this folder

- `shared_company_knowledge.md`-style intake is covered by `docs/knowledge_packages/`
  (the seven departmental packages, Phase 5).
- Phase 6 deliverables pending: official Fidelity manuals/policies — upload
  them here as PDF/DOCX once PDF/DOCX parsing (Phase 6) is complete, and ingest
  with `scripts/ingest_manuals.py`.
- **Sample manual** `EXAMPLE_claims_procedures.txt` — ingest with:

  ```powershell
  python scripts/ingest_manuals.py docs/manuals
  ```

## Updating manuals (Phase 7)

Re-run `python scripts/ingest_manuals.py docs/manuals` after changing files.
Re-seed packages with `python scripts/refresh_kb.py` — both scripts are
idempotent; edits to seeded packages are re-ingested automatically by
`seed_knowledge_packages()` (Phase 7 update loop).
