"""Predictive Fraud Risk Monitoring API (Phase 11).

Proactive risk alerts generated from claim/customer data; distinct from
confirmed fraud (never labeled as such — human review decides).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user
from ..services import predictive_monitoring
from ..services.db import get_db

router = APIRouter(prefix="/predictive", tags=["Predictive Fraud Risk Monitoring"])


@router.post("/scan", summary="Run a predictive monitoring scan and create new alerts")
async def scan_predictive(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    alerts = predictive_monitoring.scan_for_pending_alerts(db)
    return {
        "message": f"Predictive monitoring scan completed. {len(alerts)} new alert(s) generated.",
        "new_alerts": alerts,
        "honesty_note": (
            "Predictive alerts describe risk patterns for human review; "
            "they are not confirmed fraud."
        ),
    }


@router.get("/alerts", summary="List predictive alerts")
async def list_alerts(
    status: Optional[str] = Query(None, description="new | acknowledged | resolved | dismissed"),
    severity: Optional[str] = Query(None, description="INFO | WARNING | HIGH | CRITICAL"),
    limit: int = Query(100, ge=1, le=200),
    include_dismissed: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    return predictive_monitoring.get_alerts(
        db, status=status, severity=severity, limit=limit, include_dismissed=include_dismissed,
    )


@router.get("/alerts/{alert_id}", summary="Get a predictive alert detail")
async def get_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    recs = predictive_monitoring.get_alerts(db, limit=500)
    for r in recs:
        if r["id"] == alert_id:
            return r
    raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")


@router.put("/alerts/{alert_id}/acknowledge", summary="Acknowledge a predictive alert")
async def acknowledge(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    result = predictive_monitoring.acknowledge_alert(db, alert_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found or already resolved/dismissed.")
    return result


@router.put("/alerts/{alert_id}/resolve", summary="Resolve a predictive alert (human decision)")
async def resolve(
    alert_id: int,
    resolution_note: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    result = predictive_monitoring.resolve_alert(db, alert_id, current_user.id, resolution_note)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found or already resolved.")
    return result


@router.put("/alerts/{alert_id}/dismiss", summary="Dismiss a predictive alert (human decision)")
async def dismiss(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    result = predictive_monitoring.dismiss_alert(db, alert_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return result


@router.get("/summary", summary="Predictive alert summary by severity and status")
async def predictive_summary(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from sqlalchemy import func
    alerts = predictive_monitoring.get_alerts(db, limit=500)
    by_severity: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for a in alerts:
        by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1
        by_type[a["alert_type"]] = by_type.get(a["alert_type"], 0) + 1
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
    return {
        "total": len(alerts),
        "new": by_status.get("new", 0),
        "acknowledged": by_status.get("acknowledged", 0),
        "resolved": by_status.get("resolved", 0),
        "dismissed": by_status.get("dismissed", 0),
        "by_severity": by_severity,
        "by_alert_type": by_type,
    }
