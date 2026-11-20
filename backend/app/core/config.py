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
    TESSERACT_CMD: str = Field(default_factory=lambda: os.getenv("TESSERACT_CMD", "tesseract"))
    
    # Model configuration
    MODEL_VERSION: str = "v1.0-fidelity-rf-iso"
    MODEL_DIR: str = Field(default_factory=lambda: os.getenv("MODEL_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "models"))))

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8010",
        "http://127.0.0.1:8010",
        "*"
    ]

settings = Settings()
