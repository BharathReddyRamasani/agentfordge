"""Database engine, session management and initialization (auto-created database + migrations)."""

import logging
import shutil
import sqlalchemy as sa
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger("agentforge.database")


class Base(DeclarativeBase):
    pass


engine_kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 1800}
if settings.is_sqlite:
    engine_kwargs.update({"connect_args": settings.sqlalchemy_connect_args})
else:
    # Production PostgreSQL: bounded connection pool (never unbounded growth)
    engine_kwargs.update({"pool_size": settings.db_pool_size, "max_overflow": settings.db_max_overflow})
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

import app.models  # noqa: E402,F401  (register all tables on Base.metadata)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_dir() -> None:
    if settings.is_sqlite:
        raw = settings.database_url.split("///", 1)[-1]
        if raw and raw != ":memory:":
            Path(raw).parent.mkdir(parents=True, exist_ok=True)


def _ensure_postgres_database() -> None:
    url = sa.engine.url.make_url(settings.database_url)
    if url.get_backend_name() != "postgresql":
        return
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    with admin_engine.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :name"), {"datname": url.database}
        ).scalar()
        if not exists:
            conn.execute(sa.text('CREATE DATABASE "%s"' % url.database))
            conn.commit()
            logger.info("Created database %s", url.database)
    admin_engine.dispose()


def run_migrations() -> None:
    """Run Alembic migrations to head."""
    _ensure_sqlite_dir()
    if not settings.is_sqlite:
        _ensure_postgres_database()
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    script_dir = Path(__file__).resolve().parents[2] / "alembic"
    cfg.set_main_option("script_location", str(script_dir))
    command.upgrade(cfg, "head")
    logger.info("Database migrations applied (%s)", "sqlite" if settings.is_sqlite else "postgres")


def init_db() -> None:
    """Initialize the database. Alembic for postgres; create_all fallback for lightweight test/dev sqlite."""
    _ensure_sqlite_dir()
    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
        logger.info("SQLite database initialized via create_all")
    else:
        run_migrations()


def reset_db() -> None:
    """Drop all tables and recreate (used by tests)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def clean_workspace() -> None:
    ws = Path(settings.workspace_dir)
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True, exist_ok=True)
