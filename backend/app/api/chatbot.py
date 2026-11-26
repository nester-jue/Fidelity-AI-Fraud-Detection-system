"""
NEXA AI Intelligence Assistant — Conversational Intelligence API
=================================================================

A role-aware conversational chatbot for the Fidelity Life Assurance AI Fraud
Detection Platform. It answers operational questions using real system
records — claims, fraud assessments, OCR extractions, investigations,
compliance exceptions and management performance data. All data is retrieved
through role-enforced queries; the chatbot never fabricates claims, OCR
results, evidence, investigations or statistics.

Optional external LLM integration (OpenAI-compatible): when CHATBOT_LLM_API_KEY
is set, the chatbot forwards the retrieved records context to the model with a
strict system prompt that only permits answers from that context. Without a
key the chatbot answers deterministically from real records.

Security notes:
- Every request is authenticated (JWT via get_current_active_user).
- Capability and per-record access rules mirror the underlying data APIs
  (claims.py, fraud.py, investigations.py, ocr.py, compliance_reports.py,
  management_reports.py).
- Every user message and assistant reply is persisted to the chat_messages
  table so history is retained within the authenticated session.
- Messages are capped in length; assistant replies never approve/reject
  claims or alter evidence — recommendations require human review.
"""

import json
import logging
import re
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..dependencies import get_current_active_user, log_audit_trail
from ..models.sqlalchemy_models import (
    AuditLog,
    ChatMessage,
    Claim,
    ClaimNote,
    Customer,
    EvidenceRecord,
    FraudAssessment,
    Investigation,
    KnowledgeDocument,
    ManagementReport,
    ModelPerformance,
    Notification,
    OCRDocument,
    Policy,
    RoleEnum,
    User,
)
from ..services.db import get_db
from ..services.knowledge import add_chunks, add_document, get_provider, list_documents, search
from ..services.knowledge.provider import KnowledgeSource
from ..services import (
    fraud_network, claim_timeline, historical_behavior, predictive_monitoring,
    zim_config, model_performance,
)
from ..services import evidence as evidence_service
from .compliance_reports import _compliance_summary
from .management_reports import _fraud_trends, _performance_snapshot
from .ocr import _claims_visible_to_user

router = APIRouter(prefix="/chatbot", tags=["NEXA AI Intelligence Assistant"])
logger = logging.getLogger("chatbot")

MAX_MESSAGE_LENGTH = 2000

# Capability constants
CAP_CLAIMS = "claims"
CAP_FRAUD = "fraud"
CAP_OCR = "ocr"
CAP_INVESTIGATIONS = "investigations"
CAP_COMPLIANCE = "compliance"
CAP_MANAGEMENT = "management"
CAP_ADMIN = "admin"
CAP_FORENSICS = "forensics"
CAP_AUDIT = "audit"
CAP_NOTIFICATIONS = "notifications"
CAP_NOTES = "notes"
CAP_MANAGEMENT_REPORTS = "management_reports"
CAP_USERS = "users"
CAP_CUSTOMERS = "customers"
CAP_POLICIES = "policies"
# Advanced intelligence capabilities (enterprise upgrade, Phase 2-14)
CAP_NETWORK = "network"
CAP_TIMELINE = "timeline"
CAP_EVIDENCE = "evidence"
CAP_HISTORICAL = "historical"
CAP_PREDICTIVE = "predictive"
CAP_ZIM = "zim"
CAP_MODEL_PERFORMANCE = "model_performance"
CAP_EXPOSURE = "exposure"

# Role -> permitted chatbot capabilities (enforced at the backend level).
# Claims Managers get departmental-scoped management answers only.
ROLE_CAPABILITIES: Dict[RoleEnum, List[str]] = {
    RoleEnum.CLAIMS_OFFICER: [CAP_CLAIMS, CAP_FRAUD, CAP_OCR, CAP_NOTIFICATIONS, CAP_NOTES, CAP_CUSTOMERS, CAP_POLICIES, CAP_NETWORK, CAP_TIMELINE, CAP_HISTORICAL, CAP_ZIM],
    RoleEnum.CLAIMS_MANAGER: [CAP_CLAIMS, CAP_FRAUD, CAP_OCR, CAP_INVESTIGATIONS, CAP_MANAGEMENT, CAP_FORENSICS, CAP_NOTIFICATIONS, CAP_NOTES, CAP_CUSTOMERS, CAP_POLICIES, CAP_NETWORK, CAP_TIMELINE, CAP_HISTORICAL],
    RoleEnum.FRAUD_INVESTIGATOR: [CAP_FRAUD, CAP_OCR, CAP_INVESTIGATIONS, CAP_FORENSICS, CAP_NOTIFICATIONS, CAP_NOTES, CAP_CUSTOMERS, CAP_POLICIES, CAP_NETWORK, CAP_TIMELINE, CAP_EVIDENCE, CAP_HISTORICAL, CAP_MODEL_PERFORMANCE],
    RoleEnum.COMPLIANCE_OFFICER: [CAP_COMPLIANCE, CAP_FRAUD, CAP_OCR, CAP_INVESTIGATIONS, CAP_FORENSICS, CAP_AUDIT, CAP_NOTIFICATIONS, CAP_CUSTOMERS, CAP_POLICIES, CAP_TIMELINE, CAP_EVIDENCE, CAP_HISTORICAL],
    RoleEnum.MANAGEMENT: [CAP_MANAGEMENT, CAP_FRAUD, CAP_NOTIFICATIONS, CAP_CUSTOMERS, CAP_POLICIES, CAP_MANAGEMENT_REPORTS, CAP_NETWORK, CAP_TIMELINE, CAP_HISTORICAL, CAP_EXPOSURE, CAP_PREDICTIVE, CAP_MODEL_PERFORMANCE],
    RoleEnum.SYSTEM_ADMIN: [CAP_ADMIN, CAP_MANAGEMENT, CAP_FRAUD, CAP_OCR, CAP_INVESTIGATIONS, CAP_COMPLIANCE, CAP_CLAIMS, CAP_FORENSICS, CAP_AUDIT, CAP_USERS, CAP_NOTIFICATIONS, CAP_NOTES, CAP_CUSTOMERS, CAP_POLICIES, CAP_MANAGEMENT_REPORTS, CAP_NETWORK, CAP_TIMELINE, CAP_EVIDENCE, CAP_HISTORICAL, CAP_PREDICTIVE, CAP_ZIM, CAP_MODEL_PERFORMANCE, CAP_EXPOSURE],
    RoleEnum.CHIEF_RISK_OFFICER: [CAP_FRAUD, CAP_OCR, CAP_INVESTIGATIONS, CAP_FORENSICS, CAP_MANAGEMENT, CAP_NOTIFICATIONS, CAP_CUSTOMERS, CAP_POLICIES, CAP_NETWORK, CAP_TIMELINE, CAP_HISTORICAL, CAP_EVIDENCE, CAP_PREDICTIVE, CAP_MODEL_PERFORMANCE, CAP_EXPOSURE],
}

ROLE_NAME: Dict[RoleEnum, str] = {
    RoleEnum.CLAIMS_OFFICER: "Claims Officer",
    RoleEnum.CLAIMS_MANAGER: "Claims Manager",
    RoleEnum.FRAUD_INVESTIGATOR: "Fraud Investigator",
    RoleEnum.COMPLIANCE_OFFICER: "Compliance Officer",
    RoleEnum.MANAGEMENT: "Executive Management",
    RoleEnum.CHIEF_RISK_OFFICER: "Chief Risk Officer",
    RoleEnum.SYSTEM_ADMIN: "System Administrator",
}

# Role -> knowledge-base department scope. "shared" documents apply to everyone;
# department-specific documents are only retrievable for the matching role.
ROLE_DEPARTMENT: Dict[RoleEnum, str] = {
    RoleEnum.CLAIMS_OFFICER: "claims_officer",
    RoleEnum.CLAIMS_MANAGER: "claims_manager",
    RoleEnum.FRAUD_INVESTIGATOR: "fraud_investigator",
    RoleEnum.COMPLIANCE_OFFICER: "compliance_officer",
    RoleEnum.MANAGEMENT: "executive_management",
    RoleEnum.CHIEF_RISK_OFFICER: "executive_management",
    RoleEnum.SYSTEM_ADMIN: "system_admin",
}

SUGGESTED_QUESTIONS: Dict[str, List[str]] = {
    "claims_officer": [
        "Which documents are missing from my assigned claims?",
        "What is the status of my assigned claims?",
        "Show me the fraud risk scores of my assigned claims.",
        "Which of my claims are flagged for investigation?",
        "What documentation do I need for claim CLM-1234?",
        "Show me my unread notifications.",
        "Tell me about customer APP-WANG.",
        "What is the coverage of policy POL-2024-008?",
        "Show me the fraud network relationships for my claims.",
        "Show me the timeline for claim CLM-1234.",
        "What are the anomalies in my claims' timelines?",
        "Compare claim CLM-1234 with my claim history.",
    ],
    "claims_manager": [
        "Show me the outstanding claims awaiting departmental review.",
        "Which claims in the Claims department have fraud alerts?",
        "What is the processing performance of my Claims department?",
        "Which claims are high risk or critical in my portfolio?",
        "What compliance issues do my claims have?",
        "Show my departmental claim notes.",
        "Show my management reports.",
    ],
    "fraud_investigator": [
        "Explain why this claim received a critical fraud-risk score.",
        "Show me my open investigations.",
        "Summarise the evidence recorded for an investigation.",
        "Which investigations are outstanding?",
        "List my recent fraud alerts.",
        "Show me the high-risk forensic queue with top indicators.",
        "Why was this document flagged as evidence of tampering?",
        "Show me my unread notifications.",
        "Tell me about customer APP-WANG.",
        "Which claims share suspicious characteristics?",
        "Show me the fraud network relationships for this investigation.",
        "Verify the integrity of the evidence for investigation N.",
    ],
    "compliance_officer": [
        "Which cases have outstanding compliance requirements?",
        "Show me the high-risk claims awaiting review.",
        "Summarise the latest audit observations.",
        "Which claims are missing documentation?",
        "Give me my compliance summary for this period.",
        "Show me the audit log activity.",
        "Show me unread notifications.",
    ],
    "management": [
        "Summarise the organisation's fraud detection performance.",
        "Which areas currently present the highest fraud exposure?",
        "Provide a management summary of the last 12 months.",
        "Show me the recent fraud alerts and investigation outcomes.",
        "Which claims have been flagged as High or Critical risk?",
        "Show my management reports.",
        "Show me the latest audit logs.",
        "Tell me about customer APP-WANG.",
        "Show me the model performance metrics (precision, recall, false positives).",
        "Which emerging fraud patterns should I be aware of?",
        "What is the current fraud exposure estimate?",
    ],
    "chief_risk_officer": [
        "Which claims currently present the highest fraud risk?",
        "Summarise the fraud network intelligence findings.",
        "Show the AI model performance metrics and data quality indicators.",
        "Which predictive alerts are still open?",
        "Show the recent investigation outcomes.",
    ],
    "system_admin": [
        "Are all AI and document-processing services operational?",
        "Summarise the system and user management status.",
        "Show me the latest audit logs.",
        "Which services have outstanding or pending work?",
        "What is the current volume of claims and investigations?",
        "How many users are active?",
        "Show me my notifications.",
        "Tell me about customer APP-WANG.",
    ],
}

# Intent detection: keyword groups mapped to capabilities (checked in order).
INTENT_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("claims_missing", ["missing", "pending documentation", "request documents", "documentation required"]),
    ("model_performance", ["model accuracy", "model precision", "model recall", "false positive rate",
                           "false-negative rate", "model versions", "ai model performance", "model performance",
                           "detection rate", "precision recall"]),
    ("forensics", ["forensic", "fingerprint", "tamper", "image manipulation", "document fingerprint",
                   "duplicate document", "forensic analysis", "hash match", "altered document",
                   "benchmark", "model performance", "ai model performance", "model evaluation",
                   "document analysis", "duplicates", "document integrity", "inconsistencies",
                   "suspicious documents", "inconsistent documents", "duplicate documents",
                   "document set", "documents analysis", "inconsistent claims"]),
    ("ocr", ["ocr", "extract", "extracted", "extraction", "confidence level", "raw text"]),
    # Advanced intelligence capabilities (enterprise upgrade, checked before generic fraud)
    ("network", ["fraud network", "fraud relationship", "connected entities", "relationship network", "network graph",
                 "fraud clusters", "suspicious relationships", "entity connections", "who is connected"]),
    ("timeline", ["timeline", "chronological", "event order", "sequence of events", "reconstruct",
                  "event history", "timeline of claim"]),
    ("evidence", ["evidence", "integrity hash", "sha256", "document integrity", "forensic evidence",
                  "evidence record", "evidence integrity", "re-verify evidence"]),
    ("historical", ["prior claims", "past claims", "claim history", "historical claims", "previous claims",
                    "claims history of", "similar historical claims", "claim history analysis"]),
    ("predictive", ["predictive", "predictive alert", "risk monitoring", "emergent pattern", "emerging pattern",
                    "proactive risk", "predictive monitoring", "unusual claim pattern"]),
    ("exposure", ["fraud exposure", "loss exposure", "financial exposure", "exposure overview",
                  "portfolio exposure", "exposure by", "estimated exposure"]),
    ("zim", ["zimbabwe", "zwl", "national id format", "zimbabwian", "zim config", "zim id", "zim id format",
             "republic of zimbabwe"]),
    ("fraud", ["fraud", "risk", "critical", "high risk", "flagged", "score", "detection rate"]),
    ("investigations", ["investigation", "investigations", "siu", "audit trail", "outstanding cases"]),
    ("compliance", ["compliance", "audit log", "regulatory", "exception", "audit observation"]),
    ("audit", ["audit log", "audit trail", "activity log", "audit activity", "audit history", "compliance audit"]),
    ("users", ["users", "user count", "active users", "user management", "users by role", "departments"]),
    ("notifications", ["notification", "notifications", "alert me", "my alerts"]),
    ("notes", ["departmental notes", "claim notes", "notes on claims"]),
    ("management_reports", ["management report", "management reports", "my reports", "executive report",
                            "generate report", "report summary", "performance reports"]),
    ("customers", ["customer", "customers", "policyholder", "customer status"]),
    ("policies", ["polic", "policies", "policyholder"]),
    ("management", ["performance", "summary", "trends", "exposure", "volume", "fraud alerts", "organisation", "organization", "management"]),
    ("claims", ["claim", "claims", "processing"]),
]

INTENT_TO_CAPABILITY = {
    "claims_missing": CAP_CLAIMS,
    "forensics": CAP_FORENSICS,
    "ocr": CAP_OCR,
    "investigations": CAP_INVESTIGATIONS,
    "compliance": CAP_COMPLIANCE,
    "audit": CAP_AUDIT,
    "users": CAP_USERS,
    "notifications": CAP_NOTIFICATIONS,
    "notes": CAP_NOTES,
    "management_reports": CAP_MANAGEMENT_REPORTS,
    "customers": CAP_CUSTOMERS,
    "policies": CAP_POLICIES,
    "management": CAP_MANAGEMENT,
    "fraud": CAP_FRAUD,
    "claims": CAP_CLAIMS,
    "network": CAP_NETWORK,
    "timeline": CAP_TIMELINE,
    "evidence": CAP_EVIDENCE,
    "historical": CAP_HISTORICAL,
    "predictive": CAP_PREDICTIVE,
    "exposure": CAP_EXPOSURE,
    "model_performance": CAP_MODEL_PERFORMANCE,
    "zim": CAP_ZIM,
}

ADMIN_KEYWORDS = ["operational", "ai service", "document-processing", "system status", "user management", "audit logs", "system health"]


# ---------------------------------------------------------------------------
# API Models
# ---------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH, description="User question or statement")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Recent conversation history from the frontend (direction/content/created_at)")
    conversation_id: Optional[str] = Field(None, description="Client-supplied conversation identifier (conversation scope is per-user)")


class ChatMessageResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)  # verified records used
    suggestions: List[str] = Field(default_factory=list)
    ai_mode: str = "deterministic"  # deterministic | llm | deterministic_fallback


class ChatHistoryEntry(BaseModel):
    direction: str  # 'user' | 'assistant'
    content: str
    created_at: Optional[str] = None


class KnowledgeDocumentUpload(BaseModel):
    """A System Administrator uploads an approved knowledge document (Phase 6).

    Text formats (manuals, procedures, SOPs, policies) are stored as-is and
    embedded by the RAG engine; PDF/DOCX parsing is Phase 6 work in
    ``parse_document``.
    """
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=100000)
    department: str = Field(default="shared", pattern="^[a-z][a-z_0-9]*$")
    doc_type: str = Field(default="manual", pattern="^[a-z_0-9]+$")
    status: str = Field(default="draft", pattern="^[a-z_0-9]+$")


# ---------------------------------------------------------------------------
# Small formatting helpers (all values come from live DB queries)
# ---------------------------------------------------------------------------

def _fmt_amount(amount: Optional[float]) -> str:
    if isinstance(amount, (int, float)):
        return f"${amount:,.0f}"
    return "unknown amount"


def _fmt_date(dt: Any) -> str:
    if dt is None:
        return "unknown"
    try:
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(dt)


def _indicator_codes(indicators: Optional[Any]) -> List[str]:
    codes = set()
    for item in indicators or []:
        if isinstance(item, dict):
            for key in ("code", "name", "code_"):
                if item.get(key):
                    codes.add(str(item[key]))
                    break
            else:
                detail = item.get("detail") or ""
                if detail:
                    codes.add(str(detail)[:70])
        elif isinstance(item, str) and item:
            codes.add(item)
    return sorted(codes, key=str.lower)


# ---------------------------------------------------------------------------
# Shared data access helpers (mirror the underlying data APIs)
# ---------------------------------------------------------------------------

def _officer_claims_query(db: Session, user: User):
    """Claims the Claims department workspace shows the user.

    - Claims Officers: their assignments or unassigned.
    - Claims Managers: departmental scope — claims assigned to Claims officers
      or unassigned (they are in the Claims department: DEPARTMENT_BY_ROLE in
      app/dependencies.py maps managers to ['Claims']).
    - Other roles: unfiltered (management/admin have global views).
    """
    q = db.query(Claim)
    if user.role == RoleEnum.CLAIMS_OFFICER:
        q = q.filter(
            (Claim.assigned_officer_id == user.id) | (Claim.assigned_officer_id.is_(None))
        )
    elif user.role == RoleEnum.CLAIMS_MANAGER:
        claims_officer_ids = [
            r[0] for r in db.query(User.id).filter(User.role == RoleEnum.CLAIMS_OFFICER).all()
        ]
        q = q.filter(
            Claim.assigned_officer_id.in_(claims_officer_ids) | Claim.assigned_officer_id.is_(None)
        )
    return q


def _claim_ref_from_message(message: str) -> Optional[str]:
    m = re.search(r"\b(CLM-[A-Za-z0-9-]+)\b", message)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b(\d{2,})\b", message)
    if m and re.search(r"\b(claims?|case|investigation|ref(erence)?)\b", message, re.IGNORECASE):
        return m.group(1)
    return None


def _claim_visible_ids(db: Session, user: User) -> List[int]:
    """Claim IDs the user may see in the Claims department workspace (manager scope aware)."""
    return [c.id for c in _officer_claims_query(db, user).all()]


def _get_claim_visible(db: Session, user: User, ref: Optional[str]) -> Optional[Claim]:
    if not ref:
        return None
    claim = db.query(Claim).filter((Claim.claim_id == ref) | (Claim.id == ref)).first()
    if not claim:
        return None
    if user.role in (RoleEnum.CLAIMS_OFFICER, RoleEnum.CLAIMS_MANAGER):
        if claim.id not in _claim_visible_ids(db, user):
            return None
    return claim


def _fraud_visible_claim_ids(db: Session, user: User) -> Optional[List[int]]:
    """Returns claim IDs whose fraud assessments the user may access (None = global)."""
    if user.role in (RoleEnum.CLAIMS_OFFICER, RoleEnum.CLAIMS_MANAGER):
        return _claim_visible_ids(db, user)
    if user.role == RoleEnum.FRAUD_INVESTIGATOR:
        return [i.claim_id for i in db.query(Investigation).filter(Investigation.investigator_id == user.id).all()]
    if user.role == RoleEnum.COMPLIANCE_OFFICER:
        return _claims_visible_to_user(db, user)
    return None  # management / system_admin: global view


def _ocr_base_for_user(db: Session, user: User):
    visible = _claims_visible_to_user(db, user)
    if visible:
        return db.query(OCRDocument).filter(OCRDocument.claim_id.in_(visible))
    if user.role in (RoleEnum.MANAGEMENT, RoleEnum.SYSTEM_ADMIN):
        return db.query(OCRDocument)
    # Officer/compliance/investigator with nothing visible sees nothing.
    return db.query(OCRDocument).filter(OCRDocument.id == -1)


def _investigations_visible(db: Session, user: User):
    if user.role == RoleEnum.FRAUD_INVESTIGATOR:
        return db.query(Investigation).filter(Investigation.investigator_id == user.id).order_by(desc(Investigation.opened_at))
    if user.role == RoleEnum.CLAIMS_MANAGER:
        claim_ids = [c.id for c in _officer_claims_query(db, user).all()]
        if not claim_ids:
            return db.query(Investigation).filter(Investigation.id == -1)
        return db.query(Investigation).filter(Investigation.claim_id.in_(claim_ids)).order_by(desc(Investigation.opened_at))
    if user.role == RoleEnum.COMPLIANCE_OFFICER:
        visible = _claims_visible_to_user(db, user)
        if not visible:
            return db.query(Investigation).filter(Investigation.id == -1)
        return db.query(Investigation).filter(Investigation.claim_id.in_(visible)).order_by(desc(Investigation.opened_at))
    if user.role == RoleEnum.SYSTEM_ADMIN:
        return db.query(Investigation).order_by(desc(Investigation.opened_at))
    # Claims officer and others: nothing permitted.
    return db.query(Investigation).filter(Investigation.id == -1)


# ---------------------------------------------------------------------------
# Capability handlers — every answer is built from real records
# ---------------------------------------------------------------------------

def _answer_claim_detail(db: Session, claim: Claim) -> str:
    assess = claim.assessment
    investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
    lines = [
        f"Claim {claim.claim_id}:",
        f"Status: {claim.status or 'submitted'}",
        f"Amount: {_fmt_amount(claim.amount)} ({claim.claim_type or 'unknown type'} claim)",
        f"Incident date: {_fmt_date(claim.incident_date)}",
        f"Submitted: {_fmt_date(claim.submission_date)}",
        f"Policy: {claim.policy.policy_number if claim.policy else 'n/a'}",
    ]
    if claim.description:
        lines.append(f"Narrative: {claim.description[:200]}")
    lines.append(f"Documents on record: {len(claim.documents)}")
    for doc in claim.documents[:6]:
        lines.append(f"  • {doc.filename}")
    if assess:
        lines.append(f"AI risk score: {float(assess.risk_score):.1f}/100 — {assess.risk_category or 'Pending'}")
        if assess.explanation:
            lines.append(f"AI explanation: {assess.explanation}")
        codes = _indicator_codes(assess.indicators)
        if codes:
            lines.append(f"AI indicators: {', '.join(codes)}")
    else:
        lines.append("AI risk assessment: not yet available")
    if investigation:
        inv_text = f"Investigation: {investigation.status}"
        if investigation.closed_at:
            inv_text += f" (closed {_fmt_date(investigation.closed_at)})"
        else:
            inv_text += f" (opened {_fmt_date(investigation.opened_at)})"
        lines.append(inv_text)
    return "\n".join(lines)


def _claims_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]]]:
    q = _officer_claims_query(db, user)
    lower = message.lower()
    samples: List[Dict[str, Any]] = []
    ref = _claim_ref_from_message(message)

    # 1. Specific claim detail
    if ref:
        claim = _get_claim_visible(db, user, ref)
        if claim:
            text = _answer_claim_detail(db, claim)
            samples.append({"type": "claim", "claim_id": claim.claim_id, "status": claim.status})
        else:
            text = f"I could not find an accessible claim with reference '{ref}'."
            samples.append({"type": "claim", "claim_id": ref, "status": None})
        return text, samples

    # 2. Missing documentation
    if "missing" in lower or any(k in lower for k in ("pending documentation", "request documents", "documentation required")):
        pending = q.filter(Claim.status == "pending_documents").order_by(desc(Claim.submission_date)).limit(8).all()
        no_docs = [
            c for c in q.filter(Claim.status.in_(["submitted", "flagged", "in_review"]))
            .order_by(desc(Claim.submission_date)).all()
            if not c.documents
        ][:5]
        lines = [
            f"Found {len(pending)} claim(s) with pending documentation and {len(no_docs)} claim(s) without supporting documents in your view."
        ]
        if pending:
            lines.append("Pending documentation: " + ", ".join(c.claim_id for c in pending) + ".")
        if no_docs:
            lines.append("Without documents: " + ", ".join(c.claim_id for c in no_docs) + ".")
        lines.append("Missing documents can be uploaded from the Document Upload workspace, or you can request documents for a specific claim via the Claims Officer tools.")
        samples.extend([{"type": "claim", "claim_id": c.claim_id, "status": c.status} for c in pending[:8]])
        samples.extend([{"type": "claim", "claim_id": c.claim_id, "status": c.status} for c in no_docs[:5]])
        return "\n".join(lines), samples

    # 3. Status breakdown
    rows = q.with_entities(Claim.status, func.count()).group_by(Claim.status).all()
    total = sum(r[1] for r in rows)
    statuses = {(s or "submitted"): n for s, n in rows}
    breakdown = ", ".join(f"{s}: {n}" for s, n in sorted(statuses.items(), key=lambda x: -x[1]))
    lines = [f"Your view shows {total} claim(s): {breakdown}." if breakdown else "There are currently no claims in your view."]
    if "pending_documents" in statuses or "flagged" in statuses:
        lines.append("Note: 'pending_documents' claims need additional documentation; 'flagged' claims are awaiting review.")
    lines.append("Use the Claims workspace to check claim details or upload missing documentation.")
    samples.append({"type": "summary", "claims_visible": total, "statuses": statuses})
    return "\n".join(lines), samples


def _fraud_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]]]:
    lower = message.lower()
    samples: List[Dict[str, Any]] = []
    ref = _claim_ref_from_message(message)

    if ref:
        claim = _get_claim_visible(db, user, ref)
        if not claim:
            return f"I could not find an accessible claim with reference '{ref}'.", samples
        assess = claim.assessment
        samples.append({
            "type": "fraud_assessment", "claim_id": claim.claim_id,
            "risk_score": assess.risk_score if assess else None,
            "risk_category": assess.risk_category if assess else None,
        })
        if not assess:
            return f"No AI fraud assessment has been recorded for claim {claim.claim_id} yet.", samples
        lines = [
            f"Claim {claim.claim_id} — {_fmt_amount(claim.amount)} ({claim.claim_type or 'unknown type'})",
            f"Risk score: {float(assess.risk_score):.1f}/100 — {assess.risk_category or 'Pending'}",
        ]
        codes = _indicator_codes(assess.indicators)
        if codes:
            lines.append(f"Risk indicators: {', '.join(codes)}")
        if assess.explanation:
            lines.append(f"AI explanation: {assess.explanation}")
        lines.append(f"Assessed by {assess.model_version or 'the NEXA AI fraud detection engine'} on {_fmt_date(assess.assessed_at)}.")
        lines.append("This is the persisted AI assessment record — it has not been altered or approved by any human reviewer.")
        return "\n".join(lines), samples

    # Summary of accessible assessments
    ids = _fraud_visible_claim_ids(db, user)
    q = db.query(FraudAssessment)
    if ids:
        q = q.filter(FraudAssessment.claim_id.in_(ids))
    rows = q.order_by(desc(FraudAssessment.assessed_at)).limit(12).all()
    breakdown: Dict[str, int] = {}
    for a in rows:
        cat = a.risk_category or "Pending"
        breakdown[cat] = breakdown.get(cat, 0) + 1
    lines = [
        f"{len(rows)} fraud assessment(s) accessible to you: "
        + (", ".join(f"{k}: {v}" for k, v in sorted(breakdown.items())) if breakdown else "none recorded")
        + "."
    ]
    high_or_critical = [a for a in rows if (a.risk_category or "") in ("High", "Critical")]
    if high_or_critical:
        lines.append(f"{len(high_or_critical)} claim(s) are High or Critical risk. Top entries:")
        for a in high_or_critical[:6]:
            claim = a.claim
            cid = claim.claim_id if claim else "n/a"
            lines.append(f"  • {cid} — {float(a.risk_score):.1f}/100 ({a.risk_category})")
    if rows:
        lines.append("Fraud explanations and risk indicators come from persisted AI assessment records.")
        samples.extend([
            {
                "type": "fraud_assessment",
                "claim_id": (a.claim.claim_id if a.claim else None),
                "risk_score": a.risk_score,
                "risk_category": a.risk_category,
            }
            for a in rows[:12]
        ])
    return "\n".join(lines), samples


def _ocr_answer_doc(doc: OCRDocument) -> str:
    conf = doc.confidence_score
    lines = [
        f"{doc.filename} ({doc.document_type or 'unknown type'})",
        f"Status: {doc.processing_status or 'pending'} · Engine: {doc.ocr_engine or 'n/a'} · "
        f"Confidence: {round(float(conf), 1) if conf is not None else 'n/a'}%"
        + (" · Manually verified" if doc.is_manually_verified else ""),
    ]
    if doc.document_hash_sha256:
        lines.append(f"Document fingerprint (SHA-256): {doc.document_hash_sha256[:16]}…")
    fields = doc.extracted_fields if isinstance(doc.extracted_fields, dict) else {}
    if fields:
        lines.append(f"Extracted fields ({len(fields)}): {', '.join(sorted(str(k) for k in fields.keys()))}")
    for name in ("extracted_dates", "extracted_amounts", "extracted_national_ids"):
        val = getattr(doc, name)
        if val:
            lines.append(f"{name.replace('_', ' ').title()}: {len(val)} value(s)")
    if doc.missing_fields:
        lines.append(f"Missing fields: {', '.join(doc.missing_fields)}")
    if doc.flags:
        lines.append(f"Flags: {', '.join(doc.flags)}")
    lines.append(f"Date mismatch detected: {'Yes' if doc.has_date_mismatch else 'No'}")
    if doc.verified_by:
        lines.append(f"Verified by: {doc.verified_by.full_name or doc.verified_by.username} on {_fmt_date(doc.verified_at)}")
    return "\n".join(lines)


def _ocr_stats_for_user(db: Session, user: User) -> Dict[str, int]:
    base = _ocr_base_for_user(db, user)
    stats = {
        "completed": base.filter(OCRDocument.processing_status == "completed").count(),
        "pending": base.filter(OCRDocument.processing_status == "pending").count(),
        "failed": base.filter(OCRDocument.processing_status == "failed").count(),
    }
    stats["total"] = stats["completed"] + stats["pending"] + stats["failed"]
    avg_conf = db.query(func.avg(OCRDocument.confidence_score)).filter(
        OCRDocument.processing_status == "completed",
        OCRDocument.confidence_score > 0,
    ).scalar()
    stats["average_confidence"] = round(float(avg_conf or 0), 1)
    return stats


def _ocr_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]]]:
    lower = message.lower()
    samples: List[Dict[str, Any]] = []
    ref = _claim_ref_from_message(message)
    base = _ocr_base_for_user(db, user)

    # 1. Specific document details
    if ref:
        try:
            ref_id = int(ref)
        except (TypeError, ValueError):
            ref_id = None
        docs = base.filter(
            (OCRDocument.claim_id == ref_id) | OCRDocument.filename.ilike(f"%{ref}%")
        ).limit(3).all()
        if not docs:
            return f"I could not find an accessible OCR document for reference '{ref}'.", samples
        text = "\n\n".join(_ocr_answer_doc(d) for d in docs[:2])
        samples.extend([
            {"type": "ocr_document", "filename": d.filename, "confidence": d.confidence_score, "missing_fields": d.missing_fields}
            for d in docs[:2]
        ])
        return text, samples

    # 2. Overview stats
    if any(k in lower for k in ("overview", "statistics", "stats", "how many", "count of", "summary")):
        stats = _ocr_stats_for_user(db, user)
        samples.append({"type": "ocr_stats", **stats})
        return (
            f"OCR overview: {stats['total']} document(s) — completed: {stats['completed']}, "
            f"pending: {stats['pending']}, failed: {stats['failed']}; "
            f"average confidence of completed extractions: {stats['average_confidence']}%.",
            samples,
        )

    # 3. List recent extractions
    docs = base.order_by(desc(OCRDocument.uploaded_at)).limit(6).all()
    if not docs:
        return "There are no OCR documents visible for you at the moment.", samples
    lines = [f"Showing up to {len(docs)} recent OCR documents with their extraction results:"]
    for d in docs[:3]:
        lines.append("  • " + _ocr_answer_doc(d))
        samples.append({"type": "ocr_document", "filename": d.filename, "confidence": d.confidence_score, "missing_fields": d.missing_fields})
    return "\n".join(lines), samples


# ---------------------------------------------------------------------------
# Forensics — evidence, fingerprints, findings (connects to /forensics/*)
# ---------------------------------------------------------------------------

def _forensics_overview_text(db: Session, samples: List[Dict[str, Any]]) -> str:
    total_claims = db.query(Claim).count()
    total_analysed = db.query(FraudAssessment).count()
    low = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Low").count()
    medium = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Medium").count()
    high = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "High").count()
    critical = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Critical").count()
    confirmed = db.query(Investigation).filter(Investigation.status == "confirmed_fraud").count()
    completion = round((total_analysed / max(total_claims, 1)) * 100, 1)
    avg = db.query(func.avg(FraudAssessment.risk_score)).scalar()
    lines = [
        f"Forensic overview: {total_analysed}/{total_claims} claims analysed "
        f"({completion}% completion rate), average risk score {round(float(avg or 0), 1)/1:.0f}/100.",
        f"Risk breakdown: Low {low}, Medium {medium}, High {high}, Critical {critical}.",
        f"Confirmed suspicious cases: {confirmed}.",
        "Use 'Show me the high-risk forensic queue' or ask about a specific claim (e.g. 'Explain claim CLM-1234 forensically').",
    ]
    samples.append({"type": "forensic_overview", "claims_analysed": total_analysed, "completion_rate": completion})
    return "\n".join(lines)


def _forensics_high_risk_queue(db: Session, limit: int = 8) -> Tuple[str, List[Dict[str, Any]]]:
    assessments = (
        db.query(FraudAssessment)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.risk_score))
        .limit(limit)
        .all()
    )
    samples: List[Dict[str, Any]] = []
    lines = [f"High/Critical risk forensic queue — {len(assessments)} case(s):"]
    for a in assessments:
        claim = a.claim
        cid = claim.claim_id if claim else "n/a"
        top_code = None
        if a.indicators:
            top_code = str((a.indicators[0] or {}).get("detail") or (a.indicators[0] or {}).get("code") or "")[:80] or None
        inv = db.query(Investigation).filter(Investigation.claim_id == (claim.id if claim else -1)).first()
        lines.append(
            f"  • {cid} — {float(a.risk_score):.1f}/100 ({a.risk_category})"
            + (f" — {top_code}" if top_code else "")
            + (f" — Investigation: {inv.status}" if inv else "")
        )
        samples.append({
            "type": "forensic_queue",
            "claim_id": cid,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "top_indicator": top_code,
            "investigation_status": inv.status if inv else None,
        })
    if not assessments:
        lines = ["No High/Critical risk forensic queue entries at the moment."]
    return "\n".join(lines), samples


def _forensics_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]]]:
    lower = message.lower()
    samples: List[Dict[str, Any]] = []
    ref = _claim_ref_from_message(message)

    if ref:
        claim = _get_claim_visible(db, user, ref)
        if not claim:
            return f"I could not find an accessible claim with reference '{ref}'.", samples
        assessment = claim.assessment
        lines = [f"Forensic analysis for Claim {claim.claim_id}:"]
        if assessment:
            codes = _indicator_codes(assessment.indicators)
            lines.append(
                f"Risk score: {float(assessment.risk_score):.1f}/100 — {assessment.risk_category or 'Pending'}"
            )
            if codes:
                lines.append("Forensic findings (from AI indicators): " + ", ".join(codes))
            if assessment.explanation:
                lines.append(f"Forensic explanation: {assessment.explanation}")
            samples.append({
                "type": "forensic_assessment",
                "claim_id": claim.claim_id,
                "risk_score": assessment.risk_score,
                "risk_category": assessment.risk_category,
                "model_version": assessment.model_version,
            })
        else:
            lines.append("No forensic assessment has been recorded yet for this claim.")
        # OCR evidence: document fingerprints, flags, mismatches.
        ocr_docs = db.query(OCRDocument).filter(OCRDocument.claim_id == claim.id).order_by(desc(OCRDocument.uploaded_at)).limit(5).all()
        if ocr_docs:
            lines.append("OCR evidence:")
            for d in ocr_docs:
                parts = [d.filename or "unknown"]
                if d.document_hash_sha256:
                    parts.append(f"SHA-256 fingerprint: {d.document_hash_sha256[:16]}…")
                if d.has_date_mismatch:
                    parts.append("date-mismatch detected")
                if d.flags:
                    parts.append(f"flags: {', '.join(str(f) for f in d.flags)}")
                if d.missing_fields:
                    parts.append(f"missing fields: {', '.join(str(f) for f in d.missing_fields)}")
                lines.append("  • " + " | ".join(parts))
                samples.append({
                    "type": "forensic_evidence",
                    "filename": d.filename,
                    "sha256_fingerprint": d.document_hash_sha256,
                    "has_date_mismatch": bool(d.has_date_mismatch),
                    "flags": [str(f) for f in d.flags or []],
                })
        investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
        if investigation:
            inv_text = f"Investigation: {investigation.status}"
            if investigation.closed_at:
                inv_text += f" (closed {_fmt_date(investigation.closed_at)}, outcome: {investigation.outcome or 'n/a'})"
            else:
                inv_text += f" (opened {_fmt_date(investigation.opened_at)})"
            lines.append(inv_text)
            samples.append({"type": "investigation", "investigation_id": investigation.id, "status": investigation.status})
        return "\n".join(lines), samples

    if any(k in lower for k in ("queue", "high risk", "critical", "priority", "top queue")):
        return _forensics_high_risk_queue(db)

    if not ref and any(k in lower for k in ("document analysis", "documents analysis", "duplicates",
                                            "cross-document", "cross document", "document consistency",
                                            "inconsistencies", "document issues", "suspicious documents",
                                            "document set", "document integrity", "inconsistent documents")):
        return _forensics_doc_analysis_text(db, samples)

    if "department" not in lower and any(
        k in lower for k in ("performance", "accuracy", "ai model", "benchmark", "model version",
                             "coverage rate", "model evaluation", "precision", "recall", "f1")
    ):
        return _forensics_performance_text(db, samples)

    return _forensics_overview_text(db, samples)


def _forensics_doc_analysis_text(db: Session, samples: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    from ..services.document_forensics import generate_forensic_analysis

    analysis = generate_forensic_analysis(db)
    dup_groups = analysis["duplicate_groups"]
    cons = analysis["claim_consistency_issues"]
    susp = analysis["suspicious_flags"]

    lines = []
    lines.append(f"Document forensic analysis — duplicate groups: {len(dup_groups)}, "
                 f"claim consistency issues: {len(cons)}, suspicious flags: {len(susp)}.")
    for g in dup_groups[:5]:
        names = ", ".join(d["filename"] for d in g["documents"][:3])
        lines.append(f"  • Duplicate document hash {g['hash'][:16]}… — {names}")
    for i in cons[:6]:
        claim = db.get(Claim, i["claim_id"]) if i["claim_id"] else None
        cid = claim.claim_id if claim else i["claim_id"]
        lines.append(f"  • Claim {cid or '-'} — {i['type']}: {i['details']}")
    for f in susp[:5]:
        det = f" — {', '.join(f['details'])}" if f.get("details") else ""
        lines.append(f"  • {f['filename']} — {f['type']}{det}")
    if not (dup_groups or cons or susp):
        lines.append("No duplicate documents, claim consistency issues or suspicious flags found.")
    samples.append({
        "type": "forensic_document_analysis",
        "duplicate_groups": len(dup_groups),
        "claim_consistency_issues": len(cons),
        "suspicious_flags": len(susp),
    })
    return "\n".join(lines), samples


def _forensics_performance_text(db: Session, samples: List[Dict[str, Any]]) -> str:
    from ..ml.fraud_engine import FraudDetectionEngine

    assessed = db.query(FraudAssessment).count()
    claims = db.query(Claim).count()
    completion = round((assessed / max(claims, 1)) * 100, 1)
    breakdown = db.query(FraudAssessment.risk_category, func.count()).group_by(FraudAssessment.risk_category).all()
    top_explanations = [
        (a.risk_category, a.risk_score, (a.explanation or "")[:120])
        for a in db.query(FraudAssessment)
        .filter(FraudAssessment.risk_category == "Critical")
        .order_by(desc(FraudAssessment.assessed_at))
        .limit(3)
        .all()
    ]
    perf_rows = db.query(ModelPerformance).order_by(desc(ModelPerformance.evaluated_at)).limit(3).all()

    lines = [
        f"Forensic/AI performance: {assessed} fraud assessments, {completion}% of {claims} claims analysed.",
        "Risk breakdown: " + (", ".join(f"{c}: {n}" for c, n in sorted(breakdown, key=lambda x: -x[1])) or "none"),
        f"Engine version: {FraudDetectionEngine.MODEL_VERSION}",
    ]
    for name, score, note in top_explanations:
        lines.append(f"Top critical finding: {name} ({score}/100) — {note or 'n/a'}")
    for p in perf_rows:
        lines.append(
            f"Model performance — {p.model_name} v{p.version}: precision {p.precision}, "
            f"recall {p.recall}, f1 {p.f1_score} (evaluated {_fmt_date(p.evaluated_at)})"
        )
    if not perf_rows:
        lines.append("No standalone model performance benchmarks recorded yet.")
    samples.append({"type": "forensic_performance", "assessed": assessed, "completion_rate": completion})
    return "\n".join(lines), samples


# ---------------------------------------------------------------------------
# Phase 4 — assistance using existing system data (audit, notifications,
# claim notes, management reports, users, customers, policies)
# ---------------------------------------------------------------------------

def _audit_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(12).all()
    samples: List[Dict[str, Any]] = []
    if not logs:
        return "No audit or compliance activity records are available right now.", samples
    lines = [f"{len(logs)} most recent audit/compliance activity records:"]
    for l in logs:
        who = l.user.username if l.user else "System"
        lines.append(f"  • {l.action} — {who} — {l.target or ''} — {_fmt_date(l.timestamp)}")
        samples.append({"type": "audit_log", "action": l.action, "target": l.target,
                        "timestamp": l.timestamp.isoformat() if l.timestamp else None})
    return "\n".join(lines), samples


def _notifications_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    notifs = db.query(Notification).filter(Notification.recipient_id == user.id) \
        .order_by(desc(Notification.created_at)).limit(8).all()
    samples: List[Dict[str, Any]] = []
    if not notifs:
        return "You have no notifications.", samples
    unread = db.query(Notification).filter(
        Notification.recipient_id == user.id, Notification.read == False
    ).count()
    lines = [f"You have {len(notifs)} notification(s), {unread} unread:"]
    for n in notifs:
        lines.append(f"  • {(n.message or '')[:220]} — {_fmt_date(n.created_at)} [{'unread' if not n.read else 'read'}]")
        samples.append({"type": "notification", "id": n.id, "unread": not n.read,
                        "created_at": n.created_at.isoformat() if n.created_at else None})
    return "\n".join(lines), samples


def _notes_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    samples: List[Dict[str, Any]] = []
    ref = _claim_ref_from_message(message)
    claim = _get_claim_visible(db, user, ref) if ref else None
    if claim:
        notes = db.query(ClaimNote).filter(ClaimNote.claim_id == claim.id) \
            .order_by(desc(ClaimNote.created_at)).limit(10).all()
        if not notes:
            return f"There are no departmental notes recorded on claim {claim.claim_id} yet.", samples
        lines = [f"Departmental notes for claim {claim.claim_id}:"]
        for n in notes:
            author = n.user.full_name or n.user.username if n.user else "Unknown"
            lines.append(f"  • {(n.note or '')[:200]} — {author} — {_fmt_date(n.created_at)}")
            samples.append({"type": "claim_note", "claim_id": claim.claim_id, "note_id": n.id})
        return "\n".join(lines), samples
    # No specific claim: notes on claims visible in my view.
    ids = _claim_visible_ids(db, user)
    notes = (
        db.query(ClaimNote).filter(ClaimNote.claim_id.in_(ids)).order_by(desc(ClaimNote.created_at)).limit(10).all()
        if ids else []
    )
    if not notes:
        return "You have no claims with departmental notes in your view.", samples
    lines = [f"{len(notes)} note(s) on claims in your view:"]
    for n in notes:
        author = n.user.full_name or n.user.username if n.user else "Unknown"
        claim_ref = db.get(Claim, n.claim_id).claim_id if db.get(Claim, n.claim_id) else "n/a"
        lines.append(f"  • Claim {claim_ref} — {(n.note or '')[:200]} — {author}")
        samples.append({"type": "claim_note", "claim_id": claim_ref, "note_id": n.id})
    return "\n".join(lines), samples


def _management_reports_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    reports = db.query(ManagementReport).order_by(desc(ManagementReport.generated_at)).limit(10).all()
    samples: List[Dict[str, Any]] = []
    if not reports:
        return "No management reports have been generated yet.", samples
    lines = [f"Generated management reports ({len(reports)} most recent):"]
    for r in reports:
        summary = r.summary or {}
        author = r.generated_by.full_name or r.generated_by.username if r.generated_by else "n/a"
        line = f"  • {r.title} — {author} — {_fmt_date(r.generated_at)}"
        if summary.get("claims_received") is not None:
            line += f" — {summary['claims_received']} claims received"
        if summary.get("fraud_alerts_high_critical") is not None:
            line += f", {summary['fraud_alerts_high_critical']} High/Critical alerts"
        lines.append(line)
        samples.append({"type": "management_report", "report_id": r.id, "title": r.title})
    return "\n".join(lines), samples


def _users_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    counts = db.query(User.role, func.count()).group_by(User.role).all()
    active = db.query(User).filter(User.is_active == True).count()
    depts = sorted(d[0] for d in db.query(User.department).filter(User.department.isnot(None)).distinct().all())
    samples: List[Dict[str, Any]] = []
    lines = [
        "System user counts: " + (", ".join(f"{r.value}: {c}" for r, c in counts) or "none") + ".",
        f"Active users: {active}.",
        "Departments: " + (", ".join(depts) if depts else "none recorded") + ".",
    ]
    users = db.query(User).order_by(User.username).limit(25).all()
    lines.append(f"Users ({len(users)} shown):")
    for u in users:
        lines.append(f"  • {u.full_name or u.username} — {u.role.value} — {u.department or 'n/a'} — {u.username}")
        samples.append({"type": "user", "username": u.username, "role": u.role.value, "department": u.department})
    return "\n".join(lines), samples


_COMMON_WORD = {"customer", "customers", "policy", "policies", "policyholder", "the", "a", "my", "me",
                "is", "are", "status", "details", "info", "tell", "show", "about", "who", "what", "their", "him", "her"}


def _significant_tokens(message: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z0-9]+", message) if t.lower() not in _COMMON_WORD and len(t) >= 2]


def _customers_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]]]:
    samples: List[Dict[str, Any]] = []
    ref = _claim_ref_from_message(message)
    claim = _get_claim_visible(db, user, ref) if ref else None
    cust = claim.customer if claim else None
    if not cust:
        for token in _significant_tokens(message):
            cust = (
                db.query(Customer)
                .filter(
                    (Customer.customer_id.ilike(f"%{token}%"))
                    | (Customer.name.ilike(f"%{token}%"))
                    | (Customer.national_id.ilike(f"%{token}%"))
                )
                .order_by(Customer.id)
                .first()
            )
            if cust:
                break
    if cust is None and ref:
        return f"I could not find an accessible customer with reference '{ref}'.", samples
    if cust is None and _significant_tokens(message):
        return "I could not find an accessible customer matching your description.", samples
    if cust:
        lines = [f"Customer: {cust.name} — Customer ID: {cust.customer_id}"]
        if cust.national_id:
            lines.append(f"National ID: {cust.national_id}")
        if cust.date_of_birth:
            lines.append(f"Date of birth: {_fmt_date(cust.date_of_birth)}")
        claims = db.query(Claim).filter(Claim.customer_id == cust.id) \
            .order_by(desc(Claim.submission_date)).limit(5).all()
        lines.append(f"Claims on record: {len(claims)}")
        for c in claims[:3]:
            lines.append(f"  • {c.claim_id} — {c.claim_type or 'claim'} — {c.status} — submitted {_fmt_date(c.submission_date)}")
        samples.append({"type": "customer", "customer_id": cust.customer_id, "name": cust.name,
                        "claims_visible": len(claims)})
        return "\n".join(lines), samples

    # No specific customer: top customers by claim count.
    customers = db.query(Customer).limit(8).all()
    if not customers:
        return "There are no customers in the system at the moment.", samples
    lines = ["Customers in the system:"]
    for c in customers:
        n = db.query(Claim).filter(Claim.customer_id == c.id).count()
        lines.append(f"  • {c.name} — {c.customer_id} — {n} claim(s)")
        samples.append({"type": "customer", "customer_id": c.customer_id, "name": c.name})
    return "\n".join(lines), samples


def _policies_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]]]:
    samples: List[Dict[str, Any]] = []
    policy = None
    ref = _claim_ref_from_message(message)
    claim = _get_claim_visible(db, user, ref) if ref else None
    if claim:
        policy = claim.policy
    if not policy:
        for token in _significant_tokens(message):
            policy = db.query(Policy).filter(Policy.policy_number.ilike(f"%{token}%")).order_by(Policy.id).first()
            if policy:
                break
    if policy:
        lines = [
            f"Policy {policy.policy_number} — Type: {policy.policy_type or 'n/a'}",
            f"Effective: {_fmt_date(policy.effective_date)} — Expiry: {_fmt_date(policy.expiry_date)}",
            f"Claims on this policy: {len(policy.claims)}",
        ]
        samples.append({"type": "policy", "policy_number": policy.policy_number,
                        "policy_type": policy.policy_type, "claims_visible": len(policy.claims)})
        return "\n".join(lines), samples

    policies = db.query(Policy).order_by(desc(Policy.id)).limit(8).all()
    if not policies:
        return "There are no policies in the system at the moment.", samples
    lines = ["Policies in the system:"]
    for p in policies:
        customer = p.customer.name if p.customer else "n/a"
        lines.append(f"  • {p.policy_number} — {p.policy_type or 'n/a'} — {customer} — {_fmt_date(p.effective_date)} → {_fmt_date(p.expiry_date)}")
        samples.append({"type": "policy", "policy_number": p.policy_number, "policy_type": p.policy_type})
    return "\n".join(lines), samples


def _investigations_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    invs = _investigations_visible(db, user).limit(12).all()
    samples: List[Dict[str, Any]] = []
    if not invs:
        return "You currently have no accessible investigation cases.", samples
    lines = [f"{len(invs)} investigation case(s):"]
    for inv in invs:
        claim_id = inv.claim.claim_id if inv.claim else "n/a"
        detail = f"  • Investigation #{inv.id} — Claim {claim_id} — Status: {inv.status}"
        if inv.outcome:
            detail += f" — Outcome: {inv.outcome}"
        detail += f" — Opened: {_fmt_date(inv.opened_at)}"
        if inv.closed_at:
            detail += f" — Closed: {_fmt_date(inv.closed_at)}"
        lines.append(detail)
        if inv.notes:
            lines.append(f"    Notes: {inv.notes[:200]}")
        samples.append({"type": "investigation", "investigation_id": inv.id, "claim_id": claim_id, "status": inv.status})
    outstanding = [i for i in invs if (i.status or "").lower() in ("open", "in_review", "escalated")]
    if outstanding:
        lines.append(f"Outstanding cases: {len(outstanding)} open/in_review/escalated.")
    return "\n".join(lines), samples


def _compliance_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    summary = _compliance_summary(db)
    exceptions = (
        db.query(Claim).join(FraudAssessment)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.risk_score))
        .limit(6)
        .all()
    )
    audit_rows = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(6).all()
    samples: List[Dict[str, Any]] = [
        {"type": "compliance_summary", **{k: summary[k] for k in ("flagged_claims", "high_risk_claims", "critical_risk_claims", "claims_missing_documentation")}}
    ]
    lines = [
        f"Compliance summary: {summary['flagged_claims']} flagged claims, {summary['high_risk_claims']} high-risk claims, "
        f"{summary['critical_risk_claims']} critical-risk claims, {summary['claims_missing_documentation']} claims missing documentation."
    ]
    if exceptions:
        lines.append("High/critical-risk claims awaiting review or investigation:")
        for c in exceptions:
            inv = db.query(Investigation).filter(Investigation.claim_id == c.id).first()
            risk = float(c.assessment.risk_score) if c.assessment else None
            lines.append(
                f"  • {c.claim_id} — {c.customer.name if c.customer else 'n/a'} — "
                f"{('%.1f' % risk) + '/100 (' + (c.assessment.risk_category or 'Pending') + ')' if risk is not None else 'n/a'} — "
                f"claim status: {c.status} — investigation: {inv.status if inv else 'none'}"
            )
            samples.append({
                "type": "compliance_exception",
                "claim_id": c.claim_id,
                "risk_score": risk,
                "risk_category": c.assessment.risk_category if c.assessment else None,
                "investigation_status": inv.status if inv else "none",
            })
    if audit_rows:
        lines.append("Recent audit activity: " + ", ".join(f"{r.action} ({_fmt_date(r.timestamp)})" for r in audit_rows[:5]))
    return "\n".join(lines), samples


def _department_performance(db: Session, user: User) -> Dict[str, Any]:
    """Departmental performance counts for Claims Managers (department scope only)."""
    q = _officer_claims_query(db, user)
    visible_ids = _claim_visible_ids(db, user)
    high_risk_q = db.query(FraudAssessment).filter(
        FraudAssessment.risk_category.in_(["High", "Critical"])
    )
    if visible_ids:
        high_risk_q = high_risk_q.filter(FraudAssessment.claim_id.in_(visible_ids))
    else:
        high_risk_q = high_risk_q.filter(FraudAssessment.id == -1)
    return {
        "department_claims_total": q.count(),
        "pending": q.filter(Claim.status.in_(["submitted", "in_review", "pending_documents"])).count(),
        "flagged": q.filter(Claim.status == "flagged").count(),
        "processed": q.filter(Claim.status.in_(["approved", "rejected", "cleared"])).count(),
        "high_risk_claims": high_risk_q.count(),
    }


def _management_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    if user.role == RoleEnum.CLAIMS_MANAGER:
        dep = _department_performance(db, user)
        lines = [
            f"Claims department performance: {dep['department_claims_total']} claims in the Claims department; "
            f"{dep['pending']} pending; {dep['flagged']} flagged; {dep['processed']} processed; "
            f"{dep['high_risk_claims']} High/Critical-risk claims in the department."
        ]
        samples = [{"type": "department_performance", **dep}]
        return "\n".join(lines), samples

    snapshot = _performance_snapshot(db)
    trends = _fraud_trends(db, months=12)
    alerts = db.query(FraudAssessment).filter(FraudAssessment.risk_category.in_(["High", "Critical"])).count()
    lines = [
        f"Claims received: {snapshot['claims_received']}; processed: {snapshot['claims_processed']}; "
        f"pending: {snapshot['claims_pending']}; flagged: {snapshot['claims_flagged']}.",
        f"Confirmed fraud cases: {snapshot['confirmed_fraud_cases']}; "
        f"AI coverage rate: {snapshot['ai_coverage_rate']}%; fraud detection rate: {snapshot['fraud_detection_rate']}%.",
        f"Total financial exposure: {_fmt_amount(snapshot['total_financial_exposure'])}.",
        f"Current fraud alerts (High/Critical): {alerts}.",
    ]
    recent = [t for t in trends if t["claims_received"] > 0][-6:]
    if recent:
        parts = ", ".join(f"{t['period']}: {t['claims_received']} claims" for t in recent)
        lines.append(f"Recent claim volumes — {parts}.")
    samples = [{
        "type": "management_snapshot",
        "claims_received": snapshot["claims_received"],
        "claims_flagged": snapshot["claims_flagged"],
        "fraud_alerts_high_critical": alerts,
    }]
    return "\n".join(lines), samples


def _admin_handler(db: Session, user: User, message: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    counts = {
        "users": db.query(User).count(),
        "claims": db.query(Claim).count(),
        "fraud_assessments": db.query(FraudAssessment).count(),
        "investigations": db.query(Investigation).count(),
        "investigations_open": db.query(Investigation).filter(Investigation.status == "open").count(),
        "ocr_documents": db.query(OCRDocument).count(),
        "audit_logs_recent": db.query(AuditLog).count(),
    }
    lines = [f"{k}: {v}" for k, v in counts.items()]
    recent = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(5).all()
    if recent:
        lines.append("Recent audit activity: " + ", ".join(f"{r.action} ({_fmt_date(r.timestamp)})" for r in recent))
    samples = [{"type": "system_overview", **{k: counts[k] for k in ("users", "claims", "fraud_assessments", "investigations_open", "ocr_documents")}}]
    return "\n".join(lines), samples


# ---------------------------------------------------------------------------
# Advanced intelligence handlers (enterprise upgrade, Phase 2-14)
# ---------------------------------------------------------------------------

def _network_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Fraud relationship network summary for human review (not confirmed fraud)."""
    try:
        insights = fraud_network.get_network_insights(db)
    except Exception as exc:
        logger.warning("NETWORK_HANDLER_FAILED: %s", exc)
        return "I could not fetch fraud network data right now. Please try again or contact IT support.", [], "deterministic"
    lines = ["Fraud Network Intelligence — suspicious relationships for review:"]
    top_nodes = insights.get("top_suspicious_nodes", [])
    if top_nodes:
        lines.append("Top suspicious connections:")
        for n in top_nodes[:5]:
            parts = [f"  - {n.get('entity_type')}: {n.get('name')}",
                     f"risk {n.get('risk_score')}/100",
                     f"claim {n.get('claim_id')}" if n.get("claim_id") else "",
                     f"investigation {n.get('investigation_status')}" if n.get("investigation_status") else ""]
            lines.append(" (" + ", ".join([p for p in parts if p]) + ")")
    top_edges = insights.get("top_suspicious_edges", [])
    if top_edges:
        lines.append("Top suspicious relationships:")
        for e in top_edges[:5]:
            lines.append(f"  - {e.get('relationship_type')}: {(e.get('evidence') or '')[:160]}")
    if not top_nodes and not top_edges:
        lines.append("  No suspicious connections detected in the current network view.")
    lines.append("Note: flagged connections are indicators for review — they are not confirmed fraud.")
    samples = [{"type": "network", "summary": insights.get("summary"),
                "top_nodes": top_nodes[:3], "top_edges": top_edges[:3]}]
    return "\n".join(lines), samples, "deterministic"


def _timeline_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Chronological claim timeline reconstruction with anomalies and missing steps."""
    ref = _claim_ref_from_message(message)
    claim = _get_claim_visible(db, user, ref) if ref else None
    if claim:
        data = claim_timeline.build_claim_timeline(db, claim.id)
        lines = [f"Claim timeline for {claim.claim_id} (real records):"]
        for e in data["events"][:15]:
            lines.append(f"  • {e['display_label']} ({e['timestamp']}) — {e['description']}")
        if data["anomalies"]:
            lines.append("Anomalies / inconsistencies:")
            for a in data["anomalies"][:5]:
                lines.append(f"  ⚠ {a['type']}: {a['description']}")
        if data["summary"]["missing_steps"]:
            lines.append("Missing steps: " + ", ".join(data["summary"]["missing_steps"]))
        lines.append("Use investigation actions to explain anomalies; timeline is read-only.")
        samples = [{"type": "timeline", "summary": data["summary"], "anomalies": data["anomalies"][:3]}]
        return "\n".join(lines), samples, "deterministic"

    # No claim reference: summarize the latest claims' timelines.
    recent = db.query(Claim).order_by(desc(Claim.submission_date)).limit(5).all()
    lines = [f"Latest claim timeline summary ({len(recent)} most recent claims):"]
    for c in recent:
        tl = claim_timeline.build_claim_timeline(db, c.id)
        lines.append(
            f"  - {c.claim_id}: {tl['summary']['total_events']} events, "
            f"anomalies: {len(tl['anomalies'])}, missing: {', '.join(tl['summary']['missing_steps']) or 'none'}"
        )
    samples = [{"type": "timeline_summary",
                "claims": [{"claim_id": c.claim_id, "status": c.status} for c in recent]}]
    return "\n".join(lines), samples, "deterministic"


def _evidence_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Digital evidence listing with integrity status for visible claims/investigations."""
    visible_claim_ids = _claim_visible_ids(db, user)
    if visible_claim_ids:
        q = db.query(EvidenceRecord).filter(EvidenceRecord.claim_id.in_(visible_claim_ids))
    elif user.role in (RoleEnum.FRAUD_INVESTIGATOR, RoleEnum.SYSTEM_ADMIN, RoleEnum.MANAGEMENT):
        q = db.query(EvidenceRecord)
    else:
        q = db.query(EvidenceRecord).filter(EvidenceRecord.id == -1)
    records = q.order_by(desc(EvidenceRecord.collected_at)).limit(12).all()
    lines = ["Digital evidence records:"]
    if not records:
        lines.append("  No evidence records available for your scope.")
    for e in records:
        inv_txt = f" (inv {e.investigation_id})" if e.investigation_id else ""
        claim_txt = f" (claim {e.claim_id})" if e.claim_id else ""
        integ = "integrity OK" if e.integrity_verified else ("no fingerprint" if not e.sha256_hash else "integrity unverified")
        lines.append(f"  - '{e.title}' [{e.evidence_type}]{inv_txt}{claim_txt}: status {e.status}, {integ}")
    return "\n".join(lines), [{"type": "evidence", "count": len(records),
                               "items": [{"id": e.id, "status": e.status} for e in records]}], "deterministic"


def _historical_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Historical claim behaviour analysis (real records, never fabricated)."""
    ref = _claim_ref_from_message(message)
    claim = _get_claim_visible(db, user, ref)
    if not claim:
        return ("I need the claim reference (e.g. 'claim CLM-xxxxxx') to compare it against history. "
                "If you don't know the reference, ask: 'What is the status of my assigned claims?'"), [], "deterministic"
    data = historical_behavior.analyze_claim_vs_history(db, claim.id)
    stats = historical_behavior.compute_customer_claim_stats(db, data["claim"]["customer_id"])
    lines = [
        f"Historical behaviour analysis for {claim.claim_id}:",
        f"  Type: {data['claim']['claim_type']}; amount: {_fmt_amount(data['claim']['amount'])}",
        f"  Policyholder history: {stats['claim_count']} prior claims; average amount {_fmt_amount(stats['avg_amount'])}; total {_fmt_amount(stats['total_amount'])}",
    ]
    if data["similar_historical_claims"]:
        lines.append("Similar historical claims:")
        for s in data["similar_historical_claims"][:5]:
            lines.append(f"  - {s['claim_id']} ({s['claim_type']}, {_fmt_amount(s['amount'])}, similarity {s['similarity_score']:.0%})")
    if data["history_anomalies"]:
        lines.append("Identified anomalies:")
        for a in data["history_anomalies"][:6]:
            lines.append(f"  - {a['type']}: {a['evidence']} (severity: {a['severity']})")
    if data["comparisons"]:
        lines.append("Comparisons (current claim vs history/policy):")
        for c in data["comparisons"][:6]:
            lines.append(f"  - {c['topic']}: {c['detail']}")
    if not data["history_anomalies"] and not data["comparisons"]:
        lines.append("  No notable historical anomalies or comparisons were identified.")
    samples = [{"type": "historical", "claim_id": claim.id,
                "anomalies": data["history_anomalies"][:3],
                "similar_claims": [s["claim_id"] for s in data["similar_historical_claims"][:5]]}]
    return "\n".join(lines), samples, "deterministic"


def _predictive_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Predictive risk alerts — indicators for review, not confirmed fraud."""
    alerts = predictive_monitoring.get_alerts(db, limit=10)
    lines = ["Predictive risk alerts (not confirmed fraud):"]
    if not alerts:
        lines.append("  No new predictive alerts currently.")
    else:
        for a in alerts[:8]:
            lines.append(f"  - [{a['severity']}] {a['alert_type']}: {a['description']} (risk {a['risk_score']}, status {a['status']})")
    lines.append("Alerts are review indicators; they do not establish fraud.")
    samples = [{"type": "predictive", "count": len(alerts),
                "items": [{"id": a["id"], "type": a["alert_type"], "severity": a["severity"],
                           "risk_score": a["risk_score"]} for a in alerts[:5]]}]
    return "\n".join(lines), samples, "deterministic"


def _zim_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Zimbabwe insurance intelligence: formats, currencies, regulatory rules."""
    cfg = zim_config.get_zim_config()
    lines = [
        "Zimbabwe Insurance Intelligence (NEXA):",
        f"  Accepted currencies: {', '.join(cfg['accepted_currencies'])} (mandatory: {cfg['mandatory_currency']})",
        f"  National ID formats: {len(cfg['national_id_formats'])} configured (primary: {cfg['primary_national_id_pattern']})",
        f"  Specialised products: {', '.join(zim_config.get_zim_timeline_context()['specialised_products'])}",
    ]
    for group in zim_config.get_regulatory_rules()["rule_groups"]:
        lines.append(f"  {group['group_id']} ({group['description']}):")
        for rule in group["rules"]:
            lines.append(f"    - {rule['rule_id']}: {rule['description']} (default: {rule['value']})")
    lines.append("  Regulatory defaults are configurable; insurers must verify against current legislation with legal counsel.")
    return "\n".join(lines), [{"type": "zim", "config": cfg}], "deterministic"


def _model_performance_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """AI model performance metrics from validated records."""
    data = model_performance.compute_model_performance_metrics(db)
    metrics = data["metrics"]
    lines = [
        "AI Model Performance Dashboard:",
        f"  Claims assessed: {data['claims_assessed']}",
        f"  Claims flagged for review: {data['claims_flagged']}",
        f"  Confirmed fraud cases: {data['confirmed_fraud_cases']}",
        f"  Unconfirmed suspicious cases: {data['unconfirmed_suspicious_cases']}",
        f"  Accuracy proxy: {metrics['accuracy_proxy_flagged_confirmed_or_clear']}",
        f"  Precision: {metrics['precision']}; Recall: {metrics['recall']}; F1: {metrics['f1_score']}",
        f"  False positive rate: {metrics['false_positive_rate']}; False negative rate: {metrics['false_negative_rate']}",
        f"  Model versions: {', '.join(v['version'] for v in data['model_versions'])}",
        f"  {data['honesty_note']}",
    ]
    return "\n".join(lines), [{"type": "model_performance", "metrics": data["metrics"],
                               "versions": data["model_versions"]}], "deterministic"


def _exposure_handler(db: Session, user: User, message: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Estimated fraud risk exposure summary (indicator, not confirmed fraud)."""
    assessments = db.query(FraudAssessment).all()
    high = [a for a in assessments if a.risk_category == "High"]
    critical = [a for a in assessments if a.risk_category == "Critical"]
    exposure = round(sum(float(a.risk_score or 0) for a in high + critical), 2)
    lines = [
        "Fraud exposure overview (risk-score weighted; not confirmed fraud):",
        f"  High risk claims: {len(high)}",
        f"  Critical risk claims: {len(critical)}",
        f"  Estimated exposure score: {exposure}",
        f"  Latest assessed: {max((a.assessed_at.isoformat() for a in assessments if a.assessed_at), default='none')}",
    ]
    return "\n".join(lines), [{"type": "exposure", "high": len(high),
                               "critical": len(critical), "exposure_score": exposure}], "deterministic"


_HANDLERS = {
    CAP_CLAIMS: _claims_handler,
    CAP_FRAUD: _fraud_handler,
    CAP_OCR: _ocr_handler,
    CAP_INVESTIGATIONS: _investigations_handler,
    CAP_COMPLIANCE: _compliance_handler,
    CAP_MANAGEMENT: _management_handler,
    CAP_ADMIN: _admin_handler,
    CAP_FORENSICS: _forensics_handler,
    CAP_AUDIT: _audit_handler,
    CAP_NOTIFICATIONS: _notifications_handler,
    CAP_NOTES: _notes_handler,
    CAP_MANAGEMENT_REPORTS: _management_reports_handler,
    CAP_USERS: _users_handler,
    CAP_CUSTOMERS: _customers_handler,
    CAP_POLICIES: _policies_handler,
    CAP_NETWORK: _network_handler,
    CAP_TIMELINE: _timeline_handler,
    CAP_EVIDENCE: _evidence_handler,
    CAP_HISTORICAL: _historical_handler,
    CAP_PREDICTIVE: _predictive_handler,
    CAP_ZIM: _zim_handler,
    CAP_MODEL_PERFORMANCE: _model_performance_handler,
    CAP_EXPOSURE: _exposure_handler,
}


def _classify_message(user: User, message: str) -> Optional[str]:
    lower = message.lower()
    if user.role == RoleEnum.SYSTEM_ADMIN and any(k in lower for k in ADMIN_KEYWORDS):
        return CAP_ADMIN
    for intent, keywords in INTENT_KEYWORDS:
        if any(k in lower for k in keywords):
            return INTENT_TO_CAPABILITY[intent]
    return None


def _suggested_questions(role: RoleEnum) -> List[str]:
    return SUGGESTED_QUESTIONS.get(role.value, SUGGESTED_QUESTIONS["claims_officer"])


def _general_response(user: User) -> str:
    """Minimal greeting — the assistant doesn't reveal capabilities or data
    unless the user asks a question. Suggested questions are shown separately
    in the UI; here we keep the first question out of the response text."""
    name = user.full_name or user.username
    return (
        f"Hello {name}! I'm the NEXA AI Intelligence Assistant. Ask me anything about your work — "
        f"claims, fraud risks, OCR documents, investigations, compliance, management or system operations."
    )


# ---------------------------------------------------------------------------
# Conversational intent recognition (greetings, gratitude, farewells,
# acknowledgements, follow-ups) and conversation context
# ---------------------------------------------------------------------------

def _match_words(lower: str, keywords: List[str]) -> bool:
    """Match keywords as words (word boundaries); multi-word phrases allowed."""
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower):
            return True
    return False


CONV_FAREWELL = ["goodbye", "see you later", "see you soon", "have a good day",
                 "talk later", "catch you later", "i will come back later", "bye"]
CONV_INTRO = ["introduce yourself", "tell me about yourself", "who are you",
              "what can you do", "describe yourself", "what do you do",
              "who is nesa", "what is nesa", "tell me what you do", "who built you", "who made you"]
CONV_GRATITUDE = ["thank", "appreciated", "that helps", "grateful", "thanks"]
CONV_GREETING = ["hello", "hi", "hey", "good morning", "good afternoon",
                 "good evening", "greetings"]
CONV_ACK = ["ok", "okay", "understood", "got it", "alright", "sure",
            "noted", "fine", "yes", "yeah"]
CONV_FOLLOWUP = ["explain further", "explain that", "explain it", "elaborate",
                 "what about the documents", "what about the document", "what about that",
                 "why is that", "why was that", "can you give me an example",
                 "give me an example", "tell me more", "more about",
                 "which document contains", "which documents contain", "the inconsistency",
                 "the discrepancies", "expand on that", "say more", "additional detail",
                 "where is the inconsistency", "which dates", "which date",
                 "which documents are affected", "which document is affected"]


def _classify_conversational(message: str) -> Optional[str]:
    """Classify a message into a conversational intent (natural-language chat).

    Returns one of: "farewell", "intro", "gratitude", "greeting",
    "acknowledgement", "followup" or None (a work question).
    """
    lower = message.lower().strip()
    if not lower:
        return None
    if _match_words(lower, CONV_FAREWELL):
        return "farewell"
    if _match_words(lower, CONV_INTRO):
        return "intro"
    if _match_words(lower, CONV_GRATITUDE):
        return "gratitude"
    if _match_words(lower, CONV_GREETING):
        return "greeting"
    if _match_words(lower, CONV_ACK):
        return "acknowledgement"
    if _match_words(lower, CONV_FOLLOWUP):
        return "followup"
    return None


def _extract_context(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract conversation context (previous exchange + entities mentioned)."""
    ctx: Dict[str, Any] = {
        "previous_question": None,
        "previous_answer": None,
        "mentioned_claim": None,
        "mentioned_investigation": None,
        "mentioned_document": None,
    }
    users = [m for m in messages if m.get("direction") == "user" and m.get("content")]
    assistants = [m for m in messages if m.get("direction") == "assistant" and m.get("content")]
    if users:
        ctx["previous_question"] = users[-1]["content"]
    if assistants:
        ctx["previous_answer"] = assistants[-1]["content"]
    text = " ".join(m["content"] for m in users[-6:] + assistants[-6:])
    m = re.search(r"\b(CLM-[A-Za-z0-9-]+)\b", text)
    if m:
        ctx["mentioned_claim"] = m.group(1).upper()
    m = re.search(r"\b(INV-\d+)\b", text)
    if m:
        ctx["mentioned_investigation"] = m.group(1)
    m = re.search(r"\b([\w\-]+\.(?:pdf|png|jpg|jpeg|gif|txt|doc))\b", text)
    if m:
        ctx["mentioned_document"] = m.group(1)
    if not ctx["mentioned_document"]:
        low = text.lower()
        for kw in ("medical report", "death certificate", "death cert", "benefit letter",
                   "funeral invoice", "claim document", "ocr document"):
            if kw in low:
                ctx["mentioned_document"] = kw
                break
    return ctx


def _load_context(db: Session, user: User, history: Optional[List[Dict[str, Any]]] = None,
                  exclude_id: Optional[int] = None) -> Dict[str, Any]:
    """Loads recent conversation context: persisted history from the DB
    (authoritative) with a frontend-provided history as fallback when the DB
    has none. `exclude_id` drops the current user message from the context."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.id != exclude_id)
        .order_by(ChatMessage.id)
        .all()
    )
    messages = [
        {"direction": r.direction, "content": r.content or "", "created_at": r.created_at}
        for r in rows[-20:]
    ]
    if not messages and history:
        messages = [
            {"direction": h.get("direction", "user"), "content": h.get("content") or "",
             "created_at": h.get("created_at")}
            for h in history[-20:] if h.get("content")
        ]
    return _extract_context(messages)


def _greeting_response(user: User, ctx: Dict[str, Any]) -> str:
    name = user.full_name or user.username
    if ctx.get("previous_question"):
        return f"Hello again, {name}! I'm the NEXA AI Intelligence Assistant — what can I help you with today?"
    return (
        f"Hello, {name}! I'm the NEXA AI Intelligence Assistant, your workplace AI assistant "
        f"for {ROLE_NAME.get(user.role, 'claims work')}. Ask me anything about your work — "
        f"claims, fraud investigation, OCR documents, compliance and system operations."
    )


def _gratitude_response(user: User) -> str:
    name = user.full_name or user.username
    return f"You're welcome, {name}! Let me know if you need anything else."


def _farewell_response(user: User) -> str:
    name = user.full_name or user.username
    return f"Goodbye! Have a great day, {name}."


def _ack_response() -> str:
    return "Understood."


def _intro_response(user: User) -> str:
    name = user.full_name or user.username
    return (
        f"Hello, {name}! I'm the NEXA AI Intelligence Assistant, your workplace AI assistant "
        f"for {ROLE_NAME.get(user.role, 'claims work')}. I help with claims, fraud investigation, "
        f"OCR documents, compliance and system operations. Ask me anything about your work."
    )


def _followup_response(user: User, message: str, ctx: Dict[str, Any],
                       db: Session) -> Tuple[str, List[Dict[str, Any]], str]:
    """Follow-up questions ('Explain further', 'What about the documents?') —
    answers using conversation context and real system data."""
    samples: List[Dict[str, Any]] = []
    # 1. Approved company knowledge relevant to the follow-up.
    kb_sources = _kb_retrieve(user, message)
    if kb_sources:
        return _format_kb_sources(kb_sources), _kb_samples(kb_sources), "deterministic"
    # 2. If a claim is referenced (in this message or in context), answer with
    #    the forensic handler — includes document evidence for the claim.
    ref = _claim_ref_from_message(message) or ctx.get("mentioned_claim")
    if ref:
        text, forensic_samples = _forensics_handler(
            db, user, f"Explain documents and evidence for claim {ref}")
        if text:
            return text, forensic_samples, "deterministic"
    # 3. Expand on the previous question using its capability handler.
    prev = ctx.get("previous_question")
    if prev:
        cap = _classify_message(user, prev)
        if cap and cap in ROLE_CAPABILITIES.get(user.role, []):
            text, prev_samples = _HANDLERS[cap](db, user, prev)
            if text:
                return f"Here is further detail — {text}", prev_samples, "deterministic"
    # 4. Natural contextual response.
    target = ctx.get("mentioned_document") or ctx.get("mentioned_investigation") or ""
    if target:
        return (f"I can explain that further. What would you like to know about {target}?",
                [], "deterministic")
    return ("I can explain that further, including any related documents or records, if "
            "available. What specific detail would you like to know?", [], "deterministic")


def _denied_response(user: User) -> str:
    """Denial without disclosing the user's permitted capabilities — those are
    capabilities of the assistant, not information the user asked for."""
    role_label = ROLE_NAME.get(user.role, user.role.value)
    return (
        f"I can't provide that information with your current role ('{role_label}'). "
        f"Ask about claims, fraud, documents or investigations instead — what would you like to know?"
    )


# ---------------------------------------------------------------------------
# Knowledge base (RAG) — approved company knowledge used to answer natural questions
# ---------------------------------------------------------------------------

def _kb_retrieve(user: User, message: str) -> List[KnowledgeSource]:
    """Returns knowledge-base sources relevant to the user's question.

    Empty when the knowledge base is disabled (CHATBOT_KB_ENABLED=false) or on
    retrieval failure — retrieval is a best-effort enhancement over live data.
    """
    if not settings.CHATBOT_KB_ENABLED:
        return []
    try:
        return get_provider().retrieve(
            message,
            department=ROLE_DEPARTMENT.get(user.role, "shared"),
            top_k=settings.CHATBOT_KB_TOP_K,
        )
    except Exception as exc:
        logger.warning("CHATBOT_KB_RETRIEVAL_FAILED: %s", exc)
        return []


def _format_kb_sources(sources: List[KnowledgeSource]) -> str:
    lines = ["According to company knowledge:"]
    for s in sources[:5]:
        excerpt = (s.excerpt or "").replace("\n", " ").strip()
        lines.append(f"- [{s.title}] {excerpt[:500]}")
    return "\n".join(lines)


def _kb_samples(sources: List[KnowledgeSource]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "knowledge",
            "document_id": s.document_id,
            "title": s.title,
            "department": s.department,
            "source": s.source,
            "excerpt": (s.excerpt or "")[:300],
            "score": round(s.score, 4),
        }
        for s in sources[:3]
    ]


def _answer(db: Session, user: User, message: str,
            history: Optional[List[Dict[str, Any]]] = None,
            exclude_id: Optional[int] = None) -> Tuple[str, List[Dict[str, Any]], str]:
    """Deterministic response built from real records + approved company knowledge,
    or a denial for unauthorised capabilities.

    Conversational intents (greetings, gratitude, farewells, acknowledgements,
    follow-ups, introductions) are handled first with natural, context-aware
    responses; genuine questions fall through to the capability flow."""
    ctx = _load_context(db, user, history=history, exclude_id=exclude_id)

    # 1. Conversational intents — greetings, gratitude, farewells,
    #    acknowledgements and follow-ups respond naturally.
    conv = _classify_conversational(message)
    if conv == "greeting":
        return _greeting_response(user, ctx), [], "deterministic"
    if conv == "gratitude":
        return _gratitude_response(user), [], "deterministic"
    if conv == "farewell":
        return _farewell_response(user), [], "deterministic"
    if conv == "acknowledgement":
        return _ack_response(), [], "deterministic"
    if conv == "intro":
        return _intro_response(user), [], "deterministic"
    if conv == "followup":
        return _followup_response(user, message, ctx, db)

    # 2. Existing capability flow (questions about work data).
    capability = _classify_message(user, message)
    kb_sources = _kb_retrieve(user, message)
    if capability is None:
        # Natural-question fallback: answer from the knowledge base when it has
        # relevant context; otherwise the general greeting.
        if kb_sources:
            return _format_kb_sources(kb_sources), _kb_samples(kb_sources), "deterministic"
        return _general_response(user), [], "deterministic"
    if capability not in ROLE_CAPABILITIES.get(user.role, []):
        return _denied_response(user), [], "deterministic"
    handler_result = _HANDLERS[capability](db, user, message)
    text, samples = handler_result[0], handler_result[1]
    # Merge live-record answers with relevant approved knowledge.
    if kb_sources:
        text = text + "\n\n" + _format_kb_sources(kb_sources)
        samples = samples + _kb_samples(kb_sources)
    return text, samples, "deterministic"


# ---------------------------------------------------------------------------
# Optional external LLM integration (OpenAI-compatible API)
# ---------------------------------------------------------------------------

LLM_SYSTEM_PROMPT = (
    "You are the NEXA AI Intelligence Assistant, a role-aware conversational assistant for the "
    "Fidelity Life Assurance AI Fraud Detection Platform.\n\n"
    "Rules:\n"
    "- Answer using ONLY the 'Verified system data context' provided.\n"
    "- Do NOT invent, alter, or guess claims, claim IDs, amounts, policies, risk scores, risk "
    "indicators, OCR extracted fields, investigation evidence, compliance observations, or "
    "statistics. If the context does not contain the information, say you do not have that information.\n"
    "- Always distinguish verified records (numbers/IDs from the context) from AI-generated "
    "recommendations or next steps.\n"
    "- Never approve or reject a claim, alter evidence, or close an investigation; recommend "
    "human review for consequential decisions.\n"
    "- Keep responses concise, professional, and focused on the question. Avoid markdown tables."
)


def _call_llm(message: str, samples: List[Dict[str, Any]], user: User) -> Optional[str]:
    """Calls the configured OpenAI-compatible chat completions endpoint.

    Returns the model text, or None on any failure so callers can fall back to
    deterministic responses with a clear audit trail. The API key is never logged.
    """
    if not settings.CHATBOT_LLM_API_KEY:
        return None
    base = (settings.CHATBOT_LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    context_json = json.dumps(samples, default=str)
    if len(context_json) > 12000:
        context_json = context_json[:12000] + "... (truncated)"
    payload = {
        "model": settings.CHATBOT_LLM_MODEL,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User question: {message}\n\nVerified system data context:\n{context_json}\n\n"
                           "Provide your response using only this context.",
            },
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.CHATBOT_LLM_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("CHATBOT_LLM_CALL_FAILED: %s", exc)
        return None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/suggested-questions", summary="Role-specific suggested questions for the assistant")
async def get_suggested_questions(current_user: User = Depends(get_current_active_user)):
    return {
        "role": current_user.role.value,
        "questions": _suggested_questions(current_user.role),
    }


@router.post("/messages", summary="Send a message to the NEXA AI Intelligence Assistant")
async def send_message(
    req: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")

    db_user_msg = ChatMessage(user_id=current_user.id, role=current_user.role.value, direction="user", content=message)
    db.add(db_user_msg)
    db.commit()

    try:
        text, samples, mode = _answer(
            db, current_user, message,
            history=req.history, exclude_id=db_user_msg.id,
        )
    except Exception as exc:
        logger.exception("CHATBOT_ERROR: %s", exc)
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="NEXA AI Intelligence Assistant is unable to generate a response right now. "
                   "Please try again in a moment or contact IT support.",
        )

    # Optional external LLM refinement: forwards retrieved records with a strict
    # system prompt restricting answers to that context. Falls back to the
    # deterministic response (labelled deterministic_fallback) on any failure.
    if settings.CHATBOT_ENABLED and settings.CHATBOT_LLM_API_KEY and mode == "deterministic":
        llm_text = _call_llm(message, samples, current_user)
        if llm_text:
            verified = "\n".join(f"- {json.dumps(s, default=str)}" for s in samples)
            text = llm_text + "\n\nVerified records retrieved by the platform:\n" + (verified or "- None recorded")
            mode = "llm"
        else:
            mode = "deterministic_fallback"

    db_assistant_msg = ChatMessage(user_id=current_user.id, role=current_user.role.value, direction="assistant", content=text)
    db.add(db_assistant_msg)
    log_audit_trail(
        db, current_user,
        action="CHATBOT_MESSAGE_SENT",
        target=f"Chatbot:Msg:{db_user_msg.id}",
        detail={"message_preview": message[:200], "intent": mode, "conversation_id": req.conversation_id},
    )
    db.commit()

    return ChatMessageResponse(
        response=text,
        sources=samples,
        suggestions=_suggested_questions(current_user.role),
        ai_mode=mode,
    )


@router.get("/history", summary="Get persisted chatbot conversation history for the authenticated user")
async def get_chatbot_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.id)
        .limit(100)
        .all()
    )
    return [
        {
            "direction": r.direction,
            "content": r.content or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.delete("/history", summary="Clear this user's persisted chatbot conversation history")
async def reset_chatbot_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).delete()
    db.commit()
    log_audit_trail(db, current_user, action="CHATBOT_HISTORY_RESET", target="Chatbot:History")
    return {"message": "Conversation history cleared.", "cleared": True}


# ---------------------------------------------------------------------------
# Knowledge base administration (System Administrator only, Phase 5-6)
# ---------------------------------------------------------------------------

def _ensure_admin(user: User) -> None:
    if user.role != RoleEnum.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only System Administrators can manage the knowledge base.",
        )


@router.get("/documents", summary="List knowledge base documents (System Administrator)")
async def list_knowledge_documents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    return [
        {
            "id": d.id,
            "title": d.title,
            "department": d.department,
            "doc_type": d.doc_type,
            "status": d.status,
            "source": d.source,
            "chunk_count": len(d.chunks) if d.chunks else 0,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in list_documents(db)
    ]


@router.get("/documents/search", summary="Search knowledge base (System Administrator)")
async def search_knowledge_documents(
    q: str = Query(..., min_length=1, max_length=2000, description="Natural-language search query"),
    department: Optional[str] = None,
    top_k: int = 5,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    chunks = search(db, q, department=department, top_k=top_k)
    results = []
    for c in chunks:
        doc = db.get(KnowledgeDocument, c.document_id)
        results.append({
            "document_id": c.document_id,
            "chunk_index": c.chunk_index,
            "title": doc.title if doc else None,
            "department": doc.department if doc else None,
            "source": doc.source if doc else None,
            "excerpt": (c.text or "")[:400],
        })
    return {"query": q, "results": results}


@router.post("/documents", summary="Upload a knowledge document (System Administrator)")
async def upload_knowledge_document(
    payload: KnowledgeDocumentUpload,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ensure_admin(current_user)
    doc = add_document(
        db,
        title=payload.title,
        content=payload.content,
        department=payload.department,
        source="manual_upload",
        doc_type=payload.doc_type,
        status=payload.status,
    )
    chunks_added = add_chunks(db, doc.id)
    db.commit()
    log_audit_trail(
        db, current_user,
        action="KNOWLEDGE_DOCUMENT_UPLOADED",
        target=f"KnowledgeDocument:{doc.id}",
        detail={"title": doc.title, "department": doc.department, "doc_type": doc.doc_type, "chunks": chunks_added},
    )
    return {
        "document_id": doc.id,
        "title": doc.title,
        "department": doc.department,
        "doc_type": doc.doc_type,
        "chunks_added": chunks_added,
        "status": doc.status,
    }
