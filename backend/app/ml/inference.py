from typing import Any, Dict, List, Optional
from .fraud_engine import fraud_engine

def assess_claim_fraud(
    features_or_claim: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    ocr_results: Optional[List[Dict[str, Any]]] = None,
    beneficiary_name: Optional[str] = None,
    recent_beneficiary_change: bool = False,
) -> Dict[str, Any]:
    """Evaluates a claim for fraud risk using the multi-layered FraudDetectionEngine."""
    # Handle flat features dict passed from older handlers
    if policy_data is None:
        policy_data = {
            "policy_number": features_or_claim.get("policy_number", "POL-UNKNOWN"),
            "policy_type": features_or_claim.get("policy_type", "Life"),
            "effective_date": features_or_claim.get("effective_date", "2024-01-01"),
            "coverage_amount": features_or_claim.get("coverage_amount", 50000.0),
        }
    if customer_data is None:
        customer_data = {
            "customer_id": features_or_claim.get("customer_id", "CUST-UNKNOWN"),
            "national_id": features_or_claim.get("national_id", "63-123456-X-00"),
        }
    if historical_claims is None:
        hist_len = int(features_or_claim.get("customer_history_len", 0))
        historical_claims = [
            {"claim_id": f"HIST-{i}", "amount": 10000.0, "incident_date": "2023-01-01"}
            for i in range(hist_len)
        ]

    # Run full engine
    return fraud_engine.evaluate_claim(
        claim_data=features_or_claim,
        policy_data=policy_data,
        customer_data=customer_data,
        historical_claims=historical_claims,
        ocr_results=ocr_results,
        beneficiary_name=beneficiary_name,
        recent_beneficiary_change=recent_beneficiary_change,
    )
