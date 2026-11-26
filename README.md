# FIDELITY LIFE ASSURANCE
## NEXA AI Fraud Claims Detection and Investigation Platform

An enterprise-grade, production-oriented Artificial Intelligence and Machine Learning claims risk assessment and fraud detection system designed for **Fidelity Life Assurance Company**.

---

## 1. Executive Summary

Insurance fraud presents substantial financial exposure, operational friction, and underwriting risk. The **NEXA AI Fraud Detection System** introduces real-time intelligence into the claims processing lifecycle, automatically analyzing submitted claims, inspecting supporting documents with Optical Character Recognition (OCR), evaluating anomalies and duplicate records, and computing an explainable fraud risk score between 0 and 100.

**Human-in-the-Loop Architecture**: In accordance with regulatory guidelines and Zimbabwean Data Protection requirements, the system **never automatically rejects claims**. All elevated risk claims are surfaced with transparent explanations and prioritized into the Fraud Investigation Unit queue for expert human adjudication.

---

## 2. Key System Capabilities

- **Multi-Layered AI Fraud Detection Engine**:
  - **Duplicate Claims Detection**: Exact and fuzzy detection of repeated claims and identical incident dates across policyholders.
  - **Policy Inception Fraud**: Identifies claims filed shortly following policy commencement (critical threshold: < 60 days).
  - **Amount Anomaly & Benefit Schedule Limits**: Detects claims exceeding maximum coverage schedules or deviating from historical baselines.
  - **Claim Velocity & Frequency**: Flags policyholders with excessive claim frequency in short intervals.
  - **Beneficiary & Identity Inconsistency**: Flags recent emergency alterations to designated beneficiaries and invalid national registration numbers.
- **Advanced OCR & Document Verification**:
  - Document categorization (Death Certificates, Medical Reports, Police Reports, National IDs, Invoices, Claim Forms).
  - Cross-validation: Compares death certificate dates directly against claim incident dates to catch fictitious claims.
  - Cryptographic Fingerprinting: Detects duplicate supporting documents via SHA-256 hash checks.
  - Extensible provider interface (Local Tesseract OCR with Azure AI Document Intelligence cloud readiness).
- **Role-Based Access Control (RBAC)**:
  - Six distinct operational roles: `system_admin`, `claims_officer`, `claims_manager`, `fraud_investigator`, `compliance_officer`, `management`.
- **Investigation Case Management**:
  - Case progression tracking: `open` &rarr; `in_review` &rarr; `escalated` &rarr; `confirmed_fraud` / `cleared`.
  - Case notes logging, officer assignment, and loss prevention auditing.
- **Enterprise Executive Dashboard**:
  - Live interactive dashboard branded with Fidelity Life Assurance identity.
  - Risk distribution charts, real-time KPI metrics, suspicious claim queue, claim detail drill-down, and compliance logs.

---

## 3. Technology Architecture

| Layer | Technologies |
|---|---|
| **Backend API** | Python 3.11+ / 3.13, FastAPI, Uvicorn, Pydantic v2 |
| **Database** | PostgreSQL with SQLAlchemy ORM (Automatic local SQLite fallback for dev) |
| **Security & Auth** | JWT (PyJWT), PBKDF2-HMAC-SHA256 password hashing, RBAC dependencies |
| **Machine Learning** | Ensemble rule engine, Isolation Forest anomalies, Random Forest classification |
| **Document OCR** | Tesseract OCR provider, cryptographic SHA-256 hashing, regex entity extraction |
| **Frontend UI** | Responsive enterprise dashboard (Tailwind CSS, HTML5, Lucide/FontAwesome, React) |
| **DevOps & QA** | Pytest, Docker, Docker Compose, Alembic migrations |

---

## 4. Default Demonstration Accounts

The database comes pre-seeded with accounts for all operational roles:

| Role | Username | Password | Purpose |
|---|---|---|---|
| **System Administrator** | `admin` | `AdminPass123!` | System configuration, user management, audit logs |
| **Claims Officer** | `claims.officer` | `OfficerPass123!` | Submits claims, uploads documents, updates initial status |
| **Claims Manager** | `claims.manager` | `ManagerPass123!` | Reviews all portfolio claims and operational approvals |
| **Fraud Investigator** | `investigator` | `Investigate123!` | Investigates flagged claims, records evidence, logs outcomes |
| **Compliance Officer** | `compliance` | `Compliance123!` | Inspects immutable audit logs and regulatory adherence |
| **Executive / CRO** | `executive` | `Executive123!` | High-level loss prevention metrics and portfolio risk views |

---

## 5. Quick Start Guide (Windows)

### Option A: One-Click PowerShell Launch (Recommended)

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd "c:\Users\user\Desktop\FIDE-AI-Fraud-Detection"
   ```
2. Run the launch script:
   ```powershell
   .\run_dev.ps1
   ```
   This automatically:
   - Initializes database tables
   - Seeds realistic demonstration claims, policies, and users
   - Executes the automated test suite (`pytest`)
   - Installs frontend dependencies if needed and builds the React bundle
   - Starts the Backend API on `http://localhost:8010`, waits for `/health`, then starts the Frontend Dashboard on `http://localhost:5174`

3. Open your browser:
   - **Interactive Frontend Dashboard**: [http://localhost:5174](http://localhost:5174)
   - **Backend Dashboard & API**: [http://localhost:8010](http://localhost:8010)
   - **Interactive OpenAPI / Swagger Documentation**: [http://localhost:8010/docs](http://localhost:8010/docs)

---

### Option B: Manual Execution Steps

1. **Populate Demonstration Data**:
   ```powershell
   $env:PYTHONPATH="."
   python data/seed_db.py
   ```

2. **Run Model Benchmark & Evaluation**:
   ```powershell
   $env:PYTHONPATH="."
   python ml/train.py
   ```

3. **Run Automated Test Suite**:
   ```powershell
   $env:PYTHONPATH="."
   pytest tests/test_system.py -v
   ```

4. **Install and Build the Frontend** (required on a fresh checkout):
   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```

5. **Start the Backend API Server (Port 8010)**:
   ```powershell
   $env:PYTHONPATH="."
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 --reload
   ```

6. **Start the Frontend Dashboard (Port 5174)**:
   ```powershell
   node frontend/server.js
   # or with npm/vite:
   cd frontend; npm run dev
   ```

---

### Option C: Docker Compose (Isolated Container Stack)

To run the full stack with isolated PostgreSQL and API on port 8010:
```powershell
docker-compose up --build
```
The API will be accessible at `http://localhost:8010` and Swagger at `http://localhost:8010/docs`.

For any non-local deployment, copy `.env.example` to `.env` and set at minimum
`ENVIRONMENT=production`, a unique `JWT_SECRET_KEY`, an explicit `CORS_ORIGINS`
allow-list (never `*`), and PostgreSQL connection settings. The one-click demo
role selector is visible automatically when the UI is opened on `localhost`,
`127.0.0.1` or `[::1]`, so the local walkthrough can switch access levels. For
a hosted demonstration deployment set `DEMO_MODE=true` and
`VITE_DEMO_MODE=true`; set `VITE_DEMO_MODE=false` to hide demo credentials
everywhere, including local builds.

---

## 6. Key REST API Endpoints

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/auth/token` | Obtain JWT access token (authenticator code required when MFA is enrolled) | Public |
| `POST` | `/auth/register` | Request a `claims_officer` account (configurable, never privileged) | Public when enabled |
| `POST` | `/auth/forgot-password` / `/auth/reset-password` | SMTP-delivered single-use reset token and completion | Public when SMTP configured |
| `GET` | `/auth/me` | Current user profile & role | Authenticated |
| `GET` | `/auth/mfa/status` | MFA enrolment status and policy requirement | Authenticated |
| `POST` | `/auth/mfa/setup` / `/auth/mfa/enable` / `/auth/mfa/disable` | TOTP authenticator enrolment and removal (policy-enforced when required) | Authenticated |
| `POST` | `/enquiries/` | Record a public product enquiry with a reference | Public |
| `GET` | `/security/overview` / `/security/events` | Real authentication/audit telemetry and honestly labelled control status | Compliance / Admin / Executive / CRO |
| `POST` | `/claims/fnol`, `GET /claims/fnol/list` | Persist and list First Notices of Loss | Authenticated |
| `POST` | `/claims/submit` | Submit claim with documents & trigger AI analysis | Claims Officer / Admin |
| `GET` | `/claims/` | List claims with search, risk, and status filters | Authenticated |
| `GET` | `/claims/{id}` | Detailed claim profile with OCR forensics & AI breakdown | Authenticated |
| `PUT` | `/claims/{id}` | Update claim processing status | Claims Officer / Manager |
| `POST` | `/claims/{id}/score` | Recalculate AI fraud risk score on demand | Claims Manager / Investigator / Admin |
| `GET` | `/fraud/assessments` | List all calculated fraud risk assessments | Authenticated |
| `GET` | `/fraud/high-risk` | Priority queue of High & Critical risk claims | Authenticated |
| `GET` | `/investigations/` | List all investigation cases | Authenticated |
| `POST` | `/investigations/` | Open an investigation case for a flagged claim | Fraud Investigator / Admin |
| `PUT` | `/investigations/{id}` | Update findings, notes, and case status | Fraud Investigator |
| `GET` | `/dashboard/overview` | Executive KPI stats, loss prevention & risk distribution | Authenticated |
| `GET` | `/audit-logs/` | Tamper-evident compliance activity log | Compliance / Admin / Executive |
| `GET` | `/customers` | Policyholder customer registry | Authenticated |
| `GET` | `/policies` | Insurance policy registry | Authenticated |

### Advanced Enterprise Intelligence Endpoints (NEXA Master Upgrade)

**Fraud Network Intelligence** (`/fraud-network/*`) — Live relationship graph from real records: connected entities, relationships, suspicious clusters, relationship strength, supporting evidence.

**Claim Timeline Intelligence** (`/timeline/*`) — Chronological claim history from real records with anomalies and missing steps highlighted.

**Digital Evidence & Audit Trail** (`/evidence/*`) — Evidence records with SHA-256 hashes, integrity re-verification, status transitions, append-only audit entries.

**Historical Claim Behaviour** (`/historical/*`) — Current vs. previous vs. similar claims, policy info, benefit-change timing, patterns.

**Predictive Fraud Monitoring** (`/predictive/*`) — Predictive alerts, scan trigger, acknowledge/resolve/dismiss (human decisions; alerts are never 'confirmed fraud').

**Zimbabwe Intelligence** (`/zim/*`) — National ID format validation, date normalization, currency acceptance rules, regulatory rules (configurable defaults).

**AI Model Performance & Learning Centre** (`/model-performance/*`) — Performance dashboard (precision/recall/F1/FP/FN rates), versions, history, controlled retraining request workflow.

**Per-document forensic reports** (`/forensics/document/{id}/report`, `/forensics/documents/reuse`) — Extends the legacy forensic analysis: document reuse detection, image integrity forensics, PDF signature checks.

---

## 7. Fraud Risk Classification Matrix

Every claim receives a calibrated risk score between 0 and 100:

| Score Range | Risk Classification | System Recommended Action |
|---|---|---|
| **0 – 29** | **Low Risk** | Standard claims processing subject to routine verification. |
| **30 – 59** | **Medium Risk** | Secondary review by senior Claims Officer prior to payment authorization. |
| **60 – 79** | **High Risk** | Priority referral to Fraud Investigation Unit; document validation required. |
| **80 – 100** | **Critical Risk** | Immediate administrative payment hold; escalated investigation for suspected fraud. |

---

## 7A. Enterprise Operational Controls

### Tenant isolation (opt-in)
Set `TENANT_ISOLATION_ENABLED=true` for multi-tenant deployments. The ORM layer
then adds a `organisation_id` filter to every tenant-owned SELECT and stamps
inserts with the organisation from the signed JWT. Requests without a valid
organisation claim fail closed. Sign-in, registration, reset and public
enquiries are the only unscoped paths, and they return no tenant data.
Create the first tenant and administrator with `scripts/bootstrap_tenant.py`;
self-registration requires `DEFAULT_ORGANISATION_ID`. In single-tenant mode
the flag stays `false` so legacy databases keep working unchanged. Starlette
background AI tasks explicitly re-bind the tenant captured from the request.

### MFA, registration and password reset
`MFA_REQUIRED=true` is **enforced**: un-enrolled accounts receive a 15-minute
enrolment-only token that can reach `/auth/mfa/status|setup|enable|disable` but
no business data. On successful enrolment the API returns a full token, which
the UI stores automatically. Self-service registration can only create a
`claims_officer` account. Password reset works when `PASSWORD_RESET_EMAIL_ENABLED`
and SMTP settings are configured: a hashed, single-use token is emailed with a
link to `/reset-password?token=…`; the frontend form completes the reset (the
web server must route that path to the SPA entry point). When SMTP is not
configured the API returns a configuration error rather than a false success. Email verification, token revocation and licence/payment flows
are **not implemented** and are not claimed anywhere in the product.

### Real data, FNOL and integrations
First Notices of Loss are persisted in `first_notices_of_loss` and listed from
that table; no names, dates or channels are invented. Policy/customer/claim
adapters read the system-of-record tables, or an external API configured with
`POLICY_SYSTEM_URL`; missing records return empty results. Claims submitted
with an unknown policy are rejected with HTTP 404 instead of creating fake
policies. Payment and identity-verification adapters report `NOT_CONFIGURED`.
The public landing page records enquiries in the `enquiries` register with a
reference and does not claim to send an email.

### Versioned migrations and backup/restore
`alembic/versions/0001_initial_schema.py` is a baseline revision; the runtime
URL comes from `DATABASE_URL`. `scripts/backup_db.py` produces a checksummed
SQLite (online backup) or PostgreSQL (`pg_dump`) file plus a JSON manifest;
`scripts/verify_backup.py` verifies the checksum and integrity;
`scripts/restore_db.py` refuses a production target without
`--confirm-production`. Run a restore rehearsal on disposable data before
relying on these scripts in production. `MIGRATIONS.md` records the historical
schema evolution applied by the startup helper.

## 8. Verification & Test Results

The full backend suite is run from the repository root with `python -m pytest -q`.
Frontend tests and production build are run from `frontend` with `npm test` and
`npm run build`.

```text
Backend: 181 passed, 1 skipped (1 Starlette/httpx deprecation warning) — ephemeral SQLite test database
Frontend tests: 9 passed (Vitest + jsdom)
Frontend build: 1487 modules transformed; no chunk over 500 kB (largest JS chunk 398.53 kB)
```

`tests/conftest.py` gives each test run a disposable SQLite database seeded
with the documented demo users and baseline records; the working database in
`data/frauddb.sqlite` is not modified by tests. `tests/test_security_hardening.py`
covers registration hardening, password policy, TOTP round-trip/enrolment and
MFA enforcement, Security Centre RBAC and honest status reporting, and production
database guards. `tests/test_enterprise_operations.py` covers public enquiries,
FNOL persistence, the SMTP reset flow (with a fake SMTP server), tenant
filtering/isolation, Alembic baseline migration, backup/restore round-trip,
production-restore protection, DOCX ingestion and non-synthesising adapters.
`.github/workflows/ci.yml` runs both suites and the build on pushes and PRs.

Important caveats, stated plainly:

- OCR of scanned images requires a local Tesseract binary; it is **not**
  installed in this development environment. Text/PDF/DOCX extraction is
  covered; scanned-image OCR could not be verified here.
- No PostgreSQL server was available locally. The connection code, production
  guard, migrations and pg_dump/pg_restore scripts are implemented and unit
  tested on SQLite; live PostgreSQL and disaster-recovery rehearsal remain
  deployment-side responsibilities.
- CI YAML was validated locally but the workflow has not been executed on a
  hosted runner.

## 9. Implementation Status — Enterprise Upgrade (NEXA Master)

Status legend: `COMPLETED AND TESTED` | `IMPLEMENTED BUT NOT FULLY TESTED` | `PARTIALLY IMPLEMENTED` | `NOT IMPLEMENTED` | `BLOCKED`

| Feature | Status |
|---|---|
| Phase 2 — Multimodal AI engine (isolation component + ensemble blend) | COMPLETED AND TESTED |
| Phase 3 — Fraud network detection (graph, clusters, network analytics) | COMPLETED AND TESTED |
| Phase 4 — Document forensics upgrades (image/PDF forensics, reuse, per-document reports) | COMPLETED AND TESTED |
| Phase 5 — Historical claim behaviour analysis | COMPLETED AND TESTED |
| Phase 6 — Claim timeline reconstruction | COMPLETED AND TESTED |
| Phase 9 — Digital evidence management + audit trail | COMPLETED AND TESTED |
| Phase 11 — Predictive fraud risk monitoring | COMPLETED AND TESTED |
| Phase 13 — AI model performance dashboard + controlled retraining workflow | COMPLETED AND TESTED |
| Phase 2/6 — Ensemble model integration (fraud_engine scoring path) | COMPLETED AND TESTED |
| Phase 9 — Zimbabwe intelligence (ID formats, currencies, rules) | COMPLETED AND TESTED |
| Phase 14 — NEXA AI Investigation Copilot (network/timeline/evidence/historical/predictive/zim/model-performance/exposure handlers) | COMPLETED AND TESTED (backend) |
| Phase 14 — Departmental frontend workspaces (FraudNetworkGraph, ClaimTimeline, EvidenceManagement, HistoricalBehaviorPanel, PredictiveAlerts, ModelPerformanceDashboard, ZimIntelligencePanel) | COMPLETED AND TESTED (vite build) |
| Phase 12 — Regression testing and final validation | COMPLETED AND TESTED |
| Phase 10 — Fraud network materialised node/edge tables (service computes dynamically) | PARTIALLY IMPLEMENTED (computed on demand) |
| Phase 8 — extended forensic tests against real OCR services (tesseract) | IMPLEMENTED BUT NOT FULLY TESTED (Tesseract binary not present locally) |
| Public NEXA product overview + secured login | COMPLETED AND TESTED (vite build) |
| Security Centre (auth telemetry, audit events, database check, honest controls) | COMPLETED AND TESTED |
| Self-service MFA enrolment (TOTP authenticator app, enforced at sign-in) | COMPLETED AND TESTED |
| Privileged self-registration blocked; password policy enforced | COMPLETED AND TESTED |
| Production safety guards (no known JWT secret, no wildcard CORS, no SQLite fallback) | IMPLEMENTED (configuration-level; deployment validation pending) |
| Human-in-the-loop model governance — precision null until confirmed outcomes | COMPLETED AND TESTED |
| Financial exposure report — confirmed-fraud amounts only (no 10% estimate) | IMPLEMENTED AND TESTED |
| Tenant/organisation isolation (opt-in, ORM-enforced, fail-closed) | COMPLETED AND TESTED |
| Versioned Alembic baseline migration, verified backup/restore scripts and CI | COMPLETED AND TESTED (SQLite; PostgreSQL rehearsal deployment-side) |
| Password-reset email delivery via configured SMTP + frontend reset form | COMPLETED AND TESTED (with fake SMTP server) |
| Email verification, JWT token revocation, licensing/payments | NOT IMPLEMENTED (not claimed by the product) |
| Public enquiry register and persisted FNOL intake | COMPLETED AND TESTED |
| PDF/DOCX knowledge ingestion (`pypdf`, `python-docx`) | IMPLEMENTED (DOCX extraction tested; PDF parser installed) |

### Honest-labelling notes (system requirements)

- AI/machine outputs are labelled **potential/predictive/technical-anomaly**; nothing is auto-labelled confirmed fraud.
- The statistical isolation scorer approximates Isolation Forest principles; sklearn/pandas are declared dependencies but not installed in the local dev environment (statistical alternative implemented, documented in `backend/app/ml/fraud_engine.py`).
- ZIM regulatory values in `backend/app/services/zim_config.py` are configurable platform defaults — insurers must verify against current legislation with legal counsel.
- The assistant (`/chatbot/*`) is deterministic-from-real-records; the optional external LLM path (`CHATBOT_LLM_API_KEY`) stays off unless configured.
- The legacy "network" page on the dashboard remains as-is; the new fraud network workspace uses live data.
- Demo credentials and one-click role switching are visible on local hosts by default, or in production only when `DEMO_MODE=true` / `VITE_DEMO_MODE=true`; set `VITE_DEMO_MODE=false` to hide them everywhere.
- MFA is available per user via **My Profile → Multi-factor authentication**. With `MFA_REQUIRED=true`, un-enrolled accounts cannot reach business data until enrolment is complete; the enrolment-only token is short-lived and the UI upgrades it automatically. The Security Centre reports the effective policy.
