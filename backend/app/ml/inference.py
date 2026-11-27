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
    """Evaluates a claim for fraud risk using the multi-layered FraudDetectionEngine.

    Training/inference honesty: missing live information is NOT silently
    replaced with dataset medians or FABRICATED values. When callers do not
    supply policy/customer data we pass only what is actually known; the
    engine and supervised layer apply documented, flagged imputation
    (feature_status) or treat fields as missing. No synthetic history,
    fake national IDs, fake effective dates, or fake coverage limits are
    created. ``customer_history_len`` is honoured honestly as a count
    (``previous_claims_count``) without inventing placeholder claims.
    """
    # Work on a copy; never mutate caller's dict.
    features = dict(features_or_claim or {})

    # Handle flat features dict passed from older handlers.
    if policy_data is None:
        policy_data = {
            "policy_number": features.get("policy_number", "POL-UNKNOWN"),
            "policy_type": features.get("policy_type", "Life"),
        }
        # only include keys that are genuinely provided (never fabricate)
        if features.get("effective_date") is not None:
            policy_data["effective_date"] = features.get("effective_date")
        if features.get("coverage_amount") is not None:
            policy_data["coverage_amount"] = features.get("coverage_amount")
    if customer_data is None:
        customer_data = {"customer_id": features.get("customer_id", "CUST-UNKNOWN")}
        # never inject a fake national id; absence -> UNVERIFIED_NATIONAL_IDENTITY
        for key in ("national_id", "date_of_birth", "country", "claimant_age"):
            if features.get(key) is not None:
                customer_data[key] = features.get(key)
    if historical_claims is None:
        # No fabricated synthetic history. Honour a real count if supplied.
        historical_claims = []
        hist_len = features.get("customer_history_len")
        if hist_len is not None and features.get("previous_claims_count") is None:
            try:
                features["previous_claims_count"] = max(0, int(hist_len))
            except (TypeError, ValueError):
                pass

    # Run full engine
    return fraud_engine.evaluate_claim(
        claim_data=features,
        policy_data=policy_data,
        customer_data=customer_data,
        historical_claims=historical_claims,
        ocr_results=ocr_results,
        beneficiary_name=beneficiary_name,
        recent_beneficiary_change=recent_beneficiary_change,
    )
