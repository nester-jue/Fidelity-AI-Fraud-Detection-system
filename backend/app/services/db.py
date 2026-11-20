import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from ..core.config import settings

logger = logging.getLogger("fraud_db")

def get_database_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    # Default to PostgreSQL
    pg_url = (
        f"postgresql+psycopg://{settings.POSTGRES_USER}:"
        f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    return pg_url

db_url = get_database_url()

# Try connecting to PostgreSQL; fallback to local SQLite for development convenience
try:
    if "postgresql" in db_url:
        engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        # Test connection
        with engine.connect() as conn:
            pass
        logger.info(f"Connected to PostgreSQL at {settings.POSTGRES_HOST}")
    else:
        engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
except Exception as e:
    # Ensure local data directory exists
    base_data = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))
    os.makedirs(base_data, exist_ok=True)
    sqlite_path = os.path.join(base_data, "frauddb.sqlite")
    fallback_url = f"sqlite:///{sqlite_path}"
    logger.warning(f"Could not connect to PostgreSQL ({e}). Falling back to local SQLite at {sqlite_path}")
    engine = create_engine(fallback_url, echo=False, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes all tables defined in models."""
    from ..models import sqlalchemy_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
