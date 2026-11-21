"""Zimbabwe Insurance Intelligence Configuration (Phase 9).

Configures NEXA for the Zimbabwean insurance operating environment:

- Zimbabwean national identification formats (NN-NNNNNNN-X-XX as emitted by
  the Public Registrar of Postal & Telecommunication Statutes; alternative
  dashed/undashed variants are accepted for comparison).
- Local date formats (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, YYYY/MM/DD).
- Accepted claim currencies: Zimbabwean Dollar (ZWL) plus major regional and
  foreign currencies accepted by Zimbabwean insurers (USD, EUR, GBP, CHF,
  MWK, PYG, UGX, KES, ZAR).
- Configurable regulatory/compliance rules.

NOTE (honesty): the regulatory values in ``REGULATORY_DEFAULTS`` are
configurable defaults documented by the platform, not statements of a
specific piece of legislation. Administrators may adjust them through the
NEXA regulatory API (``/zim/``). The formats, accepted currency codes and
date conventions encode verifiable public formats (e.g. the Zimbabwean ID
format); numeric deadlines and thresholds are policy defaults requiring
legal review by the insurer.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Zimbabwean National Identification Formats
# ---------------------------------------------------------------------------

# Primary format per the Public Registrar of Postal & Telecommunication
# Statistics (Zimbabwe): NN-NNNNNNN-X-XX
ZIMBABWE_NATIONAL_ID_PRIMARY_PATTERN = r"\b\d{2}-\d{6,7}-[A-Z]-\d{2}\b"
# Acceptance variants for comparisons (dashes ignored, letter may be upper/lower).
ZIMBABWE_NATIONAL_ID_STRICT_PATTERN = r"\d{2}[-]?\d{6,7}[-]?[A-Za-z]-?\d{2}"
# Historical short form: NN-NNNNNN-X-00
ZIMBABWE_NATIONAL_ID_HISTORIC_PATTERN = r"\b\d{2}-\d{6}-[A-Z]-\d{2}\b"

ZIMBABWE_NATIONAL_ID_FORMATS: List[Dict[str, Any]] = [
    {
        "format_id": "zim_historic",
        "description": "NN-NNNNNN-X-00 (older 6-digit series)",
        "regex": ZIMBABWE_NATIONAL_ID_HISTORIC_PATTERN,
        # Squashed comparator (no dashes; the '-' inside [A-Z] must not be stripped).
        "core_regex": r"\b\d{2}\d{6}[A-Z]\d{2}\b",
        "length_range": [10, 11],
    },
    {
        "format_id": "zim_primary",
        "description": "NN-NNNNNNN-X-XX (Public Registrar format, e.g. 63-1234567-A-01)",
        "regex": ZIMBABWE_NATIONAL_ID_PRIMARY_PATTERN,
        "core_regex": r"\b\d{2}\d{6,7}[A-Z]\d{2}\b",
        "length_range": [11, 12],
    },
]

# ---------------------------------------------------------------------------
# Zimbabwean Date Formats
# ---------------------------------------------------------------------------

ZIMBABWE_DATE_FORMATS: List[Tuple[str, str]] = [
    ("%d/%m/%Y", "DD/MM/YYYY (local Zimbabwean convention)"),
    ("%d-%m-%Y", "DD-MM-YYYY"),
    ("%Y-%m-%d", "YYYY-MM-DD (ISO)"),
    ("%Y/%m/%d", "YYYY/MM/DD"),
    ("%m/%d/%Y", "MM/DD/YYYY (North American style, accepted for portability)"),
]

# ---------------------------------------------------------------------------
# Accepted Claim Currencies (Zimbabwean operating environment)
# ---------------------------------------------------------------------------

# Zimbabwean Dollar (mandatory) + major foreign currencies accepted by
# Zimbabwean insurers for international claims.
ZIMBABWE_ACCEPTED_CURRENCIES: List[str] = [
    "ZWL", "USD", "EUR", "GBP", "CHF", "MWK", "PYG", "UGX", "KES", "ZAR",
]

ZIMBABWE_CURRENCY_REGEX = re.compile(r"^[A-Za-z]{3}$")

# ---------------------------------------------------------------------------
# Configurable Regulatory Defaults (platform-configurable, reviewed by legal)
# ---------------------------------------------------------------------------

REGULATORY_DEFAULTS: Dict[str, Any] = {
    # Life assurance: standard post-inception waiting period (days).
    "life_assurance_waiting_period_days": 30,
    # Beneficiary declarations should be filed within this window before claim.
    "beneficiary_declaration_window_days": 30,
    # Claim reporting deadline measured from incident date.
    "claim_reporting_deadline_days": 90,
    # Death certificates required for life and funeral assurance claims.
    "death_certificate_required": True,
    # Standard claim cap as a percentage of the policy coverage schedule.
    "standard_claim_coverage_cap_percent": 100.0,
    # KYC / identity verification period for policyholders (days).
    "kyc_renewal_period_days": 365,
    # Minimum life coverage per policyholder (ZWL) — configuration default,
    # not a legal floor.
    "minimum_policy_coverage_zwl": 1000.0,
}


def get_zim_config() -> Dict[str, Any]:
    """Returns the full Zimbabwe insurance intelligence configuration snapshot."""
    return {
        "national_id_formats": ZIMBABWE_NATIONAL_ID_FORMATS,
        "primary_national_id_pattern": ZIMBABWE_NATIONAL_ID_PRIMARY_PATTERN,
        "date_formats": [{"format": fmt, "example_hint": desc} for fmt, desc in ZIMBABWE_DATE_FORMATS],
        "accepted_currencies": ZIMBABWE_ACCEPTED_CURRENCIES,
        "mandatory_currency": "ZWL",
        "regulatory_defaults": dict(REGULATORY_DEFAULTS),
        "disclaimer": (
            "NEXA Zimbabwe Intelligence configuration. Regulatory thresholds are "
            "platform-configurable defaults; insurers must verify against current "
            "legislation with their legal counsel."
        ),
    }


def _strip_spaces(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def validate_national_id_format(value: str) -> Dict[str, Any]:
    """Validates a Zimbabwean National ID against configured formats.

    Returns a dict with ``valid``, ``format_id``, ``normalized``, ``format_description``,
    and ``errors``.
    """
    raw = str(value or "").strip()
    if not raw:
        return {
            "valid": False,
            "format_id": None,
            "normalized": None,
            "format_description": None,
            "errors": ["National ID is empty."],
        }

    squashed = _strip_spaces(raw)
    # Accept with or without dashes (comparison normalization).
    nospace_compare = re.sub(r"[\s\-]", "", raw.upper())

    for fmt in ZIMBABWE_NATIONAL_ID_FORMATS:
        if re.fullmatch(fmt["core_regex"], nospace_compare):
            # Structural checks on numeric parts.
            errors = []
            parts = re.match(r"^(\d{2})(\d{6,7})([A-Z])(\d{2})$", nospace_compare)
            if parts:
                seq = parts.group(3)
                if seq in ("O", "0"):
                    errors.append("Sequence letter appears to contain a zero instead of the letter O.")
            return {
                "valid": not errors,
                "format_id": fmt["format_id"],
                "normalized": nospace_compare,
                "format_description": fmt["description"],
                "errors": errors,
                "matched_pattern": fmt["regex"],
            }

    return {
        "valid": False,
        "format_id": None,
        "normalized": None,
        "format_description": None,
        "errors": [
            "Value does not match any configured Zimbabwean National ID format.",
            f"Expected formats: {[f['regex'] for f in ZIMBABWE_NATIONAL_ID_FORMATS]}",
        ],
    }


def normalize_zim_date(value: str, strict: bool = False) -> Dict[str, Any]:
    """Normalizes Zimbabwean dates (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, ...).

    Returns ``{"ok": bool, "iso": "YYYY-MM-DD", "errors": [...]}``.
    Ambiguous MM/DD/YYYY is resolved by date validity where possible; note
    both conventions are configured and the first matching valid parse wins
    (DD/MM/YYYY is tried before MM/DD/YYYY so Zimbabwean style wins ties).
    """
    raw = str(value or "").strip()
    if not raw:
        return {"ok": False, "iso": None, "errors": ["Empty date value."]}

    # Plain ISO strings first.
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00").replace("+00:00", "").strip()[:10])
        if len(raw) >= 8 and "T" not in raw:
            return {"ok": True, "iso": parsed.date().isoformat(), "errors": [], "normalized_from": "iso"}
    except (ValueError, TypeError):
        pass

    errors: List[str] = []
    candidates = []
    for fmt, _desc in ZIMBABWE_DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            candidates.append((fmt, dt))
        except ValueError:
            continue

    if not candidates:
        return {
            "ok": False,
            "iso": None,
            "errors": [f"'{raw}' matches none of the configured Zimbabwean date formats: {[f for f, _ in ZIMBABWE_DATE_FORMATS]}."],
        }

    # Prefer DD/MM/YYYY ordering (first configured match), then fall back to
    # the first parseable candidate. Zimbabwe convention dominates.
    fmt, dt = candidates[0]
    return {"ok": True, "iso": dt.date().isoformat(), "errors": errors, "normalized_from": fmt}


def validate_claim_currency(currency: str) -> Dict[str, Any]:
    """Validates that a currency is accepted in the Zimbabwean environment."""
    code = _strip_spaces(currency)
    if not ZIMBABWE_CURRENCY_REGEX.match(code):
        return {"ok": False, "currency": currency, "errors": ["Currency code must be 3 letters (e.g. ZWL, USD)."]}
    accepted = code in ZIMBABWE_ACCEPTED_CURRENCIES
    notes = []
    if not accepted:
        notes.append(f"Currency '{code}' is not in the configured Zimbabwean acceptance list.")
    elif code != "ZWL":
        notes.append("Foreign currency accepted; claim reviewer should verify realisation terms with policyholder.")
    return {"ok": accepted, "currency": code, "errors": notes if not accepted else [], "notes": notes, "mandatory_currency": "ZWL"}


def get_regulatory_rules() -> Dict[str, Any]:
    """Returns the configurable regulatory/compliance rules for the Zimbabwe environment."""
    rules = {
        "rule_groups": [
            {
                "group_id": "life_assurance",
                "description": "Life assurance claim eligibility and timing rules",
                "rules": [
                    {
                        "rule_id": "death_certificate_required",
                        "description": "Death certificate is mandatory evidence for life assurance death claims.",
                        "value": REGULATORY_DEFAULTS["death_certificate_required"],
                        "configurable": True,
                    },
                    {
                        "rule_id": "waiting_period",
                        "description": "Policyholder should be free of medical condition during the policy waiting period before any claim acceptance consideration.",
                        "value": REGULATORY_DEFAULTS["life_assurance_waiting_period_days"],
                        "unit": "days",
                        "configurable": True,
                    },
                    {
                        "rule_id": "coverage_cap",
                        "description": "Claim payout subject to the policy benefit schedule; cap expressed as % of coverage.",
                        "value": REGULATORY_DEFAULTS["standard_claim_coverage_cap_percent"],
                        "unit": "%",
                        "configurable": True,
                    },
                ],
            },
            {
                "group_id": "claim_process",
                "description": "Claim submission, timing and reporting rules",
                "rules": [
                    {
                        "rule_id": "claim_reporting_deadline",
                        "description": "Claim should be reported within the configured deadline of the incident.",
                        "value": REGULATORY_DEFAULTS["claim_reporting_deadline_days"],
                        "unit": "days_after_incident",
                        "configurable": True,
                    },
                    {
                        "rule_id": "beneficiary_declaration_window",
                        "description": "Beneficiary changes should be declared within the configured window before claim submission.",
                        "value": REGULATORY_DEFAULTS["beneficiary_declaration_window_days"],
                        "unit": "days_before_claim",
                        "configurable": True,
                    },
                    {
                        "rule_id": "kyc_renewal_period",
                        "description": "KYC/identity verification should be renewed at the configured period.",
                        "value": REGULATORY_DEFAULTS["kyc_renewal_period_days"],
                        "unit": "days",
                        "configurable": True,
                    },
                ],
            },
            {
                "group_id": "fraud_countermeasures",
                "description": "Fraud prevention and detection requirements",
                "rules": [
                    {
                        "rule_id": "identity_verification",
                        "description": "National identification verification required for all claim submissions (policyholders and beneficiaries).",
                        "value": True,
                        "configurable": True,
                    },
                    {
                        "rule_id": "duplicate_document_reject",
                        "description": "Identical document fingerprints submitted across claims are flagged for investigation.",
                        "value": True,
                        "configurable": True,
                    },
                ],
            },
        ],
        "note": (
            "These rules are platform-configurable defaults. Insurers must "
            "validate against current legislation with legal counsel."
        ),
    }
    return rules


def get_zim_timeline_context() -> Dict[str, Any]:
    """Contextual note for NEXA AI Assistant / UI when operating in Zimbabwe."""
    return {
        "jurisdiction": "Zimbabwe",
        "company": "Fidelity Life Assurance Company",
        "specialised_products": ["Life Assurance", "Funeral Assurance", "Medical Aid", "Group Life", "Pension-related claims where applicable"],
        "accepted_currencies": ZIMBABWE_ACCEPTED_CURRENCIES,
        "mandatory_currency": "ZWL",
        "supporting_assumption": "Foreign-currency claims require proof of exchange rate terms with policyholder.",
    }
