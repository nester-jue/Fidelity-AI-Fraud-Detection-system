# NEXA Departmental AI Knowledge Packages

These structured markdown packages are the human-readable starting point for
the **NEXA Departmental AI Knowledge Base** (Phase 5 of the NEXA AI
Intelligence Assistant roadmap). They are prepared as separate packages so
each department's domain knowledge can be reviewed, edited and governed
independently.

Each package file contains:

- **Metadata header** — `Department:` (matches the role scope used by
  retrieval), package status, and scope notes.
- **Responsibilities** — what the department owns.
- **Products & Services** — relevant company products and financial services.
- **Technical & Operational Knowledge** — systems, processes, terminology.
- **Policies & Procedures** — approved workflows.
- **Frequently Asked Questions** — natural-language questions with verified answers.
- **Escalation Procedures** — who owns the next step when questions go beyond scope.
- **Restricted Information** — what the assistant must never disclose.

## Packages in this folder

| Package | Department scope |
|---|---|
| `shared_company_knowledge.md` | `shared` (applies to every role) |
| `claims_officer.md` | `claims_officer` |
| `claims_manager.md` | `claims_manager` |
| `fraud_investigator.md` | `fraud_investigator` |
| `compliance_officer.md` | `compliance_officer` |
| `executive_management.md` | `executive_management` (CRO role) |
| `system_admin.md` | `system_admin` |

## How packages are used (RAG)

The backend seeds every package into the knowledge store at startup
(`CHATBOT_KB_SEED=true`). The chatbot retrieves relevant chunks with
hashed-embedding retrieval (`backend/app/services/knowledge/`) and merges
the results into its answers — no model retraining is required. Packages are
editable: when a package changes, restart the backend (or call
`seed_knowledge_packages()`) — the store re-embeds changed content because
`add_chunks` appends new chunks and documents are keyed by package source.

For verified Fidelity manuals, policies and procedures (Phase 6), these
packages are the intake format: documents are uploaded via the
`/chatbot/documents` endpoints (System Administrator only) and parsed into
the same store via `backend/app/services/knowledge/documents.py`. Text
formats (.txt/.md) are supported in Phase 5; PDF/DOCX parsing is a Phase 6
extension (see `documents.parse_document`).
