from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..services.db import get_db
from ..models.sqlalchemy_models import Claim, FraudAssessment, Investigation, User
from ..dependencies import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["Executive Analytics & Dashboard"])

@router.get("/overview", summary="Get comprehensive executive dashboard metrics and fraud risk trends")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    total_claims = db.query(Claim).count()
    total_analysed = db.query(FraudAssessment).count()
    
    # Risk breakdowns
    low_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Low").count()
    medium_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Medium").count()
    high_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "High").count()
    critical_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Critical").count()

    # Investigations
    under_investigation = db.query(Investigation).filter(Investigation.status.in_(["open", "in_review", "escalated"])).count()
    confirmed_fraud = db.query(Investigation).filter(Investigation.status == "confirmed_fraud").count()
    cleared_claims = db.query(Investigation).filter(Investigation.status == "cleared").count()

    # Financial Exposure & Prevented Losses
    total_exposure = db.query(func.sum(Claim.amount)).scalar() or 0.0
    
    # Financial prevented losses from confirmed fraud + critical flagged holds
    confirmed_fraud_claim_ids = [inv.claim_id for inv in db.query(Investigation).filter(Investigation.status == "confirmed_fraud").all()]
    prevented_losses = (
        db.query(func.sum(Claim.amount))
        .filter(Claim.id.in_(confirmed_fraud_claim_ids))
        .scalar() or 0.0
    )

    # Top recent suspicious claims
    suspicious_claims_q = (
        db.query(FraudAssessment)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.assessed_at))
        .limit(6)
        .all()
    )

    recent_suspicious = []
    for a in suspicious_claims_q:
        c = a.claim
        if c:
            recent_suspicious.append({
                "claim_id": c.claim_id,
                "policy_number": c.policy.policy_number if c.policy else "",
                "customer_name": c.customer.name if c.customer else "",
                "claim_type": c.claim_type,
                "amount": c.amount,
                "risk_score": a.risk_score,
                "risk_category": a.risk_category,
                "status": c.status,
                "top_indicator": a.indicators[0].get("detail", "Multiple risk factors") if (a.indicators and len(a.indicators) > 0) else "Risk threshold exceeded",
                "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
            })

    # Risk distribution percentages
    analysed_count = total_analysed if total_analysed > 0 else 1
    risk_distribution = [
        {"name": "Low Risk (0-29)", "count": low_risk, "percentage": round((low_risk / analysed_count) * 100, 1), "color": "#10B981"},
        {"name": "Medium Risk (30-59)", "count": medium_risk, "percentage": round((medium_risk / analysed_count) * 100, 1), "color": "#F59E0B"},
        {"name": "High Risk (60-79)", "count": high_risk, "percentage": round((high_risk / analysed_count) * 100, 1), "color": "#F97316"},
        {"name": "Critical Risk (80-100)", "count": critical_risk, "percentage": round((critical_risk / analysed_count) * 100, 1), "color": "#EF4444"},
    ]

    # Product category breakdown
    products_q = db.query(Claim.claim_type, func.count(Claim.id), func.sum(Claim.amount)).group_by(Claim.claim_type).all()
    product_stats = [
        {"claim_type": p[0], "count": p[1], "total_amount": round(float(p[2] or 0), 2)}
        for p in products_q
    ]

    return {
        "kpis": {
            "total_claims_received": total_claims,
            "claims_analysed_by_ai": total_analysed,
            "high_risk_claims": high_risk,
            "critical_risk_claims": critical_risk,
            "claims_under_investigation": under_investigation,
            "confirmed_fraud_claims": confirmed_fraud,
            "cleared_claims": cleared_claims,
            "total_claim_exposure_usd": round(total_exposure, 2),
            "prevented_fraud_losses_usd": round(prevented_losses, 2),
            "ai_coverage_rate": round((total_analysed / total_claims * 100), 1) if total_claims > 0 else 100.0,
        },
        "risk_distribution": risk_distribution,
        "product_breakdown": product_stats,
        "recent_suspicious_claims": recent_suspicious,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/network-graph", summary="Get entity relationship network graph for fraud intelligence and collusion detection")
async def get_network_graph(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Provides explainable graph relationships across claims, policyholders, beneficiaries, and shared contacts from real database records."""
    from ..services.fraud_network import build_fraud_network, get_network_insights

    network = build_fraud_network(db)
    insights = get_network_insights(db)
    raw_nodes = network.get("nodes", [])
    raw_edges = network.get("edges", [])

    nodes = [
        {
            "id": n["id"],
            "label": n.get("name") or n.get("entity_key") or n["id"],
            "type": n.get("entity_type", "entity"),
            "risk": "Critical" if (n.get("risk_score", 0) >= 80) else ("High" if n.get("risk_score", 0) >= 60 else ("Medium" if n.get("risk_score", 0) >= 30 else "Low")),
            "detail": f"{n.get('entity_type', '').title()} · Key: {n.get('entity_key', '')} · Edges: {n.get('total_edges', 0)}",
            "is_suspicious": bool(n.get("is_suspicious")),
            "risk_score": n.get("risk_score", 0),
        }
        for n in raw_nodes
    ]
    links = [
        {
            "source": e.get("node_a_id") or e.get("source"),
            "target": e.get("node_b_id") or e.get("target"),
            "relation": e.get("relationship_type", "RELATED"),
            "severity": "critical" if e.get("is_suspicious") else "normal",
            "evidence": e.get("evidence", ""),
        }
        for e in raw_edges
    ]
    clusters = insights.get("clusters", [])
    critical_links = sum(1 for l in links if l["severity"] == "critical")

    return {
        "nodes": nodes,
        "links": links,
        "clusters": clusters,
        "summary": {
            "total_nodes": len(nodes),
            "total_links": len(links),
            "collusion_clusters_identified": len(clusters),
            "critical_link_count": critical_links,
        },
    }


@router.get("/model-governance", summary="Get model performance metrics, drift indicators, and model registry")
async def get_model_governance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Returns AI model governance metrics computed from real database assessments and investigation outcomes."""
    from ..core.config import settings
    from ..services.model_performance import compute_model_performance_metrics, get_model_performance_history

    perf = compute_model_performance_metrics(db)
    history = get_model_performance_history(db, limit=10)
    total_analysed = db.query(FraudAssessment).count()
    metrics = perf.get("metrics", {})

    def _pct(value):
        """model_performance returns ratios; the governance API exposes percentages."""
        return round(value * 100, 2) if value is not None else None

    return {
        "active_model": {
            "name": "NEXA Hybrid Ensemble Engine",
            "version": settings.MODEL_VERSION,
            "status": "Active",
            "algorithm": "Heuristic Rules + Statistical Isolation + Forensic Fingerprint",
            "validation_note": (
                "Precision/recall are calculated only from investigations with confirmed outcomes; "
                "null means insufficient reviewed data, not perfect performance."
            ),
        },
        "metrics": {
            "precision": _pct(metrics.get("precision")),
            "recall": _pct(metrics.get("recall")),
            "f1_score": _pct(metrics.get("f1_score")),
            "false_positive_rate": _pct(metrics.get("false_positive_rate")),
            "claims_processed": total_analysed,
            "evaluated_investigations": metrics.get("total_confirmed_fraud_cases", 0) + metrics.get("false_positives", 0),
        },
        "drift_indicators": {
            "feature_drift_status": "NOT_EVALUATED",
            "last_drift_check": None,
        },
        "confusion_matrix": {
            "true_positives": metrics.get("true_positives", 0),
            "false_positives": metrics.get("false_positives", 0),
            "true_negatives": metrics.get("true_negatives", 0),
            "false_negatives": metrics.get("false_negatives", 0),
        },
        "model_registry": history,
    }

