import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings

logger = logging.getLogger("fraud_engine")


class StatisticalIsolationScorer:
    """Statistical outlier scorer approximating Isolation Forest principles.

    Purpose (Phase 2): give the engine an unsupervised anomaly component for
    claim patterns beyond heuristic rules. Scores a feature vector by
    normalised absolute deviation from population statistics:

        score = mean( min(|z_i|, 3) / 3 )   for i in features
        z_i = (x_i - mean_i) / (std_i or range_i or 1)

    Output: 0..1 (0 = typical, 1 = extreme).

    Documented limitations:
    - Single-point deviation from population mean; not a true forest.
    - Sensitive to extreme outliers in the population baseline.
    - Limited feature space (amount, latency, frequency, amount ratio).
    - Validated on synthetic data only; not a decision-maker on its own.
    """

    FEATURE_NAMES = ["claim_amount", "submission_latency_days", "claim_frequency_30d",
                     "customer_amount_ratio", "days_since_policy_inception"]
    # claim_amount shares its baseline key with the current claim amount series
    FEATURE_KEYS = {
        "claim_amount": "amount",
        "submission_latency_days": "latency_days",
        "claim_frequency_30d": "claim_frequency_30d",
        "customer_amount_ratio": "amount",
        "days_since_policy_inception": "days_since_inception",
    }

    def __init__(self, baseline: Optional[Dict[str, Any]] = None):
        self.baseline = baseline or {}

    def set_baseline(self, stats: Dict[str, Any]) -> None:
        self.baseline = stats

    def score(self, features: Dict[str, Any], baseline: Optional[Dict[str, Any]] = None) -> float:
        stats = baseline or self.baseline
        if not stats:
            return 0.0
        scores: List[float] = []
        for name in self.FEATURE_NAMES:
            if name not in features or features.get(name) is None:
                continue
            try:
                x = float(features[name])
            except (TypeError, ValueError):
                continue
            mean = float(stats.get(f"{name}_mean", 0.0) or 0.0)
            spread = float(stats.get(f"{name}_std", 0.0) or 0.0)
            if spread <= 1e-9:
                spread = abs(mean) if mean != 0 else 1.0
            z = abs(x - mean) / spread
            scores.append(min(z, 3.0) / 3.0)
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)


def isolation_features_from_claim(claim_data: Dict[str, Any],
                                   historical_claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Builds the isolation feature vector for a claim (Phase 2)."""
    def _num(d: Dict[str, Any], key: str, default: float = 0.0) -> float:
        try:
            return float(d.get(key, default))
        except (TypeError, ValueError):
            return default

    amounts = [_num(c, "amount") for c in historical_claims if _num(c, "amount") > 0]
    avg_amt = (sum(amounts) / len(amounts)) if amounts else _num(claim_data, "amount", 0.0) or 1.0

    return {
        "claim_amount": _num(claim_data, "amount", 0.0),
        "submission_latency_days": _num(claim_data, "latency_days", 0.0),
        "claim_frequency_30d": _num(claim_data, "claim_frequency_30d", 0.0),
        "customer_amount_ratio": (_num(claim_data, "amount", 0.0) / avg_amt) if avg_amt else 0.0,
        "days_since_policy_inception": _num(claim_data, "days_since_inception", 0.0),
    }


def isolation_baseline_from_claims(claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes population statistics for the isolation scorer."""
    import statistics

    def _series(key: str) -> List[float]:
        vals = []
        for c in claims:
            try:
                v = float(c.get(key, 0) or 0)
            except (TypeError, ValueError):
                continue
            if v > 0:
                vals.append(v)
        return vals

    base: Dict[str, Any] = {}
    for name in StatisticalIsolationScorer.FEATURE_NAMES:
        key = StatisticalIsolationScorer.FEATURE_KEYS[name]
        vals = _series(key)
        if vals:
            base[f"{name}_mean"] = round(statistics.mean(vals), 4)
            base[f"{name}_std"] = round(statistics.pstdev(vals), 4) if len(vals) > 1 else max(abs(vals[0]), 1.0)
    return base

class FraudDetectionEngine:
    """Production AI & Heuristic Fraud Detection Engine for Life Assurance.
    Combines:
    1. Duplicate claims analysis
    2. Policy inception risk scoring
    3. Claim amount anomaly & velocity detection
    4. Entity and beneficiary consistency checks
    5. OCR & document tampering risk indicators
    6. Explainable multi-factor scoring calibrated to 0-100.
    """

    MODEL_VERSION = "v1.2-ensemble-hybrid"

    # Base thresholds for life assurance
    INCEPTION_CRITICAL_DAYS = 60
    INCEPTION_WARNING_DAYS = 180
    SUBMISSION_DELAY_EXTREME_DAYS = 365
    HIGH_FREQUENCY_CLAIMS_THRESHOLD = 2
    HIGH_AMOUNT_RATIO_THRESHOLD = 1.5

    def __init__(self):
        self.version = self.MODEL_VERSION

    def evaluate_claim(
        self,
        claim_data: Dict[str, Any],
        policy_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        historical_claims: List[Dict[str, Any]],
        ocr_results: Optional[List[Dict[str, Any]]] = None,
        beneficiary_name: Optional[str] = None,
        recent_beneficiary_change: bool = False,
        isolation_features: Optional[Dict[str, Any]] = None,
        isolation_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Runs the multi-layered fraud detection engine on a submitted claim.
        Returns risk score (0-100), risk category, indicators, breakdown, and recommended actions.
        """
        indicators: List[Dict[str, Any]] = []
        rule_score = 0.0
        explanations: List[str] = []
        recommended_actions: List[str] = []

        claim_amount = float(claim_data.get("amount", 0.0))
        claim_type = str(claim_data.get("claim_type", "Death")).strip().capitalize()
        incident_dt = self._parse_date(claim_data.get("incident_date"))
        submission_dt = self._parse_date(claim_data.get("submission_date")) or datetime.now(timezone.utc)
        effective_dt = self._parse_date(policy_data.get("effective_date"))
        coverage_amount = float(policy_data.get("coverage_amount", 100000.0))

        # ---------------------------------------------------------
        # 1. DUPLICATE CLAIM DETECTION (Exact & Fuzzy)
        # ---------------------------------------------------------
        dup_match, dup_reason = self._check_duplicate_claims(
            current_claim=claim_data,
            historical_claims=historical_claims,
            incident_dt=incident_dt,
            claim_amount=claim_amount,
        )
        if dup_match:
            indicators.append({
                "code": "DUPLICATE_CLAIM_DETECTED",
                "severity": "CRITICAL",
                "weight": 55.0,
                "detail": dup_reason,
            })
            rule_score += 55.0
            explanations.append(f"Duplicate claim pattern detected: {dup_reason}")
            recommended_actions.append("Immediately halt processing; cross-reference original claim reference and payment history.")

        # ---------------------------------------------------------
        # 2. POLICY INCEPTION FRAUD
        # ---------------------------------------------------------
        if incident_dt and effective_dt:
            days_since_inception = (incident_dt - effective_dt).days
            if days_since_inception < 0:
                indicators.append({
                    "code": "INCIDENT_PRIOR_TO_POLICY_START",
                    "severity": "CRITICAL",
                    "weight": 60.0,
                    "detail": f"Incident occurred {abs(days_since_inception)} days before policy inception date.",
                })
                rule_score += 60.0
                explanations.append(f"Incident date ({incident_dt.date()}) precedes policy commencement date ({effective_dt.date()}).")
                recommended_actions.append("Verify underwriting records and initial waiting period compliance.")
            elif days_since_inception <= self.INCEPTION_CRITICAL_DAYS:
                indicators.append({
                    "code": "EARLY_POLICY_INCEPTION_CLAIM",
                    "severity": "CRITICAL",
                    "weight": 65.0,
                    "detail": f"Claim incurred only {days_since_inception} days after policy inception (critical threshold: 60 days).",
                })
                rule_score += 65.0
                explanations.append(f"Short interval of {days_since_inception} days between policy start and insured event.")
                recommended_actions.append("Review original application disclosures, medical questionnaire, and anti-selection indicators.")
            elif days_since_inception <= self.INCEPTION_WARNING_DAYS:
                indicators.append({
                    "code": "RECENT_POLICY_COMMENCEMENT",
                    "severity": "MEDIUM",
                    "weight": 20.0,
                    "detail": f"Claim incurred {days_since_inception} days after policy commencement.",
                })
                rule_score += 20.0
                explanations.append("Claim occurred within the first 6 months of policy inception.")

        # ---------------------------------------------------------
        # 3. AMOUNT ANOMALY & BENEFIT LIMITS
        # ---------------------------------------------------------
        if coverage_amount > 0 and claim_amount > coverage_amount:
            indicators.append({
                "code": "CLAIM_EXCEEDS_COVERAGE_LIMIT",
                "severity": "CRITICAL",
                "weight": 50.0,
                "detail": f"Claimed amount (${claim_amount:,.2f}) exceeds policy maximum benefit (${coverage_amount:,.2f}).",
            })
            rule_score += 50.0
            explanations.append(f"Claimed amount exceeds policy benefit schedule by ${claim_amount - coverage_amount:,.2f}.")
            recommended_actions.append("Validate benefit schedule and confirm premium tier.")

        # Anomaly against historic baseline
        if historical_claims:
            amounts = [float(c.get("amount", 0)) for c in historical_claims if float(c.get("amount", 0)) > 0]
            if amounts:
                avg_amt = sum(amounts) / len(amounts)
                if claim_amount > avg_amt * 2.5 and claim_amount > 20000:
                    indicators.append({
                        "code": "UNUSUAL_CLAIM_AMOUNT_ANOMALY",
                        "severity": "HIGH",
                        "weight": 18.0,
                        "detail": f"Claimed amount (${claim_amount:,.2f}) is 2.5x higher than historical average (${avg_amt:,.2f}).",
                    })
                    rule_score += 18.0
                    explanations.append(f"Claim amount deviates substantially from historical claims profile for this customer/product.")

        # ---------------------------------------------------------
        # 4. FREQUENCY & SUBMISSION VELOCITY
        # ---------------------------------------------------------
        recent_claims_count = len(historical_claims)
        if recent_claims_count >= self.HIGH_FREQUENCY_CLAIMS_THRESHOLD:
            indicators.append({
                "code": "HIGH_CLAIM_FREQUENCY",
                "severity": "HIGH",
                "weight": 20.0,
                "detail": f"Customer or policy has {recent_claims_count} previous claims registered in system.",
            })
            rule_score += 20.0
            explanations.append(f"Multiple claim submissions ({recent_claims_count} past claims) associated with this policyholder.")
            recommended_actions.append("Conduct comprehensive cross-policy claims history audit across all life and funeral products.")

        # Submission latency check (delayed submission)
        if incident_dt and submission_dt:
            latency_days = (submission_dt - incident_dt).days
            if latency_days > self.SUBMISSION_DELAY_EXTREME_DAYS:
                indicators.append({
                    "code": "EXCESSIVE_SUBMISSION_LATENCY",
                    "severity": "MEDIUM",
                    "weight": 10.0,
                    "detail": f"Claim submitted {latency_days} days after incident date (> 1 year latency).",
                })
                rule_score += 10.0
                explanations.append(f"Unusually late submission ({latency_days} days after insured event).")

        # ---------------------------------------------------------
        # 5. BENEFICIARY & IDENTITY INCONSISTENCY
        # ---------------------------------------------------------
        if recent_beneficiary_change:
            indicators.append({
                "code": "RECENT_BENEFICIARY_ALTERATION",
                "severity": "CRITICAL",
                "weight": 30.0,
                "detail": "Beneficiary was updated or altered shortly prior to claim submission.",
            })
            rule_score += 30.0
            explanations.append("Recent change of designated beneficiary prior to the claim event.")
            recommended_actions.append("Interview policyholder representatives and inspect signed change-of-nomination forms.")

        cust_nat_id = customer_data.get("national_id")
        if not cust_nat_id or len(str(cust_nat_id).strip()) < 5:
            indicators.append({
                "code": "UNVERIFIED_NATIONAL_IDENTITY",
                "severity": "MEDIUM",
                "weight": 12.0,
                "detail": "Customer National ID is incomplete or unverified in central registry.",
            })
            rule_score += 12.0
            explanations.append("Claimant National ID format requires KYC verification.")

        # ---------------------------------------------------------
        # 6. OCR & DOCUMENT TAMPERING INDICATORS
        # ---------------------------------------------------------
        if ocr_results:
            ocr_flags_all = []
            for doc_res in ocr_results:
                flags = doc_res.get("flags", [])
                ocr_flags_all.extend(flags)
                # Date mismatch detected via OCR
                if doc_res.get("date_mismatch"):
                    indicators.append({
                        "code": "DOCUMENT_DATE_MISMATCH",
                        "severity": "CRITICAL",
                        "weight": 25.0,
                        "detail": f"Date mismatch on document '{doc_res.get('filename')}': Extracted {doc_res.get('extracted_date')} vs Claim {claim_data.get('incident_date')}.",
                    })
                    rule_score += 25.0
                    explanations.append("Discrepancy detected between date written on medical/death certificate and claim submission date.")
                    recommended_actions.append("Request original hardcopy death certificate with official registrar stamp.")

                # Suspected image alteration / duplicate file hash
                if "duplicate_document_hash" in flags:
                    indicators.append({
                        "code": "DUPLICATE_DOCUMENT_HASH",
                        "severity": "CRITICAL",
                        "weight": 35.0,
                        "detail": "Uploaded document has identical cryptographic fingerprint to a document in another claim.",
                    })
                    rule_score += 35.0
                    explanations.append("Exact duplicate supporting document uploaded in distinct claims.")
                    recommended_actions.append("Flag for forensic document analysis and notify Legal/Compliance.")

                if "empty_text" in flags or "low_ocr_confidence" in flags:
                    # Policy: a low OCR confidence reading alone must not
                    # classify a document as fraudulent. Recorded for review
                    # but contributes no fraud score.
                    indicators.append({
                        "code": "POOR_DOCUMENT_LEGIBILITY",
                        "severity": "LOW",
                        "weight": 0.0,
                        "detail": "Document text could not be extracted with sufficient confidence or is blank. Low OCR confidence alone is not evidence of fraud.",
                    })
                    explanations.append("Low readability or missing legible text on uploaded supporting document; this alone does not establish fraud.")

        # ---------------------------------------------------------
        # 7. BEHAVIOURAL & PREDICTIVE ENHANCEMENTS (Phase 2 upgrade)
        # ---------------------------------------------------------
        # Payment velocity: repeated payment account references across
        # claims in the customer's history indicate payment-pattern abuse.
        acct_refs = [str(r).strip() for r in (claim_data.get("payment_account_refs") or []) if str(r).strip()]
        if historical_claims:
            hist_accts = {
                str(r).strip()
                for hc in historical_claims
                for r in (hc.get("payment_account_refs") or [])
                if str(r).strip()
            }
            reused = [a for a in set(acct_refs) if a in hist_accts]
            if reused:
                indicators.append({
                    "code": "REPEATED_PAYMENT_ACCOUNT_REF",
                    "severity": "HIGH",
                    "weight": 18.0,
                    "detail": f"Payment account reference(s) reused from earlier claim(s): {', '.join(sorted(reused))[:80]}.",
                })
                rule_score += 18.0
                explanations.append(f"Payment account reference reused across {len(reused)} prior claim(s) — repeated-account fraud pattern.")

        # Beneficiary consistency: benign when the beneficiary matches the
        # customer; an unsolicited mismatch with verified identity is a signal.
        beneficiary_name = str(claim_data.get("beneficiary_name") or "").strip()
        cust_name = str(customer_data.get("name") or "").strip()
        if beneficiary_name and cust_name and beneficiary_name.lower() != cust_name.lower():
            cust_id_verified = bool(str(customer_data.get("national_id") or "").strip() and len(str(customer_data.get("national_id")).strip()) >= 5)
            if cust_id_verified:
                indicators.append({
                    "code": "BENEFICIARY_NAME_MISMATCH",
                    "severity": "MEDIUM",
                    "weight": 12.0,
                    "detail": f"Beneficiary name ({beneficiary_name}) differs from verified customer name ({cust_name}).",
                })
                rule_score += 12.0
                explanations.append("Beneficiary name differs from the verified customer name.")

        # Beneficiary National ID consistency (when both sides have data).
        BEN_NIN = str(claim_data.get("beneficiary_nin") or "").strip()
        CUST_NIN = str(customer_data.get("national_id") or "").strip()
        if BEN_NIN and CUST_NIN and BEN_NIN != CUST_NIN and len(CUST_NIN) >= 5:
            indicators.append({
                "code": "BENEFICIARY_IDENTITY_MISMATCH",
                "severity": "HIGH",
                "weight": 22.0,
                "detail": "Beneficiary National ID differs from the verified customer National ID — potential identity substitution.",
            })
            rule_score += 22.0
            explanations.append("Beneficiary identity number differs from the verified customer identity number.")
            recommended_actions.append("Verify beneficiary identity through the customer master file and legal custody documentation.")

        # Phone/email reuse across the customer's historical claims.
        def _norm(v: Any) -> str:
            s = str(v or "").strip().lower()
            digits = "".join(ch for ch in s if ch.isdigit())
            return digits if len(digits) >= 8 else s

        claim_phone = _norm(claim_data.get("phone_number"))
        claim_email = _norm(claim_data.get("email_address") or customer_data.get("email_address"))
        if historical_claims and (claim_phone or claim_email):
            hist_phones, hist_emails = set(), set()
            for hc in historical_claims:
                hp = _norm(hc.get("phone_number"))
                he = _norm(hc.get("email_address"))
                if hp: hist_phones.add(hp)
                if he: hist_emails.add(he)
            reused = []
            if claim_phone and claim_phone in hist_phones:
                reused.append(("phone", claim_phone))
            if claim_email and claim_email in hist_emails:
                reused.append(("email", claim_email))
            if reused:
                kinds = ", ".join(k for k, _ in reused)
                indicators.append({
                    "code": "REUSED_CONTACT_INFORMATION",
                    "severity": "HIGH",
                    "weight": 15.0,
                    "detail": f"Contact information ({kinds}) reused from earlier claim(s).",
                })
                rule_score += 15.0
                explanations.append(f"Contact information reused across earlier claims ({kinds}).")

        # Historical investigation outcome awareness (Phase 2 upgrade).
        if historical_claims:
            prior_confirmed = sum(
                1 for hc in historical_claims
                if str((hc.get("investigation_outcome") or hc.get("status") or "")).lower() in ("confirmed_fraud", "fraud_confirmed", "escalated")
            )
            if prior_confirmed >= 1:
                indicators.append({
                    "code": "PRIOR_CONFIRMED_FRAUD_ON_POLICY",
                    "severity": "HIGH",
                    "weight": 20.0,
                    "detail": f"{prior_confirmed} earlier claim(s) linked to this policy were confirmed as fraud during investigation.",
                })
                rule_score += 20.0
                explanations.append(f"Prior confirmed fraud investigations ({prior_confirmed}) on related claims raise suspicion.")
                recommended_actions.append("Escalate immediately — review the full investigation trail on earlier claims.")

        # ---------------------------------------------------------
        # 8. STATISTICAL ISOLATION COMPONENT (Phase 2 upgrade)
        # ---------------------------------------------------------
        # Unsupervised anomaly scoring (approximates Isolation Forest
        # principles; documented limitations in StatisticalIsolationScorer).
        rule_score_pre_isolation = rule_score
        isolation_score = 0.0
        if isolation_features and isolation_stats:
            isolation_score = StatisticalIsolationScorer().score(isolation_features, isolation_stats)
            if isolation_score >= 0.5:
                indicators.append({
                    "code": "ISOLATION_ANOMALY_DETECTED",
                    "severity": "HIGH",
                    "weight": 20.0,
                    "detail": f"Statistical outlier score {isolation_score:.2f} deviates from portfolio population; recorded as anomaly evidence for human review — not proof of fraud.",
                })
                rule_score += min(20.0, isolation_score * 25.0)
                explanations.append(f"Isolation anomaly score {isolation_score:.2f} higher than typical claims; flagged for human review.")

        # ---------------------------------------------------------
        # 8. SCORE CALIBRATION & CATEGORIZATION
        # ---------------------------------------------------------
        # Cap score between 0 and 100
        calibrated_score = round(min(100.0, max(0.0, rule_score)), 1)

        # Categorize using configurable thresholds
        th = settings.risk_thresholds
        low_max = float(th["low"][1])
        med_max = float(th["medium"][1])
        high_max = float(th["high"][1])
        if calibrated_score < low_max:
            category = "Low"
            base_recommendation = "Low fraud risk. Proceed with standard claims adjudication process."
        elif calibrated_score < med_max:
            category = "Medium"
            base_recommendation = "Medium fraud risk. Recommend secondary review by Claims Officer prior to payment clearance."
        elif calibrated_score < high_max:
            category = "High"
            base_recommendation = "High fraud risk. Refer claim file to Fraud Investigation Unit for verification of supporting evidence."
        else:
            category = "Critical"
            base_recommendation = "Critical fraud risk. Place immediate administrative hold on payment approval; escalate to Head of Claims and Senior Fraud Investigator."

        if not recommended_actions:
            recommended_actions.append(base_recommendation)
        else:
            recommended_actions.insert(0, base_recommendation)

        summary_explanation = " | ".join(explanations) if explanations else "Normal claims parameters; no suspicious indicators identified."

        return {
            "risk_score": calibrated_score,
            "risk_category": category,
            "indicators": indicators,
            "explanation": summary_explanation,
            "recommended_actions": recommended_actions,
            "model_version": self.version,
            "assessed_at": datetime.now(timezone.utc).isoformat(),
            # Ensemble components (Phase 2 upgrade)
            "rule_score": round(rule_score_pre_isolation, 2),
            "isolation_score": isolation_score,
            "ensemble_score": calibrated_score,
            "ensemble_method": "rule_ensemble + statistical_isolation_scorer",
        }

    def _check_duplicate_claims(
        self,
        current_claim: Dict[str, Any],
        historical_claims: List[Dict[str, Any]],
        incident_dt: Optional[datetime],
        claim_amount: float,
    ) -> Tuple[bool, str]:
        """Checks for duplicate claims against the same policy or event."""
        if not historical_claims:
            return False, ""

        current_claim_id = current_claim.get("claim_id")
        current_policy = current_claim.get("policy_number")

        for past in historical_claims:
            if past.get("claim_id") == current_claim_id:
                continue

            past_amount = float(past.get("amount", 0.0))
            past_policy = past.get("policy_number")
            past_incident = self._parse_date(past.get("incident_date"))

            # Exact match: same policy, same amount, same incident date
            if past_policy == current_policy and abs(past_amount - claim_amount) < 1.0:
                if incident_dt and past_incident and abs((incident_dt - past_incident).days) <= 1:
                    return True, f"Identical claim amount (${claim_amount:,.2f}) and incident date matches past claim {past.get('claim_id')} on policy {past_policy}."

            # Same incident date and same amount across connected customer
            if past_amount == claim_amount and claim_amount > 5000:
                if incident_dt and past_incident and (incident_dt - past_incident).days == 0:
                    return True, f"Exact duplicate amount (${claim_amount:,.2f}) and incident date ({incident_dt.date()}) matches historical claim {past.get('claim_id')}."

        # Fuzzy match (Phase 2 upgrade): same policy + near-identical amount
        # + same incident date window, or repeated beneficiary names on the
        # same policy with materially similar amounts.
        for past in historical_claims:
            if past.get("claim_id") == current_claim_id:
                continue
            past_amount = float(past.get("amount", 0.0))
            past_policy = past.get("policy_number")
            past_incident = self._parse_date(past.get("incident_date"))
            past_beneficiary = str(past.get("beneficiary_name") or "").strip().lower()
            current_beneficiary = str(current_claim.get("beneficiary_name") or "").strip().lower()

            if past_policy == current_policy and past_amount > 0 and claim_amount > 0:
                ratio = max(past_amount, claim_amount) / max(min(past_amount, claim_amount), 1.0)
                if ratio <= 1.15 and incident_dt and past_incident and abs((incident_dt - past_incident).days) <= 7:
                    return True, f"Near-duplicate: similar amount (${past_amount:,.2f} vs ${claim_amount:,.2f}) and incident date within 7 days on policy {past_policy} — past claim {past.get('claim_id')}."
            if past_beneficiary and current_beneficiary and past_beneficiary == current_beneficiary and past_amount and claim_amount:
                if abs(past_amount - claim_amount) < 5000 and past.get("policy_number") == current_policy:
                    return True, f"Repeated beneficiary with similar claim amount on policy {current_policy} — possible re-submission."

        return False, ""

    def _parse_date(self, val: Any) -> Optional[datetime]:
        if not val:
            return None
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val
        try:
            val_str = str(val).replace("Z", "+00:00")
            dt = datetime.fromisoformat(val_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            try:
                # Try common formats
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                    return datetime.strptime(str(val), fmt).replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

# Singleton instance
fraud_engine = FraudDetectionEngine()
