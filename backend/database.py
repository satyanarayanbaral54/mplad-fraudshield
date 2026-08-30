from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database, creating all tables."""
    from models.db_models import (  # noqa: F401
        Project, Vendor, Flag, SurveyResponse, SurveyBatch, GeoCheckpoint
    )
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_light_migrations()


def _apply_sqlite_light_migrations():
    """Add new demo columns to existing SQLite DBs created before migrations."""
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "survey_responses" in inspector.get_table_names():
        existing = {col["name"] for col in inspector.get_columns("survey_responses")}
        additions = {
            "satisfaction_score": "INTEGER",
            "money_spent_properly": "VARCHAR(20)",
            "batch_id": "VARCHAR(100)",
        }
        with engine.begin() as conn:
            for column, ddl_type in additions.items():
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE survey_responses ADD COLUMN {column} {ddl_type}"))
