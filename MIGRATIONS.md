# NEXA Enterprise Upgrade — Database Migration Log

This document records every schema change introduced by the master upgrade
(Phases 2–15 of the NEXA Enterprise Intelligence upgrade).

All migrations are applied automatically at startup by
`backend/app/services/db.init_db()` + the conservative `_migrate_schema()`
(adds missing **nullable** columns; never drops/renames/modifies; never
auto-adds non-nullable columns). New tables are created by
`Base.metadata.create_all()`.

Order of operations at startup:
1. `create_all` — creates new tables.
2. `_migrate_schema()` — adds missing nullable columns to pre-existing tables.

## Phase 2 — Multimodal AI engine upgrades

- `fraud_assessments.rule_score` (Float, nullable) — rule-based component of the ensemble.
- `fraud_assessments.ensemble_score` (Float, nullable) — blended final score persisted for audit.
- `fraud_assessments.isolation_score` (Float, nullable) — statistical isolation component.

## Phase 3 — Fraud network detection

New tables:
- `fraud_network_nodes` (id PK string, entity_type, entity_key, name, national_id, customer_id, policy_number, claim_id, document_hash, is_suspicious, risk_contribution, total_edges, risk_score, created_at)
- `fraud_network_edges` (node_a_id FK, node_b_id FK, relationship_type, strength, evidence, claim_ids JSON, first_seen, last_seen, is_suspicious)

## Phase 4 — Document forensics upgrades

New/extended tables:
- `ocr_documents.forensic_findings` (JSON) — image integrity, signature, field-level findings.
- `ocr_documents.forensic_review_requested` (Boolean, default False)
- `ocr_documents.forensic_review_status` (String, default "not_requested")
- `ocr_documents.forensic_reviewed_by_id` (FK users)
- `ocr_documents.forensic_reviewed_at` (DateTime)
- `claim_documents.forensic_findings` (JSON)

## Phase 5 — Historical behaviour analysis

New tables:
- `claim_beneficiary_changes` (id, claim_id FK, changed_by_id FK, beneficiary_name, beneficiary_nin, changed_at, notes)

Extended tables:
- `claims.beneficiary_name` (String, nullable)
- `claims.beneficiary_nin` (String, nullable)
- `claims.beneficiary_change_count` (Integer, nullable, default 0)
- `claims.beneficiary_last_change_date` (DateTime, nullable)
- `claims.payment_account_refs` (JSON, nullable)
- `claims.phone_number` (String, nullable)
- `claims.email_address` (String, nullable)

## Phase 6 — Claim timeline intelligence

New tables:
- `claim_timeline_events` (id, claim_id FK, event_type, event_description, event_timestamp, source, sequence_order, is_fabricated, created_at)

## Phase 9 — Digital evidence management (integrated into timeline/evidence)

New tables:
- `evidence_records` (id, investigation_id FK, claim_id FK, document_id FK, evidence_type, title, file_path, sha256_hash, status, integrity_verified, integrity_verified_at, collected_at, collected_by_id FK, notes, linked_claim_id_snapshot)
- `model_retraining_requests` (id, requested_by_id FK, new_model_version, base_model_version, dataset_version, dataset_records, training_method, approved_by_id FK, status, notes, evaluated_at, deployed_at, requested_at, approved_at)

New tables (Phase 11):
- `predictive_alerts` (id, alert_type, severity, claim_id FK, customer_id FK, policy_id FK, description, risk_score, status, evidence_summary, resolution_note, generated_at, acknowledged_at, resolved_at)

## Enterprise operations upgrade (2026-11-26)

New tables:
- `organisations` (id, name, slug unique, is_active, created_at) — tenant registry.
- `first_notices_of_loss` (id, fnol_reference unique, claim_id, policy_number,
  policy_validated, claimant_name, event_type, incident_date, estimated_amount,
  reporting_channel, initial_notes, triage_queue, status, recorded_by_id,
  organisation_id, recorded_at) — persisted FNOL intake.
- `enquiries` (id, reference unique, organisation, email, interests, status,
  created_at) — public product enquiries with a reference.

Nullable columns added to existing tables by the startup helper:
- `users`: `mfa_secret`, `mfa_enabled`, `password_reset_token_hash`,
  `password_reset_expires_at`, `organisation_id`.
- all tenant-owned tables: `organisation_id` (stamped from the signed JWT when
  `TENANT_ISOLATION_ENABLED=true`).

Versioned migrations:
- `alembic/versions/0001_initial_schema.py` establishes a baseline from the
  complete ORM metadata. `alembic/env.py` reads `DATABASE_URL` at runtime.
  Future changes must be explicit revisions, not implicit startup columns.
- Backup/restore: `scripts/backup_db.py`, `scripts/verify_backup.py`,
  `scripts/restore_db.py`; restoration into production requires explicit
  `--confirm-production`.

## Status of each migration

- Applied automatically at startup (verified: `python -m uvicorn backend.app.main:app` + `init_db()`).
- Pre-existing databases: `_migrate_schema()` adds the nullable columns; the new tables are created by `create_all`.
- No data is altered, dropped or modified by any migration.

## Note on ModelPerformance

The existing `model_performance` table is extended by the new AI Model
Performance Dashboard (`/model-performance/*`): the model version is
`fraud_engine.MODEL_VERSION` ("v1.2-ensemble-hybrid"), plus the controlled
retraining workflow is tracked in `model_retraining_requests`.
