import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    # App config
    APP_NAME: str = "NEXA AI Fraud Detection System"
    APP_VERSION: str = "1.0.0"
    ORGANIZATION: str = "Fidelity Life Assurance Company"
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8010")))
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    FRONTEND_URL: str = Field(default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:5174"))
    
    # Database configuration
    POSTGRES_USER: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    POSTGRES_PASSWORD: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "postgres"))
    POSTGRES_HOST: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    POSTGRES_PORT: str = Field(default_factory=lambda: os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "frauddb"))
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    
    # Security & JWT
    JWT_SECRET_KEY: str = Field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "fidelity-life-nexa-fraud-detection-secret-2026"))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # Document storage & OCR
    DOCUMENTS_DIR: str = Field(default_factory=lambda: os.getenv("DOCUMENTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "documents"))))
    SAMPLE_CLAIM_DOCUMENTS_DIR: str = Field(default_factory=lambda: os.getenv("SAMPLE_CLAIM_DOCUMENTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample_claim_documents"))))
    TESSERACT_CMD: str = Field(default_factory=lambda: os.getenv("TESSERACT_CMD", "tesseract"))
    
    # Model configuration
    MODEL_VERSION: str = "v1.0-fidelity-rf-iso"
    MODEL_DIR: str = Field(default_factory=lambda: os.getenv("MODEL_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "models"))))

    # Fraud risk classification thresholds (configurable)
    RISK_THRESHOLD_LOW_MAX: int = int(os.getenv("RISK_THRESHOLD_LOW_MAX", "29"))
    RISK_THRESHOLD_MEDIUM_MAX: int = int(os.getenv("RISK_THRESHOLD_MEDIUM_MAX", "59"))
    RISK_THRESHOLD_HIGH_MAX: int = int(os.getenv("RISK_THRESHOLD_HIGH_MAX", "79"))
    RISK_THRESHOLD_CRITICAL_MAX: int = int(os.getenv("RISK_THRESHOLD_CRITICAL_MAX", "100"))
    RISK_THRESHOLD_LOW_MIN: int = 0
    RISK_THRESHOLD_MEDIUM_MIN: int = 30
    RISK_THRESHOLD_HIGH_MIN: int = 60
    RISK_THRESHOLD_CRITICAL_MIN: int = 80

    # Document upload limits
    MAX_DOCUMENT_SIZE_MB: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "20"))

    @property
    def risk_thresholds(self) -> dict:
        return {
            "low": [self.RISK_THRESHOLD_LOW_MIN, self.RISK_THRESHOLD_LOW_MAX],
            "medium": [self.RISK_THRESHOLD_MEDIUM_MIN, self.RISK_THRESHOLD_MEDIUM_MAX],
            "high": [self.RISK_THRESHOLD_HIGH_MIN, self.RISK_THRESHOLD_HIGH_MAX],
            "critical": [self.RISK_THRESHOLD_CRITICAL_MIN, self.RISK_THRESHOLD_CRITICAL_MAX],
        }

    # NEXA AI Intelligence Assistant (chatbot) — optional external LLM integration.
    # When CHATBOT_LLM_API_KEY is set, the chatbot forwards retrieved records to
    # an OpenAI-compatible chat completions endpoint; otherwise it answers
    # deterministically from real system records. Never log the API key.
    CHATBOT_ENABLED: bool = os.getenv("CHATBOT_ENABLED", "true").lower() == "true"
    CHATBOT_LLM_API_KEY: str = os.getenv("CHATBOT_LLM_API_KEY", "")
    CHATBOT_LLM_BASE_URL: str = os.getenv("CHATBOT_LLM_BASE_URL", "https://api.openai.com/v1")
    CHATBOT_LLM_MODEL: str = os.getenv("CHATBOT_LLM_MODEL", "gpt-4o-mini")

    # NEXA Departmental AI Knowledge Base (RAG, Phase 5).
    # Retrieval uses hashed embeddings + cosine similarity — no ML deps needed.
    # CHATBOT_KB_ENABLED gates the whole feature; structured departmental
    # packages live in docs/knowledge_packages and are seeded into the store.
    CHATBOT_KB_ENABLED: bool = os.getenv("CHATBOT_KB_ENABLED", "true").lower() == "true"
    CHATBOT_KB_TOP_K: int = int(os.getenv("CHATBOT_KB_TOP_K", "5"))
    CHATBOT_KB_THRESHOLD: float = float(os.getenv("CHATBOT_KB_THRESHOLD", "0.15"))
    CHATBOT_KB_SEED: bool = os.getenv("CHATBOT_KB_SEED", "true").lower() == "true"
    CHATBOT_KB_PACKAGES_DIR: str = os.getenv(
        "CHATBOT_KB_PACKAGES_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "knowledge_packages")),
    )

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8010",
        "http://127.0.0.1:8010",
        "*"
    ]

settings = Settings()
