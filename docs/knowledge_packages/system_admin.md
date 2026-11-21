# Knowledge Package — System Administrator

- Department: system_admin
- Package: system_admin
- Scope: department
- Status: verified
- Owner-role: system_admin

## Overview

System Administrators operate and maintain the NEXA AI Fraud Detection
Platform. The assistant explains system state and operational procedures.

## System Architecture

- **React frontend** — dashboard web app (served by the built dashboard).
- **FastAPI backend** — Python 3.11+/3.13 API services on port 8010.
- **Database architecture** — PostgreSQL with SQLite dev fallback; SQLAlchemy
  ORM; Alembic-ready; migration via create_all + conservative additive
  migrations.
- **API endpoints** — documented in the OpenAPI/Swagger UI (`/docs`).
- **Authentication** — JWT sessions (PyJWT, 8-hour tokens by default).
- **Role-based access control** — six operational roles
  (system_admin, claims_officer, claims_manager, fraud_investigator,
  compliance_officer, management).
- **Departmental permissions** — claims management workspace, fraud
  investigation tools, compliance workspace, IT/system workspace.

## System Operations

- User registration and management — `/auth` and `/users` endpoints.
- Account activation and deactivation — role assignment, department
  assignment (e.g. "Claims", "Executive", "Compliance", "IT").
- Password resets, login auditing, and user management reporting.
- System configuration — via environment variables and settings (config
  file `backend/app/core/config.py`).
- Application monitoring — health endpoint (`/health`), uptime.
- Database health — connection status, table counts.
- API availability — service status per version.
- Deployment — docker-compose stack (isolated PostgreSQL + API), local dev
  via PowerShell script (`run_dev.ps1`), or manual steps.

## AI Services

- **AI fraud detection engine** — ensemble rule engine, Isolation Forest
  anomalies, Random Forest classification (`ml/train.py`, `backend/app/ml/`).
- **OCR processing** — Tesseract OCR provider with document categorisation,
  date/amount/ID extraction and hash-based duplicate detection.
- **AI forensic analysis** — OCR correction workflows, flag/uncertainty
  handling, image fingerprinting.
- **Chatbot integration** — NEXA AI Intelligence Assistant endpoints
  (`/chatbot/*`).
- **Model performance monitoring** — assessment tables, ML performance
  metrics.
- **Failed AI processing jobs** — retry logic, alert flags on failed docs.
- **Error handling** — structured audit trail (`/audit-logs/`), admin
  visibility of login and operation events.

## Reporting Endpoints

- `/dashboard/overview`, `/claims/`, `/fraud/assessments`,
  `/investigations/`, `/audit-logs/`, `/customers`, `/policies`.

## FAQs

- Which users are currently active?
- Is the OCR service operational?
- Why did a document-processing request fail?
- Which API services are unavailable?
- How do I assign a user to a department?
- How do I investigate a failed login?

## Escalation

Escalate operational incidents to the technical operations team and IT
support. All changes to the system must be logged via the audit trail and
approved by the change control process.

## Restricted Information

Never disclose secrets, hashes or tokens in plain text; scrub PII from
exports; only the owning team may change user roles or departments.
