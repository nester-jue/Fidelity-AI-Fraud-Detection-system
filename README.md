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
   - Starts the Frontend Dashboard on `http://localhost:5174`
   - Starts the Backend API on `http://localhost:8010`

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

4. **Start the Backend API Server (Port 8010)**:
   ```powershell
   $env:PYTHONPATH="."
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 --reload
   ```

5. **Start the Frontend Dashboard (Port 5174)**:
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

---

## 6. Key REST API Endpoints

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/auth/token` | Obtain JWT access token | Public |
| `GET` | `/auth/me` | Current user profile & role | Authenticated |
| `POST` | `/claims/submit` | Submit claim with documents & trigger AI analysis | Claims Officer / Admin |
| `GET` | `/claims/` | List claims with search, risk, and status filters | Authenticated |
| `GET` | `/claims/{id}` | Detailed claim profile with OCR forensics & AI breakdown | Authenticated |
| `PUT` | `/claims/{id}` | Update claim processing status | Claims Officer / Manager |
| `POST` | `/claims/{id}/score` | Recalculate AI fraud risk score on demand | Authenticated |
| `GET` | `/fraud/assessments` | List all calculated fraud risk assessments | Authenticated |
| `GET` | `/fraud/high-risk` | Priority queue of High & Critical risk claims | Authenticated |
| `GET` | `/investigations/` | List all investigation cases | Authenticated |
| `POST` | `/investigations/` | Open an investigation case for a flagged claim | Fraud Investigator / Admin |
| `PUT` | `/investigations/{id}` | Update findings, notes, and case status | Fraud Investigator |
| `GET` | `/dashboard/overview` | Executive KPI stats, loss prevention & risk distribution | Authenticated |
| `GET` | `/audit-logs/` | Tamper-evident compliance activity log | Compliance / Admin / Executive |
| `GET` | `/customers` | Policyholder customer registry | Authenticated |
| `GET` | `/policies` | Insurance policy registry | Authenticated |

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

## 8. Verification & Test Results

The platform has been validated through automated tests (`tests/test_system.py`):

```text
tests/test_system.py::test_system_health PASSED
tests/test_system.py::test_auth_login_success PASSED
tests/test_system.py::test_auth_login_invalid PASSED
tests/test_system.py::test_auth_me_profile PASSED
tests/test_system.py::test_rbac_admin_route_restricted PASSED
tests/test_system.py::test_rbac_admin_route_allowed PASSED
tests/test_system.py::test_submit_claim_and_fetch PASSED
tests/test_system.py::test_duplicate_claim_scoring PASSED
tests/test_system.py::test_policy_inception_fraud_scoring PASSED
tests/test_system.py::test_ocr_processing_and_hash PASSED
tests/test_system.py::test_investigations_lifecycle PASSED
tests/test_system.py::test_dashboard_overview PASSED
======================= 12 passed in 6.76s =======================
```
