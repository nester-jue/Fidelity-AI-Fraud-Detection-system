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
    policy = relationship("Policy", back_populates="claims")
    customer = relationship("Customer", back_populates="claims")
    assigned_officer = relationship("User", foreign_keys=[assigned_officer_id])
    documents = relationship("ClaimDocument", back_populates="claim", cascade="all, delete-orphan")
    assessment = relationship("FraudAssessment", uselist=False, back_populates="claim")

class ClaimDocument(Base):
    __tablename__ = "claim_documents"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=utc_now)
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
    claim = relationship("Claim")
    investigator = relationship("User")

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
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=utc_now)
    processed_at = Column(DateTime, nullable=True)
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
