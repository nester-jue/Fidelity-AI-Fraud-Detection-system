"""Historical Claim Behaviour Intelligence (Phase 5).

Engine that compares a current claim against:

- The policyholder's prior claims (patterns of repetition, amounts, timing).
- Similar historical claims (same claim type, comparable amounts, same window).
- Relevant policy information (effective dates, coverage, claim type history).

All comparisons use real database records. Anomalies include the underlying
reason and are labelled ``potential`` — never confirmed fraud.
"""

import statistics
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.sqlalchemy_models import Claim, ClaimBeneficiaryChange, Customer, Policy

AMOUNT_SIMILARITY_RANGE = 0.25  # +/- 25% of current amount counts as "similar"
WINDOW_DAYS = 365               # claims within a year count as comparable


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")[:19]).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _days(a: Optional[datetime], b: Optional[datetime]) -> Optional[int]:
    if a and b:
        return (a - b).days
    return None


def _median(values: List[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def get_customer_claim_history(db: Session, customer_id: int) -> List[Claim]:
    """All claims ever filed by a customer (excluding the current claim)."""
    return (
        db.query(Claim)
        .filter(Claim.customer_id == customer_id)
        .order_by(Claim.submission_date).all()
    )


def compute_customer_claim_stats(db: Session, customer_id: int) -> Dict[str, Any]:
    claims = get_customer_claim_history(db, customer_id)
    amounts = [float(c.amount) for c in claims]
    submissions = [c.submission_date for c in claims if c.submission_date]
    return {
        "claim_count": len(claims),
        "total_amount": round(sum(amounts), 2) if amounts else 0.0,
        "avg_amount": round(statistics.mean(amounts), 2) if amounts else 0.0,
        "median_amount": _median(amounts),
        "stdev_amount": round(statistics.pstdev(amounts), 2) if len(amounts) > 1 else 0.0,
        "max_amount": round(max(amounts), 2) if amounts else 0.0,
        "min_amount": round(min(amounts), 2) if amounts else 0.0,
        "claims_per_30d": round(len(claims) / max(1, (submissions[-1] - submissions[0]).days / 30.0), 2)
        if len(submissions) > 1 else 0.0,
    }


def analyze_customer_history(db: Session, customer_id: int, current_claim_id: Optional[int] = None) -> Dict[str, Any]:
    """Unusual patterns in the policyholder's claim history (potential only)."""
    claims = [c for c in get_customer_claim_history(db, customer_id) if c.id != (current_claim_id or -1)]
    anomalies: List[Dict[str, Any]] = []
    notes: List[str] = []

    if len(claims) >= 2:
        amounts = [float(c.amount) for c in claims]
        avg = statistics.mean(amounts) if amounts else 0
        median = _median(amounts) or 0
        # Repeated claim patterns: similar type + amount clusters
        seen: Dict[Tuple[str, int], List[Claim]] = {}
        for c in claims:
            key = (str(c.claim_type).lower(), round(float(c.amount) / 100) * 100)
            seen.setdefault(key, []).append(c)
        for (ctype, aamt), group in sorted(seen.items()):
            if len(group) >= 3:
                dates = sorted(c.submission_date for c in group if c.submission_date)
                if len(dates) >= 3:
                    span = (dates[-1] - dates[0]).days
                    if span <= 180:
                        anomalies.append({
                            "type": "REPEATED_CLAIM_PATTERN",
                            "severity": "medium",
                            "evidence": (f"{len(group)} claims of type '{ctype}' around ZWL "
                                         f"{aamt:,.0f} within {span} days."),
                            "reason": "Similar claim types and amounts recur within a short window.",
                        })
        # Multiple claims shortly after policy activation per policy
        for pol in db.query(Policy).filter(Policy.customer_id == customer_id).all():
            early_claims = [c for c in claims
                            if c.policy_id == pol.id
                            and pol.effective_date
                            and (c.incident_date or c.submission_date or c.created_at)
                            and 0 <= ((c.incident_date or c.submission_date or c.created_at) - pol.effective_date).days <= 90]
            if len(early_claims) >= 2:
                anomalies.append({
                    "type": "MULTIPLE_EARLY_POST_ACTIVATION_CLAIMS",
                    "severity": "medium",
                    "evidence": f"{len(early_claims)} claims filed within 90 days of policy activation ({pol.policy_number}).",
                    "reason": "Cluster of claims filed shortly after policy start; check for short-circuit claims.",
                })
    if claims:
        avg = statistics.mean([float(c.amount) for c in claims])
        recent = claims[-1]
        if len(claims) >= 3 and float(recent.amount) > avg * 1.6:
            anomalies.append({
                "type": "UNUSUAL_AMOUNT_CHANGE",
                "severity": "medium",
                "evidence": f"Latest claim ZWL {float(recent.amount):,.0f} vs customer average ZWL {avg:,.0f}.",
                "reason": "Claim amount deviates substantially from the customer's historical average.",
            })
        submissions = sorted(c.submission_date for c in claims if c.submission_date)
        if len(submissions) >= 2:
            gaps = [(submissions[i+1] - submissions[i]).days for i in range(len(submissions)-1)]
            if gaps and min(gaps) <= 14:
                anomalies.append({
                    "type": "FREQUENT_CLAIM_SUBMISSION",
                    "severity": "low",
                    "evidence": f"Claims submitted as little as {min(gaps)} days apart.",
                    "reason": "High submission velocity; verify each claim has an independent event.",
                })

    stats = compute_customer_claim_stats(db, customer_id)
    notes.append(f"{len(claims)} prior claims analysed for {customer_id}.")
    return {
        "customer_id": customer_id,
        "claim_count_excluded_current": len(claims),
        "stats": stats,
        "anomalies": anomalies,
        "notes": notes,
    }


def find_similar_historical_claims(
    db: Session,
    claim: Claim,
    limit: int = 10,
    include_self: bool = False,
) -> List[Dict[str, Any]]:
    """Similar historical claims: same claim type, comparable amounts, recent window."""
    out: List[Dict[str, Any]] = []
    ref_amount = float(claim.amount or 0)
    ref_type = str(claim.claim_type or "").lower()
    ref_date = claim.submission_date or claim.incident_date
    for c in db.query(Claim).filter(Claim.id != (claim.id if not include_self else -1)).all():
        if c.id == claim.id:
            continue
        amount = float(c.amount or 0)
        if ref_amount and amount:
            if abs(amount - ref_amount) > AMOUNT_SIMILARITY_RANGE * max(amount, ref_amount):
                continue
        ctype = str(c.claim_type or "").lower()
        sim_ratio = SequenceMatcher(None, ref_type, ctype).ratio() if ref_type and ctype else 0
        if sim_ratio < 0.6:
            continue
        # Window: claims within WINDOW_DAYS of the current claim
        d = _days(ref_date, c.submission_date or c.incident_date)
        if d is not None and abs(d) > WINDOW_DAYS:
            continue
        out.append({
            "claim_id": c.claim_id,
            "amount": c.amount,
            "claim_type": c.claim_type,
            "incident_date": _iso(c.incident_date),
            "submission_date": _iso(c.submission_date),
            "similarity_score": round(sim_ratio, 2),
            "amount_delta_days": None,
            "matching_strength": "similar type and comparable amount",
        })
    out.sort(key=lambda x: -x["similarity_score"])
    return out[:limit]


def analyze_claim_vs_history(db: Session, claim_id: int) -> Dict[str, Any]:
    """Full comparison of one claim against policyholder history, similar
    claims, and policy information. Uses real records only."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return {"error": "claim_not_found", "claim_id": claim_id}

    history = analyze_customer_history(db, claim.customer_id, current_claim_id=claim.id)
    similar = find_similar_historical_claims(db, claim)
    policy = claim.policy
    prev_claims = [
        {
            "claim_id": c.claim_id,
            "incident_date": _iso(c.incident_date),
            "amount": c.amount,
            "policy_number": c.policy.policy_number if c.policy else None,
            "submission_date": _iso(c.submission_date),
            "days_since_incident": _days(claim.incident_date, c.incident_date),
        }
        for c in get_customer_claim_history(db, claim.customer_id)
        if c.id != claim.id
    ]

    comparisons: List[Dict[str, Any]] = []
    # Beneficiary timing vs incident
    changes = (
        db.query(ClaimBeneficiaryChange).filter(ClaimBeneficiaryChange.claim_id == claim.id).all()
    )
    if changes and claim.beneficiary_last_change_date and claim.incident_date:
        days = _days(claim.incident_date, claim.beneficiary_last_change_date)
        if days is not None and days < 0:
            comparisons.append({
                "comparison_id": f"CMP-{claim.id}-beneficiary-timing",
                "topic": "Beneficiary changes",
                "detail": f"{abs(days)} days before the incident date there was a beneficiary change.",
                "severity": "medium",
                "evidence": f"Last beneficiary change: {claim.beneficiary_last_change_date.date().isoformat()}; incident: {claim.incident_date.date().isoformat()}.",
            })
    # Amount vs customer average
    stats = history["stats"]
    if stats["avg_amount"] and float(claim.amount):
        ratio = float(claim.amount) / stats["avg_amount"] if stats["avg_amount"] else 0
        if ratio > 1.6:
            comparisons.append({
                "comparison_id": f"CMP-{claim.id}-amount-vs-avg",
                "topic": "Claim amount vs customer average",
                "detail": f"Claim ZWL {float(claim.amount):,.0f} is ~{ratio:.1f}x the customer average ZWL {stats['avg_amount']:,.0f}.",
                "severity": "medium",
            })
    # Amount vs similar claims
    if similar:
        top = similar[0]
        comparisons.append({
            "comparison_id": f"CMP-{claim.id}-similar-claim",
            "topic": "Similar historical claims",
            "detail": f"{len(similar)} historical claim(s) share type/amount similarity (top similarity {top['similarity_score']:.0%}).",
            "severity": "low",
            "similar_claim_ids": [s["claim_id"] for s in similar[:5]],
        })
    # Policy info: claim amount vs coverage
    if policy and float(claim.amount):
        cov = float(getattr(policy, "coverage_amount", 0) or 0)
        if cov and float(claim.amount) > cov:
            comparisons.append({
                "comparison_id": f"CMP-{claim.id}-coverage",
                "topic": "Policy coverage",
                "detail": f"Claim ZWL {float(claim.amount):,.0f} exceeds policy maximum benefit ZWL {cov:,.0f}.",
                "severity": "high",
            })
        if policy.effective_date and (claim.incident_date or claim.submission_date):
            d = _days(claim.incident_date or claim.submission_date, policy.effective_date)
            if d is not None and d < 0:
                comparisons.append({
                    "comparison_id": f"CMP-{claim.id}-inception",
                    "topic": "Policy inception",
                    "detail": f"Incident occurred {abs(d)} days BEFORE policy inception.",
                    "severity": "high",
                })

    return {
        "claim": {
            "claim_id": claim.claim_id,
            "id": claim.id,
            "customer_id": claim.customer_id,
            "customer_name": claim.customer.name if claim.customer else None,
            "claim_type": claim.claim_type,
            "amount": claim.amount,
            "incident_date": _iso(claim.incident_date),
            "submission_date": _iso(claim.submission_date),
        },
        "policy": {
            "policy_number": policy.policy_number if policy else None,
            "policy_type": policy.policy_type if policy else None,
            "effective_date": _iso(policy.effective_date) if policy else None,
            "expiry_date": _iso(policy.expiry_date) if policy else None,
            "coverage_amount": float(getattr(policy, "coverage_amount", 0) or 0) if policy else None,
        },
        "customer": {
            "customer_id": claim.customer.customer_id if claim.customer else None,
            "name": claim.customer.name if claim.customer else None,
            "national_id": claim.customer.national_id if claim.customer else None,
        },
        "previous_claims": prev_claims,
        "similar_historical_claims": similar,
        "history_anomalies": history["anomalies"],
        "comparisons": comparisons,
    }


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None
