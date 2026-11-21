"""Predictive Fraud Risk Monitoring (Phase 11).

Proactive monitoring across the claim lifecycle. Evaluates data available
continuously (claims, beneficiary changes, network signals, OCR flags) and
creates PredictiveAlert records. Alerts are *predictive indicators* —
never confirmed fraud — and are presented to authorised users for review.

Hard honesty rule: alerts describe risk patterns for humans; nothing here
auto-rejects, auto-labels or auto-investigates.
"""

from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.sqlalchemy_models import (
    Claim, ClaimBeneficiaryChange, Customer, OCRDocument, PredictiveAlert,
    User,
)
from ..services import fraud_network
from .historical_behavior import compute_customer_claim_stats


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _customer_claims(db: Session, customer_id: int) -> List[Claim]:
    return db.query(Claim).filter(Claim.customer_id == customer_id).all()


def _alert(db: Session, *, alert_type: str, severity: str, description: str,
           evidence: str, claim_id: Optional[int] = None, customer_id: Optional[int] = None,
           policy_id: Optional[int] = None, risk_score: float = 0.0,
           status: str = "new") -> PredictiveAlert:
    record = PredictiveAlert(
        alert_type=alert_type,
        severity=severity,
        description=description,
        claim_id=claim_id,
        customer_id=customer_id,
        policy_id=policy_id,
        evidence_summary=evidence,
        risk_score=risk_score,
        status=status,
    )
    db.add(record)
    db.flush()  # assign id/generated_at for serialisation before commit
    return record


def scan_for_pending_alerts(db: Session, max_alerts: int = 50) -> List[Dict[str, Any]]:
    """Generates new predictive alerts from current data (idempotent per run).

    Returns the newly created alert summaries. Alerts describe *predictive
    risk indicators* and are never presented as confirmed fraud.
    """
    now = datetime.now(timezone.utc)
    created: List[Dict[str, Any]] = []

    customers = db.query(Customer).all()
    claims = db.query(Claim).all()

    # Index helper
    cust_claims_map: Dict[int, List[Claim]] = {}
    for c in claims:
        cust_claims_map.setdefault(c.customer_id, []).append(c)

    # --- 1. Unusual claim submission patterns (per customer) ---
    for cust in customers:
        cust_claims = [c for c in cust_claims_map.get(cust.id, []) if c.submission_date]
        if len(cust_claims) < 2:
            continue
        cust_claims.sort(key=lambda c: c.submission_date)
        for a, b in zip(cust_claims, cust_claims[1:]):
            gap_days = (b.submission_date - a.submission_date).days
            if gap_days <= 14:
                rec = _alert(
                    db, alert_type="UNUSUAL_SUBMISSION_PATTERN", severity="WARNING",
                    description=f"Unusually frequent claim submissions for {cust.name}: {a.claim_id} → {b.claim_id} ({gap_days} days apart).",
                    evidence=f"Customer {cust.customer_id}; claim IDs {a.claim_id}, {b.claim_id}; submission gap {gap_days} days.",
                    claim_id=b.id, customer_id=cust.id, policy_id=b.policy_id, risk_score=40.0,
                )
                created.append(_serialize(rec))
        # >2 claims in 30 days
        if len(cust_claims) >= 3:
            first, last = cust_claims[0].submission_date, cust_claims[-1].submission_date
            if (last - first).days <= 30 and len(cust_claims) >= 4:
                rec = _alert(
                    db, alert_type="HIGH_FREQUENCY_PATTERN", severity="WARNING",
                    description=f"Repeated high-frequency claims by {cust.name} ({len(cust_claims)} claims in {(last - first).days} days).",
                    evidence=f"Customer {cust.customer_id}; claims {[c.claim_id for c in cust_claims]}.",
                    customer_id=cust.id, risk_score=55.0,
                )
                created.append(_serialize(rec))

    # --- 2. Suspicious beneficiary changes (predictive) ---
    for cust in customers:
        changes = db.query(ClaimBeneficiaryChange).join(Claim).filter(
            Claim.customer_id == cust.id,
            ClaimBeneficiaryChange.changed_at >= now - timedelta(days=60),
        ).all()
        for ch in changes:
            claim_obj = db.query(Claim).filter(Claim.id == ch.claim_id).first()
            rec = _alert(
                db, alert_type="SUSPICIOUS_BENEFICIARY_CHANGE", severity="WARNING",
                description=f"Recent beneficiary change on claim {claim_obj.claim_id if claim_obj else ch.claim_id} ({cust.name}).",
                evidence=f"Customer {cust.customer_id}; change recorded {ch.changed_at.date().isoformat()}; notes: {ch.notes or 'n/a'}.",
                customer_id=cust.id, claim_id=ch.claim_id,
                policy_id=claim_obj.policy_id if claim_obj else None,
                risk_score=35.0,
            )
            created.append(_serialize(rec))

    # --- 3. Unusual claim amounts (statistical outlier) ---
    for cust in customers:
        cust_claims = [c for c in cust_claims_map.get(cust.id, []) if float(c.amount or 0) > 0]
        amounts = [float(c.amount) for c in cust_claims]
        if len(amounts) < 2:
            continue
        avg = mean(amounts); sd = pstdev(amounts)
        for c in cust_claims:
            if c.id and float(c.amount) > avg + 2 * sd and float(c.amount) > 20000:
                rec = _alert(
                    db, alert_type="UNUSUAL_CLAIM_AMOUNT", severity="WARNING",
                    description=f"Claim amount of {c.claim_id} is an outlier for customer {cust.name} (ZWL {float(c.amount):,.0f} vs avg ZWL {avg:,.0f}).",
                    evidence=f"Customer {cust.customer_id}; amount {float(c.amount):,.0f}; avg {avg:,.0f}; stdev {sd:,.0f}.",
                    claim_id=c.id, customer_id=cust.id, policy_id=c.policy_id, risk_score=45.0,
                )
                created.append(_serialize(rec))

    # --- 4. High-risk document submissions ---
    high_risk_docs = db.query(OCRDocument).filter(
        or_(
            OCRDocument.flags.contains("duplicate_document_hash"),
            OCRDocument.flags.contains("date_inconsistency"),
            OCRDocument.has_date_mismatch == True,  # noqa: E712
        )
    ).limit(20).all()
    for d in high_risk_docs:
        rec = _alert(
            db, alert_type="HIGH_RISK_DOCUMENT_SUBMISSION", severity="WARNING",
            description=f"Document '{d.filename}' carries forensic flags for review (doc ID {d.id}).",
            evidence=f"Flags: {d.flags}; hash: {(d.document_hash_sha256 or '')[:12]}…",
            claim_id=d.claim_id,
            risk_score=50.0,
        )
        created.append(_serialize(rec))

    # --- 5. Repeated claims with same type for same customer ---
    for cust in customers:
        type_map: Dict[str, List[Claim]] = {}
        for c in cust_claims_map.get(cust.id, []):
            type_map.setdefault(str(c.claim_type).lower(), []).append(c)
        for ctype, lst in type_map.items():
            if len(lst) >= 3:
                rec = _alert(
                    db, alert_type="REPEATED_CLAIM_TYPE", severity="WARNING",
                    description=f"Customer {cust.name} has {len(lst)} claims of type '{ctype}'.",
                    evidence=f"Customer {cust.customer_id}; claims {[c.claim_id for c in lst]}.",
                    customer_id=cust.id, risk_score=35.0,
                )
                created.append(_serialize(rec))

    # --- 6. Network signals (shared identity, suspicious edges) ---
    try:
        net = fraud_network.build_fraud_network(db)
        for edge in net["suspicious_edges"][:10]:
            if edge["relationship_type"] in ("SHARED_BENEFICIARY_ACROSS_POLICIES", "IDENTICAL_DOCUMENT_REUSE"):
                claim_ids = edge["claim_ids"] or []
                cust_id = None
                if claim_ids:
                    c0 = db.query(Claim).filter(Claim.id == claim_ids[0]).first()
                    cust_id = c0.customer_id if c0 else None
                rec = _alert(
                    db, alert_type="SUSPICIOUS_NETWORK_SIGNAL", severity="WARNING",
                    description=f"Network signal: {edge['relationship_type']} observed ({edge['evidence'][:120]}…).",
                    evidence=f"Relationship: {edge['relationship_type']}; strength {edge['strength']}; claims {claim_ids}.",
                    claim_id=claim_ids[0] if claim_ids else None,
                    customer_id=cust_id,
                    risk_score=round(edge["strength"] * 80, 1),
                )
                created.append(_serialize(rec))
    except Exception:
        # Network analysis failures must never break monitoring.
        pass

    # --- 7. Emerging fraud patterns (clusters) ---
    try:
        net = fraud_network.build_fraud_network(db)
        for cluster in net["clusters"]:
            if len(cluster["claim_ids"]) >= 2 and len(cluster["customer_ids"]) > 1:
                rec = _alert(
                    db, alert_type="EMERGING_PATTERN_CLUSTER", severity="WARNING",
                    description="Emerging fraud pattern: multiple claims involving connected parties observed.",
                    evidence=f"Claims: {cluster['claim_ids'][:5]}; customers: {cluster['customer_ids'][:5]}.",
                    risk_score=60.0,
                )
                created.append(_serialize(rec))
    except Exception:
        pass

    db.commit()
    return created[:max_alerts]


def _serialize(rec: PredictiveAlert) -> Dict[str, Any]:
    return {
        "id": rec.id,
        "alert_type": rec.alert_type,
        "severity": rec.severity,
        "description": rec.description,
        "evidence_summary": rec.evidence_summary,
        "risk_score": rec.risk_score,
        "status": rec.status,
        "claim_id": rec.claim_id,
        "customer_id": rec.customer_id,
        "policy_id": rec.policy_id,
        "generated_at": _iso(rec.generated_at),
    }


def get_alerts(db: Session, status: Optional[str] = None, severity: Optional[str] = None,
               limit: int = 100, include_dismissed: bool = True) -> List[Dict[str, Any]]:
    q = db.query(PredictiveAlert).order_by(PredictiveAlert.generated_at.desc())
    if status:
        q = q.filter(PredictiveAlert.status == status)
    if severity:
        q = q.filter(PredictiveAlert.severity == severity)
    if not include_dismissed:
        q = q.filter(PredictiveAlert.status != "dismissed")
    return [_serialize(a) for a in q.limit(limit).all()]


def acknowledge_alert(db: Session, alert_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    rec = db.query(PredictiveAlert).filter(PredictiveAlert.id == alert_id).first()
    if not rec or rec.status in ("resolved", "dismissed"):
        return None
    rec.status = "acknowledged"
    rec.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize(rec)


def resolve_alert(db: Session, alert_id: int, user_id: int, resolution_note: Optional[str] = None) -> Optional[Dict[str, Any]]:
    rec = db.query(PredictiveAlert).filter(PredictiveAlert.id == alert_id).first()
    if not rec or rec.status == "resolved":
        return None
    rec.status = "resolved"
    rec.resolved_at = datetime.now(timezone.utc)
    if resolution_note:
        rec.resolution_note = resolution_note
    db.commit()
    return _serialize(rec)


def dismiss_alert(db: Session, alert_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Dismissal is human-decided: the alert is marked dismissed (not 'confirmed fraud')."""
    rec = db.query(PredictiveAlert).filter(PredictiveAlert.id == alert_id).first()
    if not rec:
        return None
    rec.status = "dismissed"
    db.commit()
    return _serialize(rec)
