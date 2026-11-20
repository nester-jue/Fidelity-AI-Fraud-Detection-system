import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings

logger = logging.getLogger("fraud_engine")

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
        # 7. SCORE CALIBRATION & CATEGORIZATION
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
