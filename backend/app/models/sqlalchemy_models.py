from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..services.db import Base
import enum

def utc_now():
    return datetime.now(timezone.utc)

class RoleEnum(str, enum.Enum):
    SYSTEM_ADMIN = "system_admin"
    CLAIMS_OFFICER = "claims_officer"
    CLAIMS_MANAGER = "claims_manager"
    FRAUD_INVESTIGATOR = "fraud_investigator"
    COMPLIANCE_OFFICER = "compliance_officer"
    MANAGEMENT = "management"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.CLAIMS_OFFICER)
    department = Column(String, nullable=True)  # e.g. "Claims", "Executive", "Compliance", "Investigations", "IT"
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    national_id = Column(String, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    policies = relationship("Policy", back_populates="customer")
    claims = relationship("Claim", back_populates="customer")

class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True, index=True)
    policy_number = Column(String, unique=True, index=True, nullable=False)
    policy_type = Column(String, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    customer = relationship("Customer", back_populates="policies")
    claims = relationship("Claim", back_populates="policy")

class Claim(Base):
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String, unique=True, index=True, nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    assigned_officer_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Claims officer assignment
    claim_type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    incident_date = Column(DateTime, nullable=False)
    submission_date = Column(DateTime, default=utc_now)
    description = Column(Text, nullable=True)
    status = Column(String, default="submitted")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    # Advanced fraud intelligence (enterprise upgrade) — all nullable so the
    # schema migration path in services/db._migrate_schema() can add them to
    # pre-existing databases without data loss.
    beneficiary_name = Column(String, nullable=True)
    beneficiary_nin = Column(String, nullable=True)  # Beneficiary National/ID number (where collected)
    beneficiary_change_count = Column(Integer, nullable=True, default=0)
    beneficiary_last_change_date = Column(DateTime, nullable=True)
    payment_account_refs = Column(JSON, nullable=True)  # Bank/payment account references (where lawfully collected)
    phone_number = Column(String, nullable=True)
    email_address = Column(String, nullable=True)
    policy = relationship("Policy", back_populates="claims")
    customer = relationship("Customer", back_populates="claims")
    assigned_officer = relationship("User", foreign_keys=[assigned_officer_id])
    documents = relationship("ClaimDocument", back_populates="claim", cascade="all, delete-orphan")
    assessment = relationship("FraudAssessment", uselist=False, back_populates="claim")
    beneficiary_changes = relationship("ClaimBeneficiaryChange", back_populates="claim", cascade="all, delete-orphan")


class ClaimBeneficiaryChange(Base):
    """History of beneficiary alterations on a claim (Phase 3/5 support).

    Every row is an append-only audit record: once recorded it is not
    modified or deleted except via the Evidence/Audit machinery.
    """
    __tablename__ = "claim_beneficiary_changes"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    beneficiary_name = Column(String, nullable=True)
    beneficiary_nin = Column(String, nullable=True)
    changed_at = Column(DateTime, default=utc_now)
    notes = Column(Text, nullable=True)
    claim = relationship("Claim", back_populates="beneficiary_changes")
    changed_by = relationship("User")


class ClaimTimelineEvent(Base):
    """One chronological event in a claim's reconstructed lifecycle timeline (Phase 6)."""
    __tablename__ = "claim_timeline_events"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # e.g. POLICY_ACTIVATED, INCIDENT_OCCURRED, BENEFICIARY_CHANGED
    event_description = Column(Text, nullable=True)
    event_timestamp = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)  # e.g. db_record, ocr, beneficiary_history, fraud_engine
    sequence_order = Column(Integer, nullable=True)  # explicit ordering hint when timestamps may tie
    is_fabricated = Column(Boolean, default=False)  # True when the event is derived (not observed)
    created_at = Column(DateTime, default=utc_now)
    claim = relationship("Claim")


class EvidenceRecord(Base):
    """Digital evidence record for investigations (Phase 9).

    Every record carries the SHA-256 hash of the stored artifact; integrity
    can be re-verified on demand. Records are immutable once marked verified.
    """
    __tablename__ = "evidence_records"
    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("ocr_documents.id"), nullable=True)  # linked OCR document (if any)
    evidence_type = Column(String, nullable=False)  # e.g. DOCUMENT, NOTE, PHOTOGRAPH, DIGITAL_ARTIFACT
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=True)  # original artifact path (preserved)
    sha256_hash = Column(String, nullable=True, index=True)
    status = Column(String, default="collected")  # collected | pending_review | under_review | verified | rejected
    integrity_verified = Column(Boolean, default=False)
    integrity_verified_at = Column(DateTime, nullable=True)
    collected_at = Column(DateTime, default=utc_now)
    collected_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    linked_claim_id_snapshot = Column(String, nullable=True)  # snapshot of claim ID at registration (audit)
    investigation = relationship("Investigation")
    claim = relationship("Claim")
    document = relationship("OCRDocument")
    collected_by = relationship("User")


class FraudNetworkNode(Base):
    """Entity in the fraud relationship network (Phase 3).

    Nodes are built dynamically from records; this table stores a materialised
    view of connected entities with aggregate attributes.
    """
    __tablename__ = "fraud_network_nodes"
    id = Column(String, primary_key=True, index=True)  # e.g. CUST-123, POL-XYZ, CLAIM-abc, BENEF-{nin}, OCRDOC-1
    entity_type = Column(String, nullable=False)  # customer | policy | claim | document | beneficiary | payment_ref
    entity_key = Column(String, nullable=False)  # natural key used to link (national_id, claim_id, hash, ...)
    name = Column(String, nullable=True)
    national_id = Column(String, nullable=True)
    customer_id = Column(Integer, nullable=True)
    policy_number = Column(String, nullable=True)
    claim_id = Column(Integer, nullable=True)
    document_hash = Column(String, nullable=True)
    is_suspicious = Column(Boolean, default=False)
    risk_contribution = Column(Float, default=0.0)
    total_edges = Column(Integer, default=0)
    risk_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utc_now)


class FraudNetworkEdge(Base):
    """A relationship between two network nodes with strength and supporting evidence (Phase 3)."""
    __tablename__ = "fraud_network_edges"
    id = Column(Integer, primary_key=True, index=True)
    node_a_id = Column(String, ForeignKey("fraud_network_nodes.id"), nullable=False, index=True)
    node_b_id = Column(String, ForeignKey("fraud_network_nodes.id"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False)  # SHARED_IDENTITY, SAME_BENEFICIARY, REUSED_DOCUMENT, etc.
    strength = Column(Float, default=1.0)  # 0..1
    evidence = Column(Text, nullable=True)
    claim_ids = Column(JSON, nullable=True)  # claims that produced the edge
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)
    is_suspicious = Column(Boolean, default=False)
    node_a = relationship("FraudNetworkNode", foreign_keys=[node_a_id])
    node_b = relationship("FraudNetworkNode", foreign_keys=[node_b_id])


class PredictiveAlert(Base):
    """Proactive fraud risk alerts from the predictive monitoring engine (Phase 11)."""
    __tablename__ = "predictive_alerts"
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String, nullable=False)  # e.g. SUSPICIOUS_PATTERN, UNUSUAL_AMOUNT, CLUSTER_EMERGING
    severity = Column(String, nullable=False)  # INFO | WARNING | HIGH | CRITICAL
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=True)
    description = Column(Text, nullable=True)
    risk_score = Column(Float, default=0.0)
    status = Column(String, default="new")  # new | acknowledged | resolved | dismissed
    evidence_summary = Column(Text, nullable=True)
    resolution_note = Column(Text, nullable=True)  # recorded when a human resolves/dismisses
    generated_at = Column(DateTime, default=utc_now)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    claim = relationship("Claim")
    customer = relationship("Customer")
    policy = relationship("Policy")


class ModelRetrainingRequest(Base):
    """Controlled model retraining workflow (Phase 13).

    Retraining is requested with an approved validated dataset and only
    deployed after explicit approval.
    """
    __tablename__ = "model_retraining_requests"
    id = Column(Integer, primary_key=True, index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    new_model_version = Column(String, nullable=False)
    base_model_version = Column(String, nullable=True)
    dataset_version = Column(String, nullable=False)
    dataset_records = Column(Integer, nullable=True)  # number of training records used
    training_method = Column(String, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="requested")  # requested | approved | deployed | rejected | rolled_back
    notes = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, nullable=True)
    deployed_at = Column(DateTime, nullable=True)
    requested_at = Column(DateTime, default=utc_now)
    approved_at = Column(DateTime, nullable=True)
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])

class ClaimDocument(Base):
    __tablename__ = "claim_documents"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=utc_now)
    # Advanced forensic analysis findings (Phase 9/4)
    forensic_findings = Column(JSON, nullable=True)
    claim = relationship("Claim", back_populates="documents")

class FraudAssessment(Base):
    __tablename__ = "fraud_assessments"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), unique=True, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_category = Column(String, nullable=False)
    indicators = Column(JSON, nullable=True)  # list of strings or dicts
    explanation = Column(Text, nullable=True)
    model_version = Column(String, nullable=True)
    assessed_at = Column(DateTime, default=utc_now)
    # Ensemble components (Phase 2 upgrade; nullable for older rows)
    rule_score = Column(Float, nullable=True)  # rule-based component
    ensemble_score = Column(Float, nullable=True)  # blended score persisted for audit
    isolation_score = Column(Float, nullable=True)  # statistical isolation component
    claim = relationship("Claim", back_populates="assessment")

class Investigation(Base):
    __tablename__ = "investigations"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    investigator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="open")
    notes = Column(Text, nullable=True)
    opened_at = Column(DateTime, default=utc_now)
    closed_at = Column(DateTime, nullable=True)
    outcome = Column(String, nullable=True)  # confirmed_fraud | cleared
    evidence_documents = Column(JSON, nullable=True)  # IDs of linked OCRDocument records
    claim = relationship("Claim")
    investigator = relationship("User")


class ClaimNote(Base):
    """Internal notes attached to a claim by the Claims Management workspace."""
    __tablename__ = "claim_notes"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    claim = relationship("Claim")
    user = relationship("User")


class InvestigationNote(Base):
    """Timestamped notes recorded by Fraud Investors during an investigation."""
    __tablename__ = "investigation_notes"
    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    investigation = relationship("Investigation")
    user = relationship("User")


class ComplianceReport(Base):
    """Generated compliance and regulatory monitoring reports (Compliance Officer workspace)."""
    __tablename__ = "compliance_reports"
    id = Column(Integer, primary_key=True, index=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_type = Column(String, nullable=False)  # e.g. FRAUD_COMPLIANCE_REVIEW, AUDIT_EXCEPTIONS
    title = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=utc_now)
    generated_by = relationship("User")


class ManagementReport(Base):
    """Downloadable executive management summaries (Management Workspace)."""
    __tablename__ = "management_reports"
    id = Column(Integer, primary_key=True, index=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_type = Column(String, nullable=True)  # e.g. EXECUTIVE_KPI_SNAPSHOT, FRAUD_TREND_REVIEW
    title = Column(String, nullable=True)
    summary = Column(JSON, nullable=True)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=utc_now)
    generated_by = relationship("User")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    detail = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=utc_now)
    user = relationship("User")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    user = relationship("User")

class ModelPerformance(Base):
    __tablename__ = "model_performance"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    evaluated_at = Column(DateTime, default=utc_now)


class OCRDocument(Base):
    """Tracks every document uploaded for OCR processing, including extraction results."""
    __tablename__ = "ocr_documents"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True)  # Linked claim (if any)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    document_type = Column(String, nullable=True)  # Death Certificate, Medical Report, etc.
    file_size_bytes = Column(Integer, nullable=True)
    document_hash_sha256 = Column(String, nullable=True)
    # OCR extraction results
    ocr_engine = Column(String, nullable=True)  # Tesseract, Azure, etc.
    raw_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    extracted_fields = Column(JSON, nullable=True)  # Structured extracted data
    extracted_dates = Column(JSON, nullable=True)
    extracted_amounts = Column(JSON, nullable=True)
    extracted_national_ids = Column(JSON, nullable=True)
    # Verification status
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    has_date_mismatch = Column(Boolean, default=False)
    missing_fields = Column(JSON, nullable=True)
    flags = Column(JSON, nullable=True)
    is_manually_verified = Column(Boolean, default=False)
    # Sample claim-form documents (genuine public claim forms, data/sample_claim_documents)
    is_sample_document = Column(Boolean, default=False, nullable=True)
    sample_category = Column(String, nullable=True)  # life_insurance | medical_insurance | funeral_claims | hospitalisation | accident_disability | other
    source_institution = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    source_note = Column(String, nullable=True)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=utc_now)
    processed_at = Column(DateTime, nullable=True)
    # Advanced forensic analysis findings (Phase 9/4)
    forensic_findings = Column(JSON, nullable=True)  # image integrity, signature, reuse, comparison
    forensic_review_requested = Column(Boolean, default=False)
    forensic_review_status = Column(String, default="not_requested")  # not_requested | review_required | reviewed
    forensic_reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    forensic_reviewed_at = Column(DateTime, nullable=True)
    # Relationships
    claim = relationship("Claim", foreign_keys=[claim_id])
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
    verified_by = relationship("User", foreign_keys=[verified_by_id])
    corrections = relationship("OCRCorrection", back_populates="document", cascade="all, delete-orphan")


class OCRCorrection(Base):
    """Audit trail for manual corrections made to OCR-extracted fields."""
    __tablename__ = "ocr_corrections"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("ocr_documents.id"), nullable=False)
    corrected_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    field_name = Column(String, nullable=False)
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)
    correction_note = Column(Text, nullable=True)
    corrected_at = Column(DateTime, default=utc_now)
    document = relationship("OCRDocument", back_populates="corrections")
    corrected_by = relationship("User", foreign_keys=[corrected_by_id])


class ChatMessage(Base):
    """Persisted conversational history for the NEXA AI Intelligence Assistant.

    Every user message and assistant reply is stored per authenticated user so
    chat history is retained within the session. Assistant content is generated
    from real records only (see app/api/chatbot.py).
    """
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=True)
    direction = Column(String, nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    user = relationship("User")


class KnowledgeDocument(Base):
    """A document that the NEXA AI Knowledge Base can answer questions from.

    Sources: verified company knowledge packages (docs/knowledge_packages),
    later uploaded Fidelity manuals/policies/procedures, and — in the future —
    live OCR text linked to system records. ``department`` is the retrieval
    scope: the chatbot only returns chunks whose department matches the
    caller's role ('shared' applies to everyone).
    """
    __tablename__ = "knowledge_documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    department = Column(String, nullable=False, index=True)  # e.g. 'claims_officer', 'shared'
    source = Column(String, nullable=False)  # e.g. 'package', 'manual_upload', 'ocr_extraction'
    doc_type = Column(String, nullable=False, default="manual")  # package | manual | sop | policy | other
    status = Column(String, default="verified")  # verified | draft | restricted
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    """One searchable segment of a KnowledgeDocument with its embedding vector."""
    __tablename__ = "knowledge_chunks"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)  # hashed embedding vector (list[float])
    created_at = Column(DateTime, default=utc_now)
    document = relationship("KnowledgeDocument", back_populates="chunks")
