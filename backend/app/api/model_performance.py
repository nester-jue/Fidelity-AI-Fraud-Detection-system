"""AI Model Performance Dashboard & Learning Centre API (Phase 13).

Computes fraud-detection model metrics from validated data, serves model
versions, and exposes the controlled retraining workflow
(request → approval → deploy → rollback capability).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user, require_roles
from ..models.sqlalchemy_models import RoleEnum
from ..services import model_performance
from ..services.db import get_db

router = APIRouter(prefix="/model-performance", tags=["AI Model Performance and Learning Centre"])


class RetrainingRequest(BaseModel):
    new_model_version: str
    base_model_version: Optional[str] = None
    dataset_version: str
    dataset_records: Optional[int] = None
    training_method: Optional[str] = None
    notes: Optional[str] = None


@router.get("/dashboard", summary="Fraud detection model performance dashboard metrics")
async def model_performance_dashboard(
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    return model_performance.compute_model_performance_metrics(db)


@router.get("/metrics", summary="Calculated fraud detection metrics (TP/TN vs confirmed investigations)")
async def model_metrics(
    high_threshold: Optional[int] = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    data = model_performance.compute_model_performance_metrics(db, high_threshold=high_threshold)
    return {"metrics": data["metrics"]}


@router.get("/versions", summary="Model versions with historical metrics")
async def model_versions(
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> List[Dict[str, Any]]:
    return model_performance._model_versions(db)


@router.get("/history", summary="Historical model performance evaluations")
async def model_history(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> List[Dict[str, Any]]:
    return model_performance.get_model_performance_history(db, limit=limit)


@router.get("/supervised-model", summary="Supervised fraud model status (advisory only; nothing invented)")
async def supervised_model_status(
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    """Honest supervised-model monitoring payload from the saved artifact.

    Reports installed/enabled, version, last training date, training rows,
    ROC-AUC, PR-AUC, precision, recall, F1, decision threshold, sources and
    known/training-data limitations. Unavailable metrics are null, never
    invented. A missing or invalid artifact does not break the rule engine.
    """
    from ..ml import supervised
    return supervised.describe_model()


@router.get("/data-retention", summary="Data retention settings for model artefacts")
async def data_retention() -> Dict[str, Any]:
    return model_performance.get_data_retention_settings()


@router.post("/requests", summary="Open a controlled model retraining request")
async def open_retraining_request(
    request: RetrainingRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return model_performance.request_model_retraining(
        db,
        requested_by_id=current_user.id,
        new_model_version=request.new_model_version,
        base_model_version=request.base_model_version,
        dataset_version=request.dataset_version,
        dataset_records=request.dataset_records,
        training_method=request.training_method,
        notes=request.notes,
    )


@router.get("/requests", summary="List retraining requests")
async def list_retraining_requests(
    status: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    return model_performance.list_retraining_requests(db, status=status, limit=limit)


@router.put("/requests/{request_id}/approve", summary="Approve a retraining request (admin)")
async def approve_retraining_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    return model_performance.approve_retraining_request(db, request_id, current_user.id)


@router.put("/requests/{request_id}/deploy", summary="Mark an approved retraining as deployed")
async def deploy_retraining_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    return model_performance.deploy_retraining_request(db, request_id)


@router.put("/requests/{request_id}/reject", summary="Reject a retraining request (admin)")
async def reject_retraining_request(
    request_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    return model_performance.reject_retraining_request(db, request_id, current_user.id, reason)
