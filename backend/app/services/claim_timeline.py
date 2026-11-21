"""Claim Timeline Intelligence (Phase 6).

Reconstructs the chronological history of a claim from the relational
database and related services:

1. Policy registration (Customer.created_at).
2. Policy activation (Policy.effective_date).
3. Beneficiary changes (ClaimBeneficiaryChange + Claim.beneficiary_last_change_date).
4. Incident occurrence (Claim.incident_date).
5. Claim registration (Claim.submission_date).
6. Document submission (ClaimDocument.uploaded_at).
7. OCR processing (OCRDocument.processed_at).
8. AI fraud assessment (FraudAssessment.assessed_at).
9. Investigation initiation (Investigation.opened_at).
10. Investigation actions (InvestigationNote.created_at).
11. Investigation outcome (Investigation.closed_at).
12. Claim decision (Claim.updated_at for terminal statuses).

Uses ONLY actual database records (never fabricates events). Reports
missing steps and inconsistent sequences as findings for human review.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..models.sqlalchemy_models import (
    Claim, ClaimBeneficiaryChange, ClaimDocument, ClaimNote, Investigation,
    InvestigationNote, OCRDocument, Policy, User,
)

TERMINAL_STATUSES = {"approved", "rejected", "closed", "cleared", "confirmed_fraud"}

# Display order for the event types.
EVENT_ORDER: List[Tuple[str, str]] = [
    ("customer_registered", "Policy Registration"),
    ("policy_activated", "Policy Activation"),
    ("beneficiary_changed", "Beneficiary Changes"),
    ("incident_occurred", "Incident Occurrence"),
    ("claim_submitted", "Claim Registration"),
    ("documents_submitted", "Document Submission"),
    ("ocr_processed", "OCR Processing"),
    ("fraud_assessed", "AI Fraud Assessment"),
    ("investigation_opened", "Investigation Initiation"),
    ("investigation_actions", "Investigation Actions"),
    ("investigation_closed", "Investigation Outcome"),
    ("claim_decided", "Claim Decision"),
]


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def build_claim_timeline(db: Session, claim_id: int) -> Dict[str, Any]:
    """Builds the full timeline + anomaly findings for one claim."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return {"claim_id": claim_id, "events": [], "anomalies": [],
                "summary": {"total_events": 0, "missing_steps": [], "inconsistencies": []}}

    events: List[Dict[str, Any]] = []

    def add(event_type: str, timestamp: Optional[datetime], description: str,
            source: str, sequence: Optional[int] = None, fabricated: bool = False):
        if not timestamp:
            return
        events.append({
            "event_type": event_type,
            "timestamp": timestamp,
            "description": description,
            "source": source,
            "sequence_order": sequence,
            "is_fabricated": fabricated,
        })

    # 1. Policy registration
    policy = db.query(Policy).filter(Policy.id == claim.policy_id).first()
    if claim.customer and claim.customer.created_at:
        add("customer_registered", claim.customer.created_at,
            f"Policyholder '{claim.customer.name}' registered in the claims system.",
            "customer_record")
    # 2. Policy activation
    if policy:
        add("policy_activated", policy.effective_date,
            f"Policy {policy.policy_number} (type: {policy.policy_type}) became effective.",
            "policy_record")
    # 3. Beneficiary changes (from dedicated history table + claim-level field)
    changes: List[ClaimBeneficiaryChange] = (
        db.query(ClaimBeneficiaryChange).filter(ClaimBeneficiaryChange.claim_id == claim.id)
        .order_by(ClaimBeneficiaryChange.changed_at).all()
    )
    for ch in changes:
        add("beneficiary_changed", ch.changed_at,
            f"Beneficiary altered to '{ch.beneficiary_name or 'n/a'}'"
            + (f" (NIN: {ch.beneficiary_nin})" if ch.beneficiary_nin else "")
            + (f". {ch.notes}" if ch.notes else ""),
            "beneficiary_history", fabricated=False)
    if not changes and claim.beneficiary_last_change_date and claim.beneficiary_name:
        add("beneficiary_changed", claim.beneficiary_last_change_date,
            f"Beneficiary '{claim.beneficiary_name}' noted on claim.",
            "claim_record", fabricated=False)
    # 4. Incident occurrence
    add("incident_occurred", claim.incident_date,
        f"Incident occurred for claim ({claim.claim_type}).", "claim_record")
    # 5. Claim registration
    add("claim_submitted", claim.submission_date,
        f"Claim {claim.claim_id} registered ({claim.claim_type}).", "claim_record")
    # 6. Document submission
    for doc in db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim.id).order_by(ClaimDocument.uploaded_at).all():
        add("documents_submitted", doc.uploaded_at, f"Document '{doc.filename}' uploaded.",
            "claim_document_record")
    # 7. OCR processing
    for odoc in db.query(OCRDocument).filter(OCRDocument.claim_id == claim.id).order_by(OCRDocument.processed_at).all():
        if odoc.processed_at:
            add("ocr_processed", odoc.processed_at,
                f"Document '{odoc.filename}' processed by {odoc.ocr_engine or 'OCR engine'} "
                f"(status: {odoc.processing_status}).",
                "ocr_record")
    # 8. AI fraud assessment
    if claim.assessment and claim.assessment.assessed_at:
        add("fraud_assessed", claim.assessment.assessed_at,
            f"AI fraud assessment completed: {claim.assessment.risk_category} "
            f"(score {claim.assessment.risk_score}/100).",
            "fraud_engine")
    # 9. Investigation initiation
    investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
    if investigation:
        add("investigation_opened", investigation.opened_at,
            f"Investigation case #{investigation.id} opened (status: {investigation.status}).",
            "investigation_record")
        # 10. Investigation actions
        notes = (
            db.query(InvestigationNote)
            .filter(InvestigationNote.investigation_id == investigation.id)
            .order_by(InvestigationNote.created_at).all()
        )
        for n in notes:
            add("investigation_actions", n.created_at,
                f"Investigation action: {(n.note or '')[:200]}",
                "investigation_note")
        # 11. Investigation outcome
        if investigation.closed_at:
            add("investigation_closed", investigation.closed_at,
                f"Investigation closed (outcome: {investigation.outcome or 'unknown'}).",
                "investigation_record")
    # 12. Claim decision
    if claim.status in TERMINAL_STATUSES:
        add("claim_decided", claim.updated_at,
            f"Claim decision recorded (status: {claim.status}).", "claim_record")

    # Sort chronologically, track anomalies.
    events.sort(key=lambda e: (e["timestamp"], e["sequence_order"] is None, e["sequence_order"] or 0))
    anomalies: List[Dict[str, Any]] = []
    claim_submission_dt = claim.submission_date
    fraud_assessed_dt = claim.assessment.assessed_at if claim.assessment else None

    # Unusual sequences: document OCR/fraud assessment ordered oddly vs submission
    for e in events:
        if e["event_type"] in ("ocr_processed",) and claim_submission_dt and e["timestamp"] < claim_submission_dt:
            pass  # normal: OCR before submission
        if e["event_type"] == "ocr_processed" and fraud_assessed_dt and e["timestamp"] > fraud_assessed_dt:
            anomalies.append({
                "anomaly_id": f"ANOM-ocr-after-assess-{e['event_type']}",
                "type": "UNUSUAL_SEQUENCE",
                "event_type": e["event_type"],
                "description": "OCR processing occurred AFTER the AI fraud assessment completed.",
                "severity": "low",
            })
        if e["event_type"] in ("claim_decided",) and fraud_assessed_dt and e["timestamp"] < fraud_assessed_dt:
            anomalies.append({
                "anomaly_id": f"ANOM-decision-before-assess-{e['event_type']}",
                "type": "MISSING_ASSESSMENT",
                "event_type": e["event_type"],
                "description": "Claim was decided before the AI fraud assessment ran — possible assessment gap.",
                "severity": "medium",
            })
        if e["event_type"] in ("documents_submitted", "claim_decided") and claim.submission_date and e["timestamp"] < claim.submission_date:
            anomalies.append({
                "anomaly_id": f"ANOM-pre-submission-{e['event_type']}",
                "type": "TIME_INCONSISTENCY",
                "event_type": e["event_type"],
                "description": f"{e['description']} occurred BEFORE claim registration (unexpected ordering).",
                "severity": "medium",
            })

    # Missing steps: record expected steps that are not present.
    missing: List[str] = []
    have = {e["event_type"] for e in events}
    if not any(t == "documents_submitted" for t in have):
        missing.append("DOCUMENT_SUBMISSION")
    if not any(t == "ocr_processed" for t in have):
        missing.append("OCR_PROCESSING")
    if not any(t == "fraud_assessed" for t in have):
        missing.append("FRAUD_ASSESSMENT")
    if not any(t == "investigation_opened" for t in have) and claim.status == "flagged":
        missing.append("INVESTIGATION_INITIATION")

    # Duplicate timestamps → tie check
    seen: Dict[datetime, List[str]] = {}
    for e in events:
        seen.setdefault(e["timestamp"], []).append(e["event_type"])
    ties = [ts for ts, types in seen.items() if len(types) > 1]
    if ties:
        anomalies.append({
            "anomaly_id": f"ANOM-timestamp-ties-{claim.id}",
            "type": "TIMESTAMP_TIE",
            "description": f"Multiple events share identical timestamps: {[t for ts in ties for t in seen[ts]]}",
            "severity": "low",
        })

    serialized = [
        {
            "event_type": e["event_type"],
            "display_label": next(
                (label for et, label in EVENT_ORDER if et == e["event_type"]),
                e["event_type"],
            ),
            "timestamp": _iso(e["timestamp"]),
            "description": e["description"],
            "source": e["source"],
            "sequence_order": e["sequence_order"],
            "is_fabricated": e["is_fabricated"],
        }
        for e in events
    ]

    span_days: Optional[float] = None
    if len(events) >= 2:
        span_days = (events[-1]["timestamp"] - events[0]["timestamp"]).total_seconds() / 86400.0

    return {
        "claim_id": claim.id,
        "claim_ref": claim.claim_id,
        "events": serialized,
        "anomalies": anomalies,
        "summary": {
            "total_events": len(events),
            "missing_steps": missing,
            "inconsistencies": [a["type"] for a in anomalies],
            "span_days": round(span_days, 1) if span_days is not None else None,
        },
    }


def get_claim_notes_summary(db: Session, claim_id: int) -> List[Dict[str, Any]]:
    """ClaimNotes with user attribution for investigator-facing timeline views."""
    notes = (
        db.query(ClaimNote)
        .filter(ClaimNote.claim_id == claim_id)
        .order_by(ClaimNote.created_at).all()
    )
    return [
        {
            "id": n.id,
            "text": n.note,
            "created_by": n.user.full_name or n.user.username if n.user else "Unknown",
            "created_at": _iso(n.created_at),
        }
        for n in notes
    ]
