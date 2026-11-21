# NEXA — Insurance & Medical Claim Forms Research & OCR Integration Report

**Objective:** Source genuine insurance/medical claim form PDFs; integrate them
with the NEXA AI Fraud Claims Detection Platform (OCR, AI forensics,
dashboards, tests). Work was done inside the existing project (no new app, no
reset of existing records).

---

## 1. Documents Successfully Sourced (12)

| # | File (data/sample_claim_documents/) | Category |
|---|---|---|
| 1 | life_insurance_bajajlife_death_claim_form.pdf | life_insurance |
| 2 | life_insurance_pearlnylife_death_claim_form.pdf | life_insurance |
| 3 | funeral_claims_fiji_care_funeral_benefit_claim_form.pdf | funeral_claims |
| 4 | funeral_claims_hollard_funeral_claim_form.pdf | funeral_claims |
| 5 | funeral_claims_uwrf_funeral_claim_form.pdf | funeral_claims |
| 6 | medical_insurance_cigna_medical_claim_form.pdf | medical_insurance |
| 7 | medical_insurance_mediassist_reimbursement_claim_form.pdf | medical_insurance |
| 8 | hospitalisation_uhs_discharge_summary.pdf | hospitalisation |
| 9 | hospitalisation_vidal_standard_discharge_summary.pdf | hospitalisation |
| 10 | accident_disability_cic_kenya_personal_accident_claim_form.pdf | accident_disability |
| 11 | accident_disability_magma_individual_personal_accident_claim_form.pdf | accident_disability |
| 12 | accident_disability_mua_personal_accident_claim_form.pdf | accident_disability |

## 2. Original Source Institutions & Links (DOCUMENT_REGISTER.md)

| # | Institution | Source URL |
|---|---|---|
| 1 | Bajaj Life | https://bajajlifeinsurance.com/content/dam/balic-web/pdf/claims/deathClaim/Deathclaimapplicationform-min.pdf |
| 2 | Pearl NY Life | https://marketing.pearlinsurance.com/cdn/NYL-Forms/Death-Claim-Form.pdf |
| 3 | Fiji Care | https://fijicare.com.fj/Images/Forms/Funeral%20Benefit%20Claim%20Form.pdf |
| 4 | Hollard Group Risk | https://hollardgrouprisk.com/forms/Funeral_Claim_Form.pdf |
| 5 | UWF / Sanlam | https://uwrf.co.za/wp-content/uploads/2024/01/Funeral-claim-form.pdf |
| 6 | Cigna | https://cigna.com/static/www-cigna-com/docs/form-medical-claim.pdf |
| 7 | Medi Assist | https://t.mediassist.in/Resource/PolicyDocs/Reimbursement_ClaimForm.pdf |
| 8 | UHS NHS Trust (UK) | https://www.uhs.nhs.uk/Media/UHS-website-2019/Docs/Clinical-forms/Dischargesummary.pdf |
| 9 | Vidal Health TPA | https://vidalfestorage.blob.core.windows.net/vidal-homepage/vidalhealthtpa/vidal%20forms/Standard_Discharge_Summary.pdf |
| 10 | CIC Insurance Group (Kenya) | https://ke.cicinsurancegroup.com/wp-content/uploads/2021/09/Personal-Accident-Claim-Form.pdf |
| 11 | Magma Insurance | https://magmainsurance.com/documents/5553002/0/Claim+Form+%E2%80%93+Individual+Personal+Accident.pdf |
| 12 | MUA (South Africa) | https://mua.co.za/wp-content/uploads/2026/07/Personal-Accident-Claim-Form-2026-version-1.pdf |

## 3. Folder Structure Created

```
data/sample_claim_documents/
  DOCUMENT_REGISTER.md                     # source register (institutions + URLs)
  README.md                                # ingestion workflow documentation
  life_insurance_bajaxlife_death_claim_form.pdf
  life_insurance_pearlnylife_death_claim_form.pdf
  funeral_claims_fiji_care_funeral_benefit_claim_form.pdf
  funeral_claims_hollard_funeral_claim_form.pdf
  funeral_claims_uwrf_funeral_claim_form.pdf
  medical_insurance_cigna_medical_claim_form.pdf
  medical_insurance_mediassist_reimbursement_claim_form.pdf
  hospitalisation_uhs_discharge_summary.pdf
  hospitalisation_vidal_standard_discharge_summary.pdf
  accident_disability_cic_kenya_personal_accident_claim_form.pdf
  accident_disability_magma_individual_personal_accident_claim_form.pdf
  accident_disability_mua_personal_accident_claim_form.pdf
```

Original documents preserved; nothing altered.

## 4. OCR Functionality Implemented

- **`backend/app/ocr/pdf_text_extractor.py`** — text extraction: prefers the
  `pdftotext` binary (poppler, handles CID fonts/XFA), falls back to a
  pure-Python PDF content-stream extractor.
- **`backend/app/services/sample_documents.py`** — ingestion service:
  - Classifies documents into 5 categories (text + filename heuristics).
  - Extracts structured fields via generic label/regex extraction
    (claimant_name, policy_number, claim_number, national_id, date_of_birth,
    incident_date, claimed_amount, medical_practitioner, hospital_name,
    diagnosis, beneficiary_name, signature_declarations, supporting_documents,
    dates/amounts/IDs observed).
  - Stores each document as an `OCRDocument` row (claim_id=None,
    `is_sample_document=True`, `sample_category`, `source_institution`,
    `source_url`, SHA-256 fingerprint, confidence).
- **`backend/app/api/sample_claim_documents.py`** — `GET /ocr/sample-documents/`
  (list), `GET /ocr/sample-documents/{id}` (detail with extraction results).
  Backend role enforcement on all endpoints.
- **Ingested documents:** all 12 ingest cleanly; ~11 have full text
  extraction (confidence 0.85), Magma (image-based form) flagged at 0.35.

## 5. AI Forensic Functionality Improved

- **`backend/app/services/document_forensics.py`** (new):
  - `find_duplicate_document_groups` — duplicate SHA-256 fingerprint groups.
  - `analyze_claim_documents` — conflicting claimant names, policy numbers,
    dates; missing fields aggregated across a claim's documents.
  - `find_suspicious_flags` — heuristic flags (flags/date mismatch/failed jobs).
  - `generate_forensic_analysis` — combined analysis for dashboards.
- **`GET /forensics/document-analysis`** — new endpoint (duplicates,
  inconsistencies, suspicious flags + summary).
- **Chatbot `_forensics_handler`** — new `forensics` intent branch:
  "Show me document analysis" → document forensic findings text.
- Sample claim forms (`ocr_documents.is_sample_document`) are included in
  forensic analysis.

> **Honesty note (per spec §8):** forensic findings are human-review items,
> not proof of fraud.

## 6. Dashboard Changes

Frontend (React):
- `frontend/src/components/pages/OCRDocumentPage.jsx` — two new tabs:
  - **Genuine Claim Forms** — table of sample claim documents
    (category, source institution, confidence, missing fields) + detail modal
    with structured extracted fields, observed dates/amounts/IDs, raw text
    snippet, source URL, flags.
  - **Document Forensics** — summary cards + duplicate groups, consistency
    issues, suspicious flags.
- `frontend/src/components/DashboardLayout.jsx` — new nav items:
  Claims Officer/Manager: **Genuine Claim Forms**; Fraud Investigator/Compliance:
  **Genuine Claim Forms + Document Forensics**.
- `frontend/src/App.jsx` — render branches for the two new tabs.
- `frontend/src/api/apiClient.js` — `listSampleDocuments`,
  `getSampleDocument`, `getForensicAnalysis`.

Backend: `GET /ocr/sample-documents/`, `GET /ocr/sample-documents/{id}`,
`GET /forensics/document-analysis` — role-enforced.

## 7. Tests Executed & Results

Full suite: **103 passed, 1 skipped** (was 89+15 with earlier phases; +19
new):
- `tests/test_sample_documents.py` (9) — ingestion, classification,
  extraction sanity, API, idempotency.
- `tests/test_document_forensics.py` (3) — duplicate groups, conflicting
  claim details, analysis shape.
- `tests/test_chatbot_doc_analysis.py` (2) — chatbot document analysis.

## 8. Outstanding Issues

- **Magma form extraction is empty** — image-based PDF; text extraction
  returned nothing. Needs vision-OCR (or manual entry) — flagged with
  confidence 0.35.
- Extraction of some fields varies by form layout; generic label extraction
  is best-effort (works on the 12 ingested).
- Sample docs are a shared registry — linkage to live claims (via
  `ocr_documents.claim_id`) is future work (Phase 8 follow-up).
- Fidelity manuals/policies (Phase 6) ingestion: `scripts/ingest_manuals.py`
  + `docs/manuals/` are ready; awaiting official manual uploads.

## 9. Recommended Next Improvements

1. **Sample-doc → claim linkage**: automated association of sample forms to
   live claims via claimant name/policy matching, enabling claim-level
   forensic findings.
2. **Vision OCR for scans**: install `pdftoppm`/vision OCR for image-based
   forms (e.g. Magma); add Tesseract page-image pipeline for scanned forms.
3. **Category system extensions**: support additional categories (e.g.
   Protecting Animals / Livestock if specified for the project) via the
   category enum, package system, and register rows.
4. **Automated consolidation tests**: back the changes above with CI runs of
   the full suite (`pytest tests/`) and the frontend build.
5. **Phase 6/8 follow-ups**: parse PDF/DOCX manuals (Phase 6 when libs are
   available), KB refresh script (`scripts/refresh_kb.py`), Package
   quality tests (`tests/test_knowledge_quality.py`).
