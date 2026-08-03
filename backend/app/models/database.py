"""
Database engine and session setup (SQLAlchemy).

WHAT IS SQLAlchemy AND WHY USE AN ORM?
-----------------------------------------
SQLAlchemy is a Python SQL toolkit and Object-Relational Mapper (ORM). An
ORM lets us model database tables as Python classes and rows as Python
objects, instead of writing raw SQL strings everywhere. Benefits:

* Type-safe, IDE-friendly access to columns (`document.filename` instead of
  `row["filename"]`).
* Automatic protection against SQL injection (parameters are always bound,
  never string-formatted into the query).
* Swapping the underlying database later (SQLite -> Postgres) is a one-line
  connection-string change, not a rewrite of every query.

WHY SQLite HERE?
-------------------
SQLite stores the entire database in a single file on disk with zero setup
required - no server process, no credentials. That is ideal for a learning
project and even for many small production services. We only store
*metadata* here (document names, chunk text/positions, chat history) -
the actual vector embeddings live in FAISS, a specialised vector index.

THE `get_db` DEPENDENCY
---------------------------
FastAPI route handlers should never create their own DB sessions. Instead,
they declare `db: Session = Depends(get_db)`. This "dependency injection"
pattern guarantees:
1. Every request gets a fresh, isolated session.
2. The session is *always* closed afterwards (even if the request raises
   an exception), because the `finally` block below always runs.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings

# `check_same_thread=False` is required for SQLite when it's accessed from
# multiple threads, which happens under Uvicorn's threaded request handling.
# This is safe here because each request gets its own Session (see get_db).
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class that all ORM models inherit from."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables that don't exist yet.

    Called once at application startup. Using `create_all` (rather than a
    full migration tool like Alembic) is a deliberate simplification for
    this project's scope - it's enough to demonstrate schema design without
    the overhead of migration tooling.
    """
    # Import models here (not at module top-level) so that `Base` already
    # knows about every table before `create_all` runs, without creating a
    # circular import between `database.py` and the model modules.
    from app.models import chat, document  # noqa: F401

    Base.metadata.create_all(bind=engine)
