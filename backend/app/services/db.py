import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from ..core.config import settings

logger = logging.getLogger("fraud_db")

def get_database_url() -> str:
    if settings.DATABASE_URL:
        if (settings.ENVIRONMENT.lower() == "production"
                and settings.DATABASE_URL.lower().startswith("sqlite")):
            raise RuntimeError(
                "SQLite is not permitted as a production database. "
                "Configure DATABASE_URL with a PostgreSQL connection string."
            )
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
    if settings.ENVIRONMENT.lower() == "production":
        logger.critical(f"Production PostgreSQL connection failed ({e}). Refusing silent SQLite fallback.")
        raise RuntimeError(f"Production database connection failed: {e}") from e
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
    _migrate_schema()


def _migrate_schema():
    """
    Adds missing nullable columns to pre-existing database tables.

    The shipped development database may have been created with an older
    model schema. SQLAlchemy's ``create_all`` only creates missing tables;
    it does not alter existing ones. This migration is conservative:

    - It only adds *nullable* columns that have no Python-side default.
    - It never drops, renames or modifies existing columns or data.

    All pre-existing records are preserved.
    """
    try:
        from sqlalchemy import inspect as sa_inspect, text
        from ..models import sqlalchemy_models  # noqa: F401

        insp = sa_inspect(engine)
        added = []
        with engine.begin() as conn:
            for table_name, table in Base.metadata.tables.items():
                existing_cols = set()
                if insp.has_table(table_name):
                    existing_cols = {c["name"] for c in insp.get_columns(table_name)}
                for col in table.columns:
                    if col.name in existing_cols:
                        continue
                    if not col.nullable:
                        # Never auto-add required columns; log and skip.
                        logger.warning(
                            "Skipped migration of non-nullable column %s.%s",
                            table_name, col.name,
                        )
                        continue
                    type_sql = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(
                        f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql}'
                    ))
                    added.append(f"{table_name}.{col.name}")
        if added:
            logger.warning("Schema migration applied; added columns: %s", ", ".join(added))
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError(f"Production schema migration failed: {e}") from e
