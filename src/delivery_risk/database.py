"""Database connection and session management.

The engine is created once and shared; sessions are created per unit of work.
Configuration comes from the environment, never from code, so the same module
serves local development, tests and deployment.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def get_database_url() -> str:
    """Return the configured database URL, failing loudly if it is absent."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")
    return url


engine: Engine = create_engine(get_database_url())

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Session:
    """Create a new session bound to the shared engine."""
    return SessionLocal()
