"""AI Model Performance Dashboard & Controlled Retraining (Phase 13).

Computes fraud-detection model metrics from the relational database:

- Accuracy-equivalent (risk_score >= threshold vs investigation status as proxy
  for confirmed fraud), precision, recall, F1, false-positive and
  false-negative rates.
- Claims assessed, flagged, confirmed, unconfirmed suspicious.
- Model versions from fraud_engine.MODEL_VERSION and ModelPerformance records.
- Retraining workflow: requests, dataset validation, approval before deploy.

Honesty rules: metrics use confirmed-investigation outcomes as the labelled
signal where available; unconfirmed suspicious cases are reported separately.
Never auto-retrain using unverified fraud allegations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.sqlalchemy_models import (
    FraudAssessment, Investigation, ModelPerformance, ModelRetrainingRequest,
    User,
)
from ..services.db import Base  # noqa: F401  (anchor)

from ..ml.fraud_engine import fraud_engine

HIGH_RISK = ("High", "Critical")
CONFIRMED = "confirmed_fraud"


def _model_versions(db: Session) -> List[Dict[str, Any]]:
    versions = []
    seen = set()
    # Historical ModelPerformance records
    for row in (
        db.query(ModelPerformance)
        .order_by(ModelPerformance.evaluated_at.desc()).limit(10).all()
    ):
        key = f"{row.model_name}:{row.version}"
        if key in seen:
            continue
        seen.add(key)
        versions.append({
            "model_name": row.model_name,
            "version": row.version,
            "precision": row.precision,
            "recall": row.recall,
            "f1_score": row.f1_score,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        })
    # Current engine version
    if fraud_engine.version not in seen:
        versions.append({
            "model_name": "fraud-engine-ensemble",
            "version": fraud_engine.version,
            "precision": None,
            "recall": None,
            "f1_score": None,
            "evaluated_at": None,
        })
    return versions[:10]


def compute_model_performance_metrics(db: Session, high_threshold: Optional[int] = None) -> Dict[str, Any]:
    """Computes fraud-detection performance metrics from validated data."""
    high_th = high_threshold if high_threshold is not None else settings.RISK_THRESHOLD_HIGH_MAX

    assessments = db.query(FraudAssessment).all()
    investigations = {inv.claim_id: inv for inv in db.query(Investigation).all()}

    # Labelled positives: investigation outcome == confirmed_fraud
    tp = fp = fn = tn = 0
    for a in assessments:
        claim_id = a.claim_id
        flagged = (a.risk_score or 0) >= high_th
        inv = investigations.get(claim_id)
        confirmed = bool(inv and inv.status == CONFIRMED)
        if confirmed and flagged:
            tp += 1
        elif confirmed and not flagged:
            fn += 1
        elif not confirmed and flagged:
            fp += 1
        else:
            tn += 1

    total_confirmed = tp + fn
    total_flagged = tp + fp
    total = len(assessments)
    precision = round(tp / total_flagged, 4) if total_flagged else None
    recall = round(tp / total_confirmed, 4) if total_confirmed else None
    f1 = (round((2 * precision * recall) / (precision + recall), 4)
          if (precision and recall and precision + recall > 0) else None)
    fp_rate = round(fp / total, 4) if total else 0.0
    fn_rate = round(fn / total, 4) if total else 0.0
    accuracy_proxy = round((tp + tn) / total, 4) if total else None

    # Data quality indicators
    data_quality = {
        "assessments_with_explanation": sum(1 for a in assessments if a.explanation),
        "assessments_with_indicators": sum(1 for a in assessments if a.indicators),
        "assessments_missing_model_version": sum(1 for a in assessments if not a.model_version),
        "total": total,
    }

    return {
        "metrics": {
            "accuracy_proxy_flagged_confirmed_or_clear": accuracy_proxy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "false_positive_rate": fp_rate,
            "false_negative_rate": fn_rate,
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "total_confirmed_fraud_cases": total_confirmed,
            "total_flagged_for_review": total_flagged,
        },
        "claims_assessed": total,
        "claims_flagged": total_flagged,
        "confirmed_fraud_cases": total_confirmed,
        "unconfirmed_suspicious_cases": fp,
        "risk_distribution": {
            "low": sum(1 for a in assessments if a.risk_category == "Low"),
            "medium": sum(1 for a in assessments if a.risk_category == "Medium"),
            "high": sum(1 for a in assessments if a.risk_category == "High"),
            "critical": sum(1 for a in assessments if a.risk_category == "Critical"),
        },
        "model_versions": _model_versions(db),
        "data_quality": data_quality,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "threshold_used_for_flagging": high_th,
        "honesty_note": (
            "Accuracy proxy counts TP/TN vs Investigation.status == 'confirmed_fraud'; "
            "unconfirmed suspicious cases are reported separately and never used for "
            "training without additional verification."
        ),
    }


def get_model_performance_history(db: Session, limit: int = 30) -> List[Dict[str, Any]]:
    rows = db.query(ModelPerformance).order_by(ModelPerformance.evaluated_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "model_name": r.model_name,
            "version": r.version,
            "precision": r.precision,
            "recall": r.recall,
            "f1_score": r.f1_score,
            "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Controlled Retraining Workflow (Phase 13)
# ---------------------------------------------------------------------------

def request_model_retraining(
    db: Session,
    *,
    requested_by_id: int,
    new_model_version: str,
    base_model_version: Optional[str] = None,
    dataset_version: str,
    dataset_records: Optional[int] = None,
    training_method: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Opens a retraining request. Deployment requires explicit approval."""
    req = ModelRetrainingRequest(
        requested_by_id=requested_by_id,
        new_model_version=new_model_version,
        base_model_version=base_model_version,
        dataset_version=dataset_version,
        dataset_records=dataset_records,
        training_method=training_method,
        status="requested",
        notes=notes,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _serialize_retraining_request(req)


def _serialize_retraining_request(req: ModelRetrainingRequest) -> Dict[str, Any]:
    return {
        "id": req.id,
        "new_model_version": req.new_model_version,
        "base_model_version": req.base_model_version,
        "dataset_version": req.dataset_version,
        "dataset_records": req.dataset_records,
        "training_method": req.training_method,
        "status": req.status,
        "requested_by": req.requested_by.username if req.requested_by else None,
        "approved_by": req.approved_by.username if req.approved_by else None,
        "notes": req.notes,
        "requested_at": req.requested_at.isoformat() if req.requested_at else None,
        "approved_at": req.approved_at.isoformat() if req.approved_at else None,
        "deployed_at": req.deployed_at.isoformat() if req.deployed_at else None,
        "evaluated_at": req.evaluated_at.isoformat() if req.evaluated_at else None,
    }


def approve_retraining_request(db: Session, request_id: int, approver_user_id: int) -> Dict[str, Any]:
    req = db.query(ModelRetrainingRequest).filter(ModelRetrainingRequest.id == request_id).first()
    if not req:
        raise ValueError(f"Retraining request {request_id} not found.")
    if req.status != "requested":
        raise ValueError(f"Retraining request is '{req.status}', cannot approve.")
    req.status = "approved"
    req.approved_by_id = approver_user_id
    req.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return _serialize_retraining_request(req)


def deploy_retraining_request(db: Session, request_id: int) -> Dict[str, Any]:
    """Marks an approved retraining as deployed (controlled rollout marker)."""
    req = db.query(ModelRetrainingRequest).filter(ModelRetrainingRequest.id == request_id).first()
    if not req:
        raise ValueError(f"Retraining request {request_id} not found.")
    if req.status != "approved":
        raise ValueError(f"Retraining request is '{req.status}', cannot deploy.")
    req.status = "deployed"
    req.deployed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return _serialize_retraining_request(req)


def reject_retraining_request(db: Session, request_id: int, approver_user_id: int,
                              reason: Optional[str] = None) -> Dict[str, Any]:
    req = db.query(ModelRetrainingRequest).filter(ModelRetrainingRequest.id == request_id).first()
    if not req:
        raise ValueError(f"Retraining request {request_id} not found.")
    if req.status in ("approved", "deployed"):
        raise ValueError("Cannot reject a request that is already approved/deployed.")
    req.status = "rejected"
    req.approved_by_id = approver_user_id
    req.approved_at = datetime.now(timezone.utc)
    req.notes = (req.notes or "") + f" [Rejected] {reason or ''}".strip()[:500]
    db.commit()
    db.refresh(req)
    return _serialize_retraining_request(req)


def list_retraining_requests(db: Session, status: Optional[str] = None,
                             limit: int = 30) -> List[Dict[str, Any]]:
    q = db.query(ModelRetrainingRequest).order_by(ModelRetrainingRequest.requested_at.desc())
    if status:
        q = q.filter(ModelRetrainingRequest.status == status)
    return [_serialize_retraining_request(r) for r in q.limit(limit).all()]


def get_data_retention_settings() -> Dict[str, Any]:
    """Document retention controls used by the Model Performance dashboard."""
    return {
        "assessment_retention_days": 365,
        "evidence_retention_days": 1825,  # 5 years
        "audit_retention_days": 3650,     # 10 years
        "training_dataset_retention_days": 730,
        "audit_note": "Retention settings are platform defaults; administrators may adjust them.",
    }
