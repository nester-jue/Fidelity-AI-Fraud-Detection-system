"""Fraud Network Intelligence API (Phase 3).

Returns the relationship network graph, suspicious node/edge findings and
per-entity summaries. All endpoints are read-only; the platform never
auto-labels individuals as fraudulent — findings are presented for review.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user
from ..services import fraud_network
from ..services.db import get_db

router = APIRouter(prefix="/fraud-network", tags=["Fraud Network Intelligence"])


@router.get("/graph", summary="Full fraud relationship network graph")
async def get_network_graph(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return fraud_network.build_fraud_network(db)


@router.get("/insights", summary="Compact network insights for dashboards and the Copilot")
async def get_network_insights(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return fraud_network.get_network_insights(db)


@router.get("/entity/{entity_type}/{entity_key}", summary="Entity detail with connected neighbors")
async def get_entity_detail(
    entity_type: str,
    entity_key: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    net = fraud_network.build_fraud_network(db)
    id_prefix = {
        "customer": "CUST-", "policy": "POL-", "claim": "CLM-",
        "document": "OCR-", "beneficiary": "BENEF-", "payment_ref": "ACCT-",
    }.get(entity_type.lower(), "")
    target_id = f"{id_prefix}{entity_key}" if entity_type.lower() in id_prefix else entity_key
    node = next((n for n in net["nodes"] if n["id"] == target_id or n["entity_key"] == entity_key), None)
    if not node:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_key}' not found in the network.")
    connected = [e for e in net["edges"] if e["node_a_id"] == node["id"] or e["node_b_id"] == node["id"]]
    return {
        "entity": node,
        "connected_edges": connected,
        "honesty_note": "Connected entities may have legitimate relationships; the network surfaces suspicion for human review.",
    }


@router.get("/claim/{claim_id}", summary="Relationships around a specific claim")
async def get_claim_network(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import Claim
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    net = fraud_network.build_fraud_network(db)
    node_id = next((n["id"] for n in net["nodes"] if n.get("claim_id") == claim.id), None)
    claim_edges = [e for e in net["edges"]
                   if (node_id and node_id in (e["node_a_id"], e["node_b_id"]))
                   or f"CLM-{claim.id}:" in (e["node_a_id"], e["node_b_id"])]
    return {"claim_id": claim.claim_id, "claim_db_id": claim.id, "edges": claim_edges,
            "nodes": [n for n in net["nodes"] if n["id"] in {e["node_a_id"] for e in claim_edges} | {e["node_b_id"] for e in claim_edges}]}
