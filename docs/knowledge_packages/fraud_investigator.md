# Knowledge Package — Fraud Investigator

- Department: fraud_investigator
- Package: fraud_investigator
- Scope: department
- Status: verified
- Owner-role: fraud_investigator

## Overview

Fraud Investors (SIU) investigate suspicious claims. The assistant supports
investigations only — it never approves claims or alters evidence.

## Insurance Fraud Types

- **Identity fraud** — stolen or fabricated identities used on claims.
- **Policy application fraud** — fictitious or aggressively misrepresented applications.
- **Falsified death certificates** — certificates created or altered for gain.
- **Forged medical reports** — fabricated or altered clinical documentation.
- **Inflated funeral expenses** — support receipts not matching advertised costs.
- **Duplicate claims** — same incident claimed multiple times.
- **Beneficiary fraud** — unauthorised beneficiary changes.
- **Premium manipulation** — under-reporting premiums to qualify for coverage.
- **Staged incidents** — deliberately manufactured losses (accidents, deaths).
- **Collusion** — claimant × service provider × insurer agreements.
- **Deliberate misrepresentation** — hiding facts from the insurer.

## Fraud Detection Techniques

- Anomaly detection — claims far outside historical patterns.
- Duplicate document detection — identical extracts (SHA-256) flag later uploads.
- Duplicate claim identification — same policy, incident date and amount.
- Identity inconsistency checks — name, ID, address mismatches.
- Unusual claims frequency — clusters of claims on one policy.
- Suspicious payment patterns — payments to new or third-party beneficiaries.
- Relationship and network analysis — linked customers, agents, providers.
- Historical claims comparisons — current claims vs. same policy's history.
- Risk scoring — fraud likelihood from the AI fraud engine (High/Critical).
- Predictive fraud analytics — trend-based exposure forecasting.

## Digital Forensics

- Document metadata examination — creation/modification timestamps,
  generators, printer traces.
- Image manipulation indicators — EXIF data, cloning artefacts.
- Document alteration detection — signature/seal evidence, ink analysis.
- OCR extraction analysis — confidence scores, inconsistent field data.
- Evidence preservation — chain of custody, hash records on receipt.
- Evidence classification — supporting, independent, inconclusive.
- Investigation documentation — notes, timeline, and access audit trail.

## Investigation Procedures

1. Open an investigation for the flagged claim (case number allocated).
2. Review the suspicious claim against documentation and indicators.
3. Collect supporting evidence — documents, OCR data, payment records,
   customer history, related claims.
4. Record investigation findings — timeline, evidence reviewed, analysis.
5. Escalate — if external input is needed (legal, bank, insurer of record).
6. Prepare investigation reports — structured summary for management and
   external regulators.
7. Record outcomes — confirmed fraud, cleared (no fraud), or
   inconclusive (as applicable).

## FAQs

- Why was this claim classified as high risk?
- What are the common indicators of insurance fraud?
- How can I identify a potentially altered document?
- What evidence should I collect?
- Are there similar claims in the historical records?
- How should I document my investigation findings?

## Escalation

 escalate confirmed fraud to your Claims Manager and to Executive
Management; escalate external disputes to Compliance. Report evidence to
Compliance for regulatory submission as required.

## Restricted Information

Investigations you own only. Claims your SIU unit is not assigned to are not
visible. External party details (banking, litigation) must be handled per
fraud-evidence rules.
